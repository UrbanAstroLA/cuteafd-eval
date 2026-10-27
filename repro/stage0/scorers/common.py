"""Shared I/O, numerics and statistics for the Stage 0 scorers (P-A, P-B, Q2).

Nothing here talks to a server or a GPU. Every reduction is float64 on the host.

Row convention used everywhere in this folder
---------------------------------------------
A *row* r of a window is the engine distribution after tokens[0..r] (inclusive),
i.e. the row that predicts tokens[r + 1]. This is the convention of
`glmf-teacher-kl.py` (plan "positions", docstring lines 28-30), of our vLLM plugin
registry ("rows"), and of the P-A teacher files (row i scores token i+1,
`<runs>/kld/PLAN.md` §2). tpurtell's fidelity reference instead indexes by the
*predicted position* p = r + 1 (`reference.rs:83-96`); the P-B scorer converts.

Engine row files accepted (one window per file, `<window_id>.safetensors`)
------------------------------------------------------------------------
* values tensor: `logprobs` (our vLLM plugin) or `logits` (`glmf-teacher-kl.py`
  lines 159-164, and the legacy P-A plugin files), shape [n_rows, V],
  dtype F32, BF16 or F16. Raw logits and log-probabilities are both fine:
  every scorer log-softmaxes the row again in float64.
* row-index tensor: `rows` (our plugin) or `positions` (`glmf-teacher-kl.py`,
  I32, which holds the *plan rows* r, not r + 1; docstring lines 32-33).
  A file without a row tensor is accepted only when its row count equals the
  expected row count; rows are then 0..n-1 in order (legacy P-A layout).
* CuteAFD CLI dump leaves (`manifest.jsonl` + `row-NNNNNNNN.safetensors`, one
  F32 `log_probs` [V] per row; `cuteafd-api/src/openai/probe/rows.rs:59-86`)
  are read by `DumpDirRows`; their `position` is the predicted position, so
  row = position - 1.

Do NOT store log-probabilities as BF16: BF16 has 8 significant bits, so a
log-prob of -10 would carry an error of up to 0.03 nats. Raw BF16 logits are
lossless for vLLM (its head emits BF16), F32 log-probs are lossless for both.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import os
import struct
from dataclasses import dataclass

import numpy as np

VOCAB = 154880

# --------------------------------------------------------------------------
# numerics copied verbatim from <kld>/kld_score.py:58-90
# (copied, not imported, so that importing never writes into that directory;
#  tests/test_scorers.py checks bit-equality against the original)
# --------------------------------------------------------------------------


def log_softmax_f64(z: np.ndarray) -> np.ndarray:
    """Numerically stable log-softmax over the last axis, in float64 (kld_score.py:58-71)."""
    z = np.asarray(z, dtype=np.float64)
    m = z.max(axis=-1, keepdims=True)
    shifted = z - m                       # all entries <= 0, exp cannot overflow
    e = np.exp(shifted)
    lse = np.log(e.sum(axis=-1, keepdims=True))
    shifted -= lse
    return shifted


def kl_rows_f64(zt: np.ndarray, zc: np.ndarray) -> np.ndarray:
    """Per-row KL(P_t || P_c) in nats, float64, full vocabulary (kld_score.py:74-90)."""
    lpt = log_softmax_f64(zt)
    lpc = log_softmax_f64(zc)
    pt = np.exp(lpt)
    diff = lpt - lpc
    contrib = pt * diff
    return contrib.sum(axis=-1)


# --------------------------------------------------------------------------
# small numerics
# --------------------------------------------------------------------------

def kl_from_logprobs(lpa: np.ndarray, lpb: np.ndarray) -> np.ndarray:
    """KL(A || B) per row from already-normalised float64 log-probs.

    Terms with p_a == 0 contribute exactly 0 (guards 0 * (-inf - x) = nan when a
    stored row carries -inf entries)."""
    pa = np.exp(lpa)
    with np.errstate(invalid="ignore"):
        c = pa * (lpa - lpb)
    c = np.where(pa > 0.0, c, 0.0)
    return c.sum(axis=-1)


def js_from_logprobs(lpa: np.ndarray, lpb: np.ndarray) -> np.ndarray:
    """Jensen-Shannon divergence per row (nats): 0.5 KL(A||M) + 0.5 KL(B||M), M=(A+B)/2."""
    lpm = np.logaddexp(lpa, lpb) - math.log(2.0)
    return 0.5 * kl_from_logprobs(lpa, lpm) + 0.5 * kl_from_logprobs(lpb, lpm)


def argmax_lowid(x: np.ndarray) -> np.ndarray:
    """Row argmax, ties to the lower id (np.argmax returns the first maximum).

    Same rule as CuteAFD: probe.rs:466-476 (raw logits, key (Reverse(value), id)) and
    fidelity_rows.rs:178-179 (normalised f64 row, `then_with(|| ib.cmp(ia))`)."""
    return np.argmax(x, axis=-1)


def top3_lowid(lp: np.ndarray) -> np.ndarray:
    """[n, 3] ids of the three largest entries per row, ordered by (-value, id).

    Exact under ties (BF16 teacher logits tie often): rows whose 3rd value is
    shared by more than three entries are resolved by a per-row lexsort."""
    n = lp.shape[0]
    part = np.argpartition(-lp, 3, axis=-1)[:, :4]          # 4 candidates
    v3 = np.partition(lp, -3, axis=-1)[:, -3]               # 3rd largest value
    ge = (lp >= v3[:, None]).sum(axis=-1)                   # entries >= v3
    out = np.empty((n, 3), dtype=np.int64)
    for i in range(n):
        if ge[i] == 3:
            cand = part[i][lp[i, part[i]] >= v3[i]]
        else:
            cand = np.flatnonzero(lp[i] >= v3[i])
        order = np.lexsort((cand, -lp[i, cand]))
        out[i] = cand[order[:3]]
    return out


def tokens_sha256(tokens) -> str:
    """sha256 of the ids as little-endian u32 (glmf-teacher-kl.py:55-57)."""
    return hashlib.sha256(struct.pack(f"<{len(tokens)}I", *[int(t) for t in tokens])).hexdigest()


def sha256_file(path: str, chunk: int = 32 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb", buffering=0) as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------
# safetensors
# --------------------------------------------------------------------------

_DT = {"F64": np.float64, "F32": np.float32, "F16": np.float16, "BF16": np.uint16,
       "I64": np.int64, "I32": np.int32, "I16": np.int16, "U32": np.uint32,
       "U16": np.uint16, "U8": np.uint8, "I8": np.int8}


class SafeTensors:
    """Minimal read-only safetensors reader (memory-mapped; BF16 kept as uint16)."""

    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            if n > (100 << 20):
                raise ValueError(f"{path}: oversized safetensors header")
            header = json.loads(f.read(n))
        self.meta = header.pop("__metadata__", {}) or {}
        self.data_start = 8 + n
        self.tensors = header
        size = os.path.getsize(path)
        for name, t in header.items():
            if t["dtype"] not in _DT:
                raise ValueError(f"{path}: unsupported dtype {t['dtype']} for {name}")
            a, b = t["data_offsets"]
            width = np.dtype(_DT[t["dtype"]]).itemsize
            if b - a != width * int(np.prod(t["shape"], dtype=np.int64)) or self.data_start + b > size:
                raise ValueError(f"{path}: tensor {name} extent does not match its shape")

    def dtype(self, name: str) -> str:
        return self.tensors[name]["dtype"]

    def array(self, name: str) -> np.ndarray:
        t = self.tensors[name]
        a, _ = t["data_offsets"]
        shape = tuple(t["shape"])
        dt = np.dtype(_DT[t["dtype"]]).newbyteorder("<")
        if int(np.prod(shape, dtype=np.int64)) == 0:
            return np.zeros(shape, dtype=dt)
        return np.memmap(self.path, dtype=dt, mode="r", offset=self.data_start + a, shape=shape)


def to_f64(raw: np.ndarray, dtype: str) -> np.ndarray:
    """Decode a raw block (F32/F16/BF16-as-uint16/F64) to float64."""
    raw = np.asarray(raw)
    if dtype == "BF16":
        return (raw.astype(np.uint32) << 16).view(np.float32).astype(np.float64)
    return raw.astype(np.float64)


def write_safetensors(path: str, tensors: list, meta: dict | None = None) -> None:
    """Write [(name, dtype_str, np.ndarray)] as safetensors (used by tests and helpers)."""
    header: dict = {}
    if meta:
        header["__metadata__"] = {k: str(v) for k, v in meta.items()}
    offset, blobs = 0, []
    for name, dt, arr in tensors:
        if dt == "BF16":
            blob = np.ascontiguousarray(arr, dtype=np.uint16).astype("<u2").tobytes()
        else:
            blob = np.ascontiguousarray(arr, dtype=np.dtype(_DT[dt]).newbyteorder("<")).tobytes()
        header[name] = {"dtype": dt, "shape": list(arr.shape), "data_offsets": [offset, offset + len(blob)]}
        offset += len(blob)
        blobs.append(blob)
    text = json.dumps(header, separators=(",", ":")).encode()
    text += b" " * (-(8 + len(text)) % 8)
    tmp = path + ".partial"
    with open(tmp, "wb") as f:
        f.write(struct.pack("<Q", len(text)) + text)
        for b in blobs:
            f.write(b)
    os.replace(tmp, path)


def f32_to_bf16_bits(x: np.ndarray) -> np.ndarray:
    """Round-to-nearest-even F32 -> BF16 bit pattern (uint16). Test helper."""
    u = np.asarray(x, dtype=np.float32).view(np.uint32).astype(np.uint64)
    r = ((u >> 16) & 1) + 0x7FFF
    return ((u + r) >> 16).astype(np.uint16)


# --------------------------------------------------------------------------
# engine rows
# --------------------------------------------------------------------------

class WindowRows:
    """Engine rows of one window from a `<window_id>.safetensors` file.

    `.rows` int64 [n] (row r predicts tokens[r+1]); `.block(i0, i1)` returns the
    float64 values of entries i0..i1 of `.rows` order."""

    def __init__(self, path: str, vocab: int, expected_rows=None):
        st = SafeTensors(path)
        self.path, self.meta, self.layout = path, st.meta, "window-file"
        vname = next((n for n in ("logprobs", "logits") if n in st.tensors), None)
        if vname is None:
            raise ValueError(f"{path}: no 'logprobs' or 'logits' tensor (has {sorted(st.tensors)})")
        self.values_name, self.dtype = vname, st.dtype(vname)
        if self.dtype not in ("F32", "F16", "BF16", "F64"):
            raise ValueError(f"{path}: values dtype {self.dtype} unsupported")
        self.values = st.array(vname)
        if self.values.ndim != 2 or self.values.shape[1] != vocab:
            raise ValueError(f"{path}: values shape {self.values.shape}, expected [n, {vocab}]")
        rname = next((n for n in ("rows", "positions") if n in st.tensors), None)
        if rname is not None:
            self.rows = np.asarray(st.array(rname)).astype(np.int64).reshape(-1)
            self.rows_source = rname
        else:
            if expected_rows is None or len(expected_rows) != self.values.shape[0]:
                raise ValueError(f"{path}: no row-index tensor and row count {self.values.shape[0]} "
                                 f"does not equal the expected {None if expected_rows is None else len(expected_rows)}")
            self.rows = np.asarray(expected_rows, dtype=np.int64)
            self.rows_source = "implied-by-count"
        if len(self.rows) != self.values.shape[0]:
            raise ValueError(f"{path}: {len(self.rows)} row ids for {self.values.shape[0]} rows")
        if len(self.rows) > 1 and not np.all(np.diff(self.rows) > 0):
            raise ValueError(f"{path}: row ids are not strictly increasing")

    def block(self, i0: int, i1: int) -> np.ndarray:
        return to_f64(self.values[i0:i1], self.dtype)

    def take(self, idx: np.ndarray) -> np.ndarray:
        return to_f64(self.values[np.asarray(idx)], self.dtype)


class DumpDirRows:
    """A CuteAFD probe dump leaf: manifest.jsonl + one F32 `log_probs` [V] file per row.

    Layout from cuteafd-api/src/openai/probe/rows.rs:59-86 (file names
    row-%08d.safetensors, header {"log_probs": F32 [V]} padded to 8 bytes,
    manifest line {position, vocab_size, file, tensor, dtype, byte_order});
    validated the way fidelity_rows.rs:164-169 does. `position` is the predicted
    position p, so row = p - 1."""

    def __init__(self, leaf: str, vocab: int):
        self.path, self.meta, self.layout, self.dtype = leaf, {}, "cuteafd-dump", "F32"
        entries = {}
        with open(os.path.join(leaf, "manifest.jsonl")) as f:
            for line in f:
                e = json.loads(line)
                if (e.get("vocab_size") != vocab or e.get("dtype") != "F32" or e.get("byte_order") != "little"
                        or e.get("tensor") != "log_probs"):
                    raise ValueError(f"{leaf}: engine row format mismatch {e}")
                if e["position"] in entries:
                    raise ValueError(f"{leaf}: duplicate dump position {e['position']}")
                if os.path.isabs(e["file"]) or ".." in e["file"].split("/"):
                    raise ValueError(f"{leaf}: unsafe row path {e['file']}")
                entries[e["position"]] = e["file"]
        positions = np.array(sorted(entries), dtype=np.int64)
        self.files = [entries[int(p)] for p in positions]
        self.rows = positions - 1
        self.rows_source = "manifest.jsonl position - 1"
        self.vocab = vocab

    def _row(self, i: int) -> np.ndarray:
        st = SafeTensors(os.path.join(self.path, self.files[i]))
        t = st.tensors.get("log_probs")
        if t is None or t["dtype"] != "F32" or t["shape"] != [self.vocab]:
            raise ValueError(f"{self.path}/{self.files[i]}: row tensor shape/dtype mismatch")
        return np.asarray(st.array("log_probs"), dtype=np.float64)

    def block(self, i0: int, i1: int) -> np.ndarray:
        return np.stack([self._row(i) for i in range(i0, i1)])

    def take(self, idx) -> np.ndarray:
        return np.stack([self._row(int(i)) for i in idx])


def open_rows(src: str, vocab: int, expected_rows=None):
    """`src` is a window file or a CuteAFD dump leaf directory."""
    if os.path.isdir(src):
        return DumpDirRows(src, vocab)
    return WindowRows(src, vocab, expected_rows)


def check_tokens_meta(rows_obj, tokens) -> str | None:
    """Cross-check an engine file's token hash metadata when present.

    `tokens_sha256` (glmf-teacher-kl.py:155) and `token_ids_sha256_raw` (legacy
    P-A plugin; sha256 of the int32 LE bytes == u32 LE bytes for ids >= 0).
    Returns the key checked, or None if the file carries neither. Raises on mismatch."""
    want = tokens_sha256(tokens)
    for key in ("tokens_sha256", "token_ids_sha256_raw"):
        got = rows_obj.meta.get(key)
        if got is not None:
            if got != want:
                raise ValueError(f"{rows_obj.path}: metadata {key}={got} differs from the plan's tokens ({want})")
            return key
    return None


def select_rows(rows_obj, wanted_rows: np.ndarray, exact: bool = True) -> np.ndarray:
    """Indices into rows_obj.rows for `wanted_rows`. exact=True requires equal sets."""
    have = rows_obj.rows
    wanted_rows = np.asarray(wanted_rows, dtype=np.int64)
    if exact and (len(have) != len(wanted_rows) or not np.array_equal(have, wanted_rows)):
        missing = np.setdiff1d(wanted_rows, have)
        extra = np.setdiff1d(have, wanted_rows)
        raise ValueError(f"{rows_obj.path}: engine rows differ from the plan "
                         f"({len(missing)} missing e.g. {missing[:5].tolist()}, {len(extra)} extra e.g. {extra[:5].tolist()})")
    pos = np.searchsorted(have, wanted_rows)
    if np.any(pos >= len(have)) or not np.array_equal(have[np.minimum(pos, len(have) - 1)], wanted_rows):
        raise ValueError(f"{rows_obj.path}: engine rows lack some planned rows")
    return pos


# --------------------------------------------------------------------------
# alignment (off-by-one) detector
# --------------------------------------------------------------------------

def alignment_nll(lp: np.ndarray, tokens: np.ndarray, rows: np.ndarray) -> dict:
    """Mean NLL of the row's distribution at the token it should predict (offset 0 =
    tokens[r+1]) and at its neighbours (offset -1 = tokens[r], +1 = tokens[r+2]).

    A correctly aligned language model is far better at offset 0 (about 1-2 nats
    on real text) than at the neighbours (typically > 8 nats). Returns sums and
    counts so that callers can accumulate over blocks."""
    tokens = np.asarray(tokens, dtype=np.int64)
    out = {}
    for d in (-1, 0, 1):
        t = rows + 1 + d
        ok = (t >= 0) & (t < len(tokens))
        idx = np.flatnonzero(ok)
        vals = -lp[idx, tokens[t[idx]]]
        out[d] = (float(vals.sum()), int(idx.size))
    return out


def alignment_verdict(acc: dict) -> dict:
    """acc: {offset: (sum, count)} -> means and flag. Misaligned when offset 0 is not
    strictly the best of the three by at least 0.5 nat."""
    means = {d: (s / c if c else float("nan")) for d, (s, c) in acc.items()}
    others = [means[d] for d in (-1, 1) if not math.isnan(means[d])]
    ok = (not math.isnan(means[0])) and all(means[0] + 0.5 < o for o in others)
    return {"nll_offset_minus1": means[-1], "nll_offset_0": means[0], "nll_offset_plus1": means[1],
            "aligned": bool(ok)}


def merge_alignment(a: dict, b: dict) -> dict:
    return {d: (a[d][0] + b[d][0], a[d][1] + b[d][1]) for d in (-1, 0, 1)}


# --------------------------------------------------------------------------
# bootstrap
# --------------------------------------------------------------------------

class SplitMix64:
    """Port of cuteafd-bench/src/fidelity.rs:125-140 (SplitMix64 + unbiased index)."""
    M = (1 << 64) - 1

    def __init__(self, seed: int):
        self.s = seed & self.M

    def next(self) -> int:
        self.s = (self.s + 0x9E3779B97F4A7C15) & self.M
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self.M
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self.M
        return z ^ (z >> 31)

    def index(self, n: int) -> int:
        threshold = ((1 << 64) - n) % n          # n.wrapping_neg() % n
        while True:
            x = self.next()
            if x >= threshold:
                return x % n


@functools.lru_cache(maxsize=64)
def _bootstrap_indices_cached(n_clusters: int, iters: int, seed: int, rng: str) -> np.ndarray:
    a = _bootstrap_indices(n_clusters, iters, seed, rng)
    a.setflags(write=False)
    return a


def bootstrap_indices(n_clusters: int, iters: int, seed: int, rng: str = "numpy") -> np.ndarray:
    """Cached: the same (G, iters, seed, rng) always gives the same draw, as a fresh
    generator with that seed would (fidelity.rs:143-154 reseeds on every call)."""
    return _bootstrap_indices_cached(int(n_clusters), int(iters), int(seed), rng)


def _bootstrap_indices(n_clusters: int, iters: int, seed: int, rng: str = "numpy") -> np.ndarray:
    """[iters, n_clusters] cluster indices sampled with replacement.

    rng="numpy": np.random.default_rng(seed).integers, as kld_score.py:159-162.
    rng="splitmix": tpurtell's block_bootstrap draw order (fidelity.rs:143-154):
    replicate by replicate, one index per cluster."""
    if rng == "numpy":
        return np.random.default_rng(seed).integers(0, n_clusters, size=(iters, n_clusters))
    if rng == "splitmix":
        r = SplitMix64(seed)
        return np.array([[r.index(n_clusters) for _ in range(n_clusters)] for _ in range(iters)], dtype=np.int64)
    raise ValueError(rng)


def quantile_linear(x: np.ndarray, q: float) -> float:
    """Linear-interpolation quantile, identical to fidelity.rs:117-123 and np.quantile default."""
    return float(np.quantile(np.asarray(x, dtype=np.float64), q))


def clustered_se(sums: np.ndarray, counts: np.ndarray) -> float | None:
    """fidelity.rs:106-115: cluster-robust SE of a ratio-of-sums mean."""
    if len(sums) < 2:
        return None
    n = counts.sum()
    if n == 0:
        return None
    mean = sums.sum() / n
    g = len(sums)
    resid = ((sums - counts * mean) ** 2).sum()
    return float(math.sqrt(g / (g - 1.0) * resid) / n)


@dataclass
class BootSpec:
    iters: int = 20000
    seed: int = 20260929
    rng: str = "numpy"
    lo: float = 0.025
    hi: float = 0.975


def ratio_summary(num_by_cluster: np.ndarray, den_by_cluster: np.ndarray, idx: np.ndarray | None,
                  spec: BootSpec) -> dict:
    """Point value sum(num)/sum(den) and its cluster-bootstrap interval."""
    num = np.asarray(num_by_cluster, dtype=np.float64)
    den = np.asarray(den_by_cluster, dtype=np.float64)
    tot = den.sum()
    out = {"value": float(num.sum() / tot) if tot > 0 else None, "n": float(tot), "clusters": int((den > 0).sum())}
    if idx is not None and tot > 0 and len(num) >= 2:
        d = den[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            reps = num[idx].sum(axis=1) / d
        reps = reps[d > 0]
        out["ci95"] = [quantile_linear(reps, spec.lo), quantile_linear(reps, spec.hi)]
        out["boot_se"] = float(reps.std(ddof=1))
    else:
        out["ci95"] = None
    return out


def cluster_sums(values: np.ndarray, clusters: np.ndarray, n_clusters: int) -> np.ndarray:
    return np.bincount(clusters, weights=np.asarray(values, dtype=np.float64), minlength=n_clusters)


def summarize_metrics(metrics: dict, clusters: np.ndarray, mask: np.ndarray, spec: BootSpec | None,
                      cluster_names: list | None = None) -> dict:
    """metrics: name -> (numerator per row, denominator per row). Rows outside `mask`
    are dropped. Bootstrap clusters are the clusters that keep >= 1 row."""
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        return {"rows": 0}
    used = np.unique(clusters[mask])
    remap = -np.ones(int(clusters.max()) + 1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    c = remap[clusters[mask]]
    G = len(used)
    idx = bootstrap_indices(G, spec.iters, spec.seed, spec.rng) if (spec is not None and G >= 2) else None
    out = {"rows": int(mask.sum()), "clusters": G}
    for name, (num, den) in metrics.items():
        num_c = cluster_sums(np.asarray(num)[mask], c, G)
        den_c = cluster_sums(np.asarray(den)[mask], c, G)
        s = ratio_summary(num_c, den_c, idx, spec or BootSpec())
        if den_c.sum() > 0:
            s["clustered_se"] = clustered_se(num_c[den_c > 0], den_c[den_c > 0])
        out[name] = s
    return out


def paired_metrics(metrics_a: dict, metrics_b: dict, clusters: np.ndarray, mask: np.ndarray,
                   spec: BootSpec | None) -> dict:
    """Paired bootstrap of B - A over clusters; rows are identical in both arms, so
    each metric's denominator must be identical (checked)."""
    mask = np.asarray(mask, dtype=bool)
    used = np.unique(clusters[mask])
    remap = -np.ones(int(clusters.max()) + 1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    c = remap[clusters[mask]]
    G = len(used)
    idx = bootstrap_indices(G, spec.iters, spec.seed, spec.rng) if (spec is not None and G >= 2) else None
    out = {"rows": int(mask.sum()), "clusters": G, "direction": "B - A"}
    for name in metrics_a:
        na, da = metrics_a[name]
        nb, db = metrics_b[name]
        if not np.array_equal(np.asarray(da)[mask], np.asarray(db)[mask]):
            raise ValueError(f"paired metric {name}: denominators differ between arms")
        den_c = cluster_sums(np.asarray(da)[mask], c, G)
        a_c = cluster_sums(np.asarray(na)[mask], c, G)
        b_c = cluster_sums(np.asarray(nb)[mask], c, G)
        tot = den_c.sum()
        if tot == 0:
            out[name] = None
            continue
        diff = ratio_summary(b_c - a_c, den_c, idx, spec or BootSpec())
        out[name] = {"A": float(a_c.sum() / tot), "B": float(b_c.sum() / tot), "B_minus_A": diff["value"],
                     "ci95": diff["ci95"], "boot_se": diff.get("boot_se"),
                     "clustered_se": clustered_se((b_c - a_c)[den_c > 0], den_c[den_c > 0])}
    return out


def dump_json(path: str, obj) -> None:
    tmp = path + ".partial"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, allow_nan=True)
    os.replace(tmp, path)
