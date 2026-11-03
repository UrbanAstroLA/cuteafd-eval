# SPDX-License-Identifier: Apache-2.0
"""local-exl3-core-dequant -- local loader patch ("vLLM fork v0.9.2-experimental").

NOT part of tpurtell's vLLM fork and not his release. It lets the fork's v0.9.2 image load
wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6 (K6 EXL3 core and head, K4 EXL3 MTP core): every
non-expert EXL3 matrix is rebuilt to a BF16 ``<module>.weight`` while the weights stream in. The
routed experts keep the fork's b12x EXL3 path, so the model is built and loaded exactly like the K4
checkpoint (whose core and head are BF16 ``.weight`` tensors of the same names and shapes).

Switch (read once per process):
  LOCAL_EXL3_DEQUANT_NONEXPERT=bf16   on; unset or empty = stock behaviour (nothing here runs)
Options (only read when the switch is on):
  LOCAL_EXL3_DEQUANT_DEVICE=cuda|cpu  where to decode (default: the current CUDA device if any).
                                        The result is bit-identical on either (exact arithmetic).
  LOCAL_EXL3_DEQUANT_DITHER_SEED=<n>  noise A/B arm only: add U(-1/2, +1/2) BF16-ulp noise, seeded
                                        per matrix, before the single rounding (doubles the rounding
                                        noise variance). Unset for every normal run.

Numerics (exllamav3 get_weight_tensor; GPTQModel exl3_lib.quantize.reconstruct_exl3_tensors):
  W_eff[in, out] = diag(suh) . H . W_inner . H . diag(svh),  H = block-diagonal Sylvester Hadamard,
  order 128, normalised by 1/sqrt(128), on both sides.
  * W_inner is the fp16 trellis decode (MCG codebook), ported from b12x's numpy reference decoder
    (/opt/b12x/tests/gemm/test_trellis_linear.py: _decode_lane, _decode_3inst_fp16,
    _reconstruct_native). Integer ops plus one fp16 rounding of (lo + hi), as in every EXL3 kernel.
  * The +-1 Hadamard is applied unnormalised and the two 1/sqrt(128) factors are folded into one
    exact division by 128. W_inner values are multiples of 2^-13 below 4 in magnitude, so every
    intermediate has at most 51 significant bits: fp64 holds W_eff exactly, on any device, in any
    summation order.
  * W_eff is rounded once, to nearest-even, to BF16 (bit-level rounding; torch's float64 -> bfloat16
    cast goes through float32 and would round twice).
"""
from __future__ import annotations

import hashlib
import os
import re
import time
import zlib
from collections.abc import Iterable, Iterator
from functools import lru_cache
from typing import Any

import torch

MARKER = "local-exl3-core-dequant"
MCG_MULTIPLIER = 0xCBAC1FED
_FIELDS = frozenset(("trellis", "suh", "svh", "mcg", "mul1", "su", "sv"))
# Same expression as Exl3Config._configure_standard_fused_moe (exl3.py:656-660): what stays in
# tensor_storage must all match it, or the b12x fused-MoE path does not engage.
STANDARD_EXPERT = re.compile(
    r"^(?:model(?:\.language_model)?\.layers\.\d+|mtp\.\d+)"
    r"\.mlp\.experts\.\d+\."
    r"(?:gate_proj|up_proj|down_proj)$"
)
# Three rebuilt tensors whose sha256 is logged at load, to compare with the CPU validation receipt.
HASHED_OWNERS = (
    "model.language_model.layers.0.self_attn.q_proj",
    "model.language_model.layers.3.self_attn.q_b_proj",
    "lm_head",
)
_ELEMENTS_PER_CHUNK = 1 << 24  # decode temporaries ~1 GB; fixed, so dither streams are device-free


def _logger():
    try:
        from vllm.logger import init_logger
        return init_logger(__name__)
    except Exception:  # standalone use (CPU validation)
        import logging
        return logging.getLogger(MARKER)


def mode() -> str:
    """'' (off, stock) or 'bf16'."""
    value = os.environ.get("LOCAL_EXL3_DEQUANT_NONEXPERT", "").strip().lower()
    if value not in ("", "bf16"):
        raise ValueError("LOCAL_EXL3_DEQUANT_NONEXPERT must be unset or 'bf16'")
    return value


# --------------------------------------------------------------------------------------------
# Exl3Config hook: called from Exl3Config.maybe_update_config before _configure_standard_fused_moe
# --------------------------------------------------------------------------------------------
def split_nonexpert_storage(quant_config: Any) -> None:
    """Move non-expert EXL3 records from tensor_storage to dequant_storage (switch on only).

    Merges rather than replaces, so a second maybe_update_config on an already split config (an
    expert-only tensor_storage) keeps the records found the first time.
    """
    if not mode():
        return
    storage = quant_config.tensor_storage
    found = {
        name: entry for name, entry in storage.items()
        if entry.get("quant_format") == "exl3" and not STANDARD_EXPERT.fullmatch(name)
    }
    for name in found:
        del storage[name]
    quant_config.dequant_storage.update(found)
    left = [name for name, entry in storage.items()
            if entry.get("quant_format") == "exl3" and not STANDARD_EXPERT.fullmatch(name)]
    if left:  # cannot happen; keeps the invariant explicit
        raise ValueError(f"{MARKER}: non-expert EXL3 records remain: {left[:4]}")
    if found:
        _logger().warning(
            "%s: %d non-expert EXL3 matrices will be reconstructed to BF16 at load "
            "(local loader patch, not tpurtell's release); %d EXL3 expert records stay on b12x",
            MARKER, len(quant_config.dequant_storage), len(storage))


def dequant_entry(quant_config: Any, owner: str) -> dict[str, Any] | None:
    storage = getattr(quant_config, "dequant_storage", None)
    if not storage:
        return None
    # The fork's own name-candidate expansion (model. / language_model. / MTP spellings).
    return quant_config._storage_entry(owner, storage)


def canonical_name(quant_config: Any, entry: dict[str, Any]) -> str:
    for name, value in quant_config.dequant_storage.items():
        if value is entry:
            return name
    raise KeyError("record not in dequant_storage")


# --------------------------------------------------------------------------------------------
# Decoder
# --------------------------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _plan(bits: int) -> tuple[list[int], list[int], list[int], list[int]]:
    """Per tile position p = lane*8 + weight: (first word, last word, shift) of its 16-bit window,
    and its row-major index in the 16x16 tile. Mirrors b12x _decode_lane / _reconstruct_native."""
    width = 8 * bits
    first, last, shift, dest = [], [], [], []
    for lane in range(32):
        row0 = (lane % 4) * 2
        rows = (row0, row0 + 1, row0 + 8, row0 + 9)
        col0 = lane // 8
        col1 = col0 + 4
        parity = (lane >> 2) & 1
        for weight in range(8):
            end_bit = (lane * 8 + weight + 257) * bits
            start_bit = end_bit - 16
            fw = start_bit // 32
            lw = (end_bit - 1) // 32
            first.append(fw % width)
            last.append(lw % width)
            shift.append((lw + 1) * 32 - end_bit)
            dest.append(rows[weight % 4] * 16 + 2 * (col0 if weight < 4 else col1) + parity)
    assert sorted(dest) == list(range(256))
    return first, last, shift, dest


@lru_cache(maxsize=None)
def _plan_tensors(bits: int, device: str):
    first, last, shift, dest = _plan(bits)
    dev = torch.device(device)
    inverse = [0] * 256
    for p, d in enumerate(dest):
        inverse[d] = p
    as_long = lambda v: torch.tensor(v, dtype=torch.int64, device=dev)  # noqa: E731
    shift_t = as_long(shift)
    return as_long(first), as_long(last), shift_t, 32 - shift_t, as_long(inverse)


def decode_inner_fp16(trellis: torch.Tensor, multiplier: int = MCG_MULTIPLIER) -> torch.Tensor:
    """trellis int16 [k_tiles, n_tiles, 16*bits] (MCG) -> fp16 W_inner [16*k_tiles, 16*n_tiles]."""
    k_tiles, n_tiles, width16 = trellis.shape
    bits = width16 // 16
    first, last, shift, lshift, inverse = _plan_tensors(bits, str(trellis.device))
    halves = trellis.to(torch.int64) & 0xFFFF
    words = halves[..., 0::2] | (halves[..., 1::2] << 16)  # little-endian uint32 words, [k, n, 8*bits]
    del halves
    hi_word = words.index_select(-1, first) & 0xFFFF  # only its low 16 bits can reach the window
    lo_word = words.index_select(-1, last)
    del words
    window = ((lo_word >> shift) | (hi_word << lshift)) & 0xFFFF
    del hi_word, lo_word
    x = (window * int(multiplier)) & 0xFFFFFFFF
    x = (x & 0x8FFF8FFF) ^ 0x3B603B60
    lo = x & 0xFFFF
    hi = x >> 16
    del x, window

    def as_fp16(v: torch.Tensor) -> torch.Tensor:
        return torch.where(v >= 0x8000, v - 0x10000, v).to(torch.int16).view(torch.float16)

    # Both halves have exponents in [-3, 0], so the fp32 sum is exact and this is one fp16 rounding,
    # identical to __hadd and to numpy's float16 addition in the reference decoder.
    value = (as_fp16(lo).to(torch.float32) + as_fp16(hi).to(torch.float32)).to(torch.float16)
    del lo, hi
    tiles = value.index_select(-1, inverse).view(k_tiles, n_tiles, 16, 16)
    return tiles.permute(0, 2, 1, 3).reshape(k_tiles * 16, n_tiles * 16)


@lru_cache(maxsize=None)
def _hadamard_pm1(device: str) -> torch.Tensor:
    """Unnormalised Sylvester Hadamard of order 128, H[i, j] = (-1)^popcount(i & j) (symmetric)."""
    idx = torch.arange(128, dtype=torch.int64)
    bits = idx[:, None] & idx[None, :]
    parity = torch.zeros_like(bits)
    for b in range(7):
        parity ^= (bits >> b) & 1
    return (1 - 2 * parity).to(torch.float64).to(device)


_KEEP = (1 << 44) - 1  # rounding increment below the BF16 lsb (fp64 keeps 52 fraction bits, BF16 7)
_DROP = ~((1 << 45) - 1)


def round_bf16(x: torch.Tensor) -> torch.Tensor:
    """Correctly rounded (nearest-even) float64 -> bfloat16, for finite values in BF16 normal range."""
    bits = x.contiguous().view(torch.int64)
    bits = (bits + (_KEEP + ((bits >> 45) & 1))) & _DROP
    return bits.view(torch.float64).to(torch.float32).to(torch.bfloat16)  # both casts exact now


def weff_fp64_block(trellis_cols: torch.Tensor, suh: torch.Tensor, svh_cols: torch.Tensor,
                    multiplier: int = MCG_MULTIPLIER) -> torch.Tensor:
    """Exact W_eff[in, cols] (float64) for a column block that is a multiple of 128 wide."""
    w = decode_inner_fp16(trellis_cols, multiplier).to(torch.float64)
    rows, cols = w.shape
    h = _hadamard_pm1(str(w.device))
    w = torch.matmul(h, w.view(rows // 128, 128, cols)).view(rows, cols)
    w.mul_(suh.to(torch.float64).unsqueeze(1))
    w = torch.matmul(w.view(rows, cols // 128, 128), h).view(rows, cols)
    w.mul_(svh_cols.to(torch.float64).unsqueeze(0))
    w.div_(128.0)
    return w


def column_chunk(in_features: int) -> int:
    return max(128, (_ELEMENTS_PER_CHUNK // in_features) // 128 * 128)


def _dither_generator(seed: int, name: str) -> torch.Generator:
    gen = torch.Generator(device="cpu")
    gen.manual_seed((int(seed) * 1_000_003 + zlib.crc32(name.encode())) % (1 << 63))
    return gen


def _dither(w: torch.Tensor, gen: torch.Generator) -> torch.Tensor:
    """w + U(-1/2, 1/2) * ulp_bf16(w); zeros stay zero. Noise drawn on the CPU (device-independent)."""
    u = torch.rand(w.shape, generator=gen, dtype=torch.float64).sub_(0.5).to(w.device)
    _, exponent = torch.frexp(w)  # |w| in [2^(e-1), 2^e)  ->  BF16 ulp = 2^(e-8)
    ulp = torch.ldexp(torch.ones_like(w), (exponent - 8).to(w.dtype))
    return torch.where(w == 0, w, w + u * ulp)


def validate_record(entry: dict[str, Any], parts: dict[str, torch.Tensor], name: str) -> int:
    """Check the stored geometry against the record; return the bitrate K."""
    if "mul1" in parts or "mcg" not in parts or not {"trellis", "suh", "svh"} <= parts.keys():
        raise ValueError(f"{MARKER}: {name}: needs MCG trellis/suh/svh/mcg, got {sorted(parts)}")
    multiplier = int(parts["mcg"].reshape(-1)[0].item()) & 0xFFFFFFFF
    if multiplier != MCG_MULTIPLIER or int(entry.get("mcg_multiplier", MCG_MULTIPLIER)) != MCG_MULTIPLIER:
        raise ValueError(f"{MARKER}: {name}: unexpected MCG multiplier {multiplier:#x}")
    in_f, out_f = int(entry["in_features"]), int(entry["out_features"])
    bits = int(entry["bits_per_weight"])
    trellis, suh, svh = parts["trellis"], parts["suh"], parts["svh"]
    if int(entry.get("stored_out_features", out_f)) != out_f:
        raise ValueError(f"{MARKER}: {name}: padded output rows are not supported")
    if (trellis.dtype != torch.int16 or tuple(trellis.shape) != (in_f // 16, out_f // 16, 16 * bits)
            or in_f % 128 or out_f % 128 or not 1 <= bits <= 8):
        raise ValueError(f"{MARKER}: {name}: trellis {tuple(trellis.shape)} does not match "
                         f"[{in_f}->{out_f}] K{bits}")
    if (suh.dtype != torch.float16 or svh.dtype != torch.float16
            or tuple(suh.shape) != (in_f,) or tuple(svh.shape) != (out_f,)):
        raise ValueError(f"{MARKER}: {name}: suh/svh geometry or dtype differs")
    return bits


@torch.no_grad()
def reconstruct_bf16(entry: dict[str, Any], parts: dict[str, torch.Tensor], name: str,
                     device: str | torch.device = "cpu", dither_seed: int | None = None,
                     out_device: str | torch.device = "cpu") -> torch.Tensor:
    """BF16 [out_features, in_features] weight for one EXL3 record (the layout of K4's .weight)."""
    validate_record(entry, parts, name)
    device = torch.device(device)
    in_f, out_f = int(entry["in_features"]), int(entry["out_features"])
    trellis = parts["trellis"].to(device)
    suh = parts["suh"].to(device)
    svh = parts["svh"].to(device)
    out = torch.empty((out_f, in_f), dtype=torch.bfloat16, device=out_device)
    gen = _dither_generator(dither_seed, name) if dither_seed is not None else None
    step = column_chunk(in_f)
    for c0 in range(0, out_f, step):
        c1 = min(out_f, c0 + step)
        w = weff_fp64_block(trellis[:, c0 // 16:c1 // 16], suh, svh[c0:c1])
        if not bool(torch.isfinite(w).all()):
            raise ValueError(f"{MARKER}: {name}: non-finite reconstruction")
        if gen is not None:
            w = _dither(w, gen)
        tiny = (w != 0) & (w.abs() < 2.0 ** -126)
        if bool(tiny.any()):
            raise ValueError(f"{MARKER}: {name}: values below the BF16 normal range")
        out[c0:c1].copy_(round_bf16(w).t())
        del w
    return out


def tensor_sha256(t: torch.Tensor) -> str:
    return hashlib.sha256(t.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()).hexdigest()


# --------------------------------------------------------------------------------------------
# Loader hook: wraps the weight iterator of Glm5NextForCausalLM.load_weights and Glm5NextMTP.load_weights
# --------------------------------------------------------------------------------------------
def _layer_of(owner: str) -> int | None:
    parts = owner.split(".")
    for i in range(len(parts) - 1):
        if parts[i] == "layers" and parts[i + 1].isdigit():
            return int(parts[i + 1])
    return None


def _decode_device() -> torch.device:
    choice = os.environ.get("LOCAL_EXL3_DEQUANT_DEVICE", "").strip().lower()
    if choice not in ("", "cuda", "cpu"):
        raise ValueError("LOCAL_EXL3_DEQUANT_DEVICE must be unset, 'cuda' or 'cpu'")
    if choice == "cpu" or not torch.cuda.is_available():
        if choice == "cuda":
            raise RuntimeError("LOCAL_EXL3_DEQUANT_DEVICE=cuda but CUDA is not available")
        return torch.device("cpu")
    return torch.device("cuda", torch.cuda.current_device())


def _dither_seed() -> int | None:
    value = os.environ.get("LOCAL_EXL3_DEQUANT_DITHER_SEED", "").strip()
    return int(value) if value else None


def dequant_weights(weights: Iterable[tuple], quant_config: Any, config: Any, *,
                    spec: bool) -> Iterator[tuple]:
    """Yield the checkpoint stream with each non-expert EXL3 record replaced by `<owner>.weight` BF16.

    spec=False (target model): rebuild owners outside the MTP layers; spec=True (native MTP head):
    only owners in layers >= num_hidden_layers. The other side's raw tensors pass through untouched
    (each loader already skips them). Everything else, including 3-tuples, passes through as is.
    """
    storage = getattr(quant_config, "dequant_storage", None)
    if not mode() or not storage:
        yield from weights
        return
    num_hidden = int(config.num_hidden_layers)
    device, seed = _decode_device(), _dither_seed()
    log = _logger()
    if seed is not None:
        log.warning("%s: DITHER ARM (noise A/B): seed %d adds U(+-1/2) BF16-ulp noise before rounding",
                    MARKER, seed)
    pending: dict[str, dict[str, torch.Tensor]] = {}
    done, started = 0, time.monotonic()
    for item in weights:
        owner, _, field = item[0].rpartition(".")
        if field in _FIELDS:
            entry = dequant_entry(quant_config, owner)
            layer = _layer_of(owner)
            in_spec = layer is not None and layer >= num_hidden
            if entry is not None and in_spec == spec:
                parts = pending.setdefault(owner, {})
                parts[field] = item[1]
                need = {key.rpartition(".")[2] for key in entry["stored_tensors"]}
                if need <= parts.keys():
                    del pending[owner]
                    name = canonical_name(quant_config, entry)
                    weight = reconstruct_bf16(entry, parts, name, device=device, dither_seed=seed)
                    if name in HASHED_OWNERS:
                        log.warning("%s: sha256 %s %s %s", MARKER, name, tuple(weight.shape),
                                    tensor_sha256(weight))
                    done += 1
                    yield owner + ".weight", weight
                continue
        yield item
    if pending:
        raise RuntimeError(f"{MARKER}: incomplete EXL3 records at end of checkpoint: "
                           f"{sorted(pending)[:8]}")
    log.warning("%s: rebuilt %d %s matrices to BF16 on %s in %.1f s", MARKER, done,
                "MTP" if spec else "target", device, time.monotonic() - started)
