"""Pure-numpy core of the glm53_capture plugin: no torch, no vLLM.

Shared by the in-server hook (`__init__.py`) and the host driver (`capture.py`),
so the registry format, token hash, row arithmetic and file layout are defined
in exactly one place.

Conventions
-----------
* Token hash: SHA-256 of the prompt token ids as little-endian int32 bytes
  (the same "raw" hash the old glm53_kld plugin recorded).
* Row r of a window is the log-softmax of the logits after tokens[0..r]
  inclusive; it predicts tokens[r+1].  Valid rows are 0 .. n_tokens-2.
* A registry entry is any JSON object {window_id, tokens, rows} (plus optional
  set, tokens_sha256, meta).  `rows` is a list of ints, "all",
  {"start": a, "stop": b} (half-open) or {"last": k}.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

import numpy as np

VOCAB_DEFAULT = 154880
PRODUCER = "glm53_capture 0.2"
ROW_CONVENTION = ("row r = log-softmax of the logits after tokens[0..r] inclusive; "
                  "it predicts tokens[r+1]")
LOGPROB_METHOD = ("host-side float64 log-softmax of the native-dtype logits row "
                  "(z - logsumexp(z)), stored as float32")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")


# ------------------------------------------------------------------ hashing

def tokens_sha256(tokens) -> str:
    a = np.asarray(tokens)
    if a.ndim != 1:
        raise ValueError(f"tokens must be 1-D, got shape {a.shape}")
    a64 = a.astype(np.int64, copy=False)
    if a64.size and (a64.min() < 0 or a64.max() > np.iinfo(np.int32).max):
        raise ValueError("token id outside int32 range")
    return hashlib.sha256(a64.astype("<i4").tobytes()).hexdigest()


# --------------------------------------------------------------------- rows

def parse_rows(spec, n_tokens: int) -> np.ndarray:
    """Normalise a rows spec to a strictly increasing int32 array in [0, n-2]."""
    last_valid = n_tokens - 2
    if last_valid < 0:
        raise ValueError(f"window of {n_tokens} tokens has no prompt rows")
    if spec == "all":
        rows = np.arange(0, n_tokens - 1, dtype=np.int64)
    elif isinstance(spec, dict):
        if set(spec) == {"last"}:
            k = int(spec["last"])
            rows = np.arange(n_tokens - 1 - k, n_tokens - 1, dtype=np.int64)
        elif set(spec) == {"start", "stop"}:
            rows = np.arange(int(spec["start"]), int(spec["stop"]), dtype=np.int64)
        else:
            raise ValueError(f"rows dict must be {{start, stop}} or {{last}}, got {sorted(spec)}")
    elif isinstance(spec, (list, tuple, np.ndarray)):
        rows = np.asarray(spec, dtype=np.int64)
    else:
        raise ValueError(f"unsupported rows spec {type(spec).__name__}")
    if rows.ndim != 1 or rows.size == 0:
        raise ValueError("rows must be a non-empty 1-D list")
    if np.any(np.diff(rows) <= 0):
        raise ValueError("rows must be strictly increasing (sorted, no duplicates)")
    if rows[0] < 0 or rows[-1] > last_valid:
        raise ValueError(f"rows must lie in [0, {last_valid}] for {n_tokens} tokens; "
                         f"got [{rows[0]}, {rows[-1]}]")
    return rows.astype(np.int32)


def request_prompt_rows(qs: int, qe: int, computed: int, num_sched: int,
                        prompt_len: int):
    """Batch rows holding this request's prompt logits in this step.

    Mirrors vllm/v1/worker/gpu/sample/prompt_logprob.py:91-108 exactly:
    the request's rows are query_start_loc[i] .. query_start_loc[i+1], minus the
    last one when this is the final prompt chunk (that row predicts the first
    *output* token, not a prompt token).  Batch row qs is window row `computed`.

    Returns (b_lo, b_hi, r_lo, is_final): batch rows [b_lo, b_hi) are window
    rows r_lo .. r_lo + (b_hi - b_lo) - 1.
    """
    is_chunked = computed + num_sched < prompt_len
    b_hi = qe if is_chunked else qe - 1
    return qs, b_hi, computed, (not is_chunked)


def runs_for_call(c0: int, m: int, b_lo: int, b_hi: int, r_lo: int,
                  slot_of_row: np.ndarray):
    """Contiguous pieces of one logits_fn call that land in the dump.

    The call covers batch rows [c0, c0+m) (vLLM calls logits_fn on 1024-row
    slices of hidden_states[:num_tokens], i.e. the whole batch).  Returns a list
    of (local_lo, local_hi, slot_lo): rows [local_lo, local_hi) of the call's
    output go to dump slots slot_lo .. slot_lo + (local_hi - local_lo) - 1.
    """
    lo = max(c0, b_lo)
    hi = min(c0 + m, b_hi)
    if lo >= hi:
        return []
    r0 = r_lo + (lo - b_lo)
    r1 = r0 + (hi - lo)
    if r0 < 0 or r1 > slot_of_row.shape[0]:
        raise IndexError(f"window rows [{r0}, {r1}) outside [0, {slot_of_row.shape[0]})")
    slots = slot_of_row[r0:r1]
    idx = np.flatnonzero(slots >= 0)
    if idx.size == 0:
        return []
    s = slots[idx]
    brk = np.flatnonzero((np.diff(idx) != 1) | (np.diff(s) != 1)) + 1
    starts = np.concatenate(([0], brk))
    ends = np.concatenate((brk, [idx.size]))
    base = lo - c0
    return [(base + int(idx[a]), base + int(idx[b - 1]) + 1, int(s[a]))
            for a, b in zip(starts, ends)]


# ----------------------------------------------------------------- registry

class Entry:
    __slots__ = ("window_id", "set", "n_tokens", "sha", "rows", "path", "meta")

    def __init__(self, window_id, set_, n_tokens, sha, rows, path, meta):
        self.window_id, self.set, self.n_tokens = window_id, set_, n_tokens
        self.sha, self.rows, self.path, self.meta = sha, rows, path, meta

    @property
    def key(self):
        return f"{self.set}/{self.window_id}"


def load_entry(path: str, root: str | None = None, vocab: int = VOCAB_DEFAULT,
               keep_tokens: bool = False):
    """Parse and validate one registry JSON. Returns (Entry, tokens|None)."""
    with open(path) as f:
        d = json.load(f)
    if not isinstance(d, dict):
        raise ValueError("registry entry must be a JSON object {window_id, tokens, rows}")
    for k in ("window_id", "tokens", "rows"):
        if k not in d:
            raise ValueError(f"missing key {k!r}")
    wid = str(d["window_id"])
    if not _ID_RE.match(wid):
        raise ValueError(f"window_id {wid!r} is not a safe file name")
    set_ = d.get("set")
    if set_ is None:
        rel = os.path.relpath(path, root) if root else os.path.basename(path)
        parts = rel.split(os.sep)
        set_ = parts[0] if len(parts) > 1 else "default"
    set_ = str(set_)
    if not _ID_RE.match(set_):
        raise ValueError(f"set {set_!r} is not a safe directory name")
    toks = np.asarray(d["tokens"], dtype=np.int64)
    if toks.ndim != 1 or toks.size < 2:
        raise ValueError("tokens must be a list of at least 2 ids")
    if toks.min() < 0 or toks.max() >= vocab:
        raise ValueError(f"token ids must lie in [0, {vocab})")
    sha = tokens_sha256(toks)
    if d.get("tokens_sha256") not in (None, sha):
        raise ValueError(f"tokens_sha256 {d['tokens_sha256']} != recomputed {sha}")
    rows = parse_rows(d["rows"], int(toks.size))
    e = Entry(wid, set_, int(toks.size), sha, rows, path, d.get("meta") or {})
    return e, (toks if keep_tokens else None)


def registry_files(root: str):
    out = []
    for dp, dns, fns in os.walk(root):
        dns.sort()
        for fn in sorted(fns):
            if fn.endswith(".json") and not fn.startswith("."):
                out.append(os.path.join(dp, fn))
    return out


def registry_signature(root: str) -> str:
    """Digest of (relative path, size, mtime_ns) of every entry file."""
    h = hashlib.sha256()
    for p in registry_files(root):
        st = os.stat(p)
        h.update(f"{os.path.relpath(p, root)}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


class Registry:
    def __init__(self, root: str, vocab: int = VOCAB_DEFAULT):
        self.root, self.vocab = root, vocab
        self.signature = None
        self.by_key: dict[tuple[int, str], Entry] = {}
        self.lengths: set[int] = set()
        self.errors: list[str] = []

    def maybe_reload(self) -> bool:
        sig = registry_signature(self.root)
        if sig == self.signature:
            return False
        self.load(sig)
        return True

    def load(self, sig: str | None = None):
        by_key, names, errors = {}, {}, []
        for p in registry_files(self.root):
            try:
                e, _ = load_entry(p, self.root, self.vocab)
            except Exception as exc:  # noqa: BLE001 - every bad file is reported
                errors.append(f"{os.path.relpath(p, self.root)}: {exc}")
                continue
            k = (e.n_tokens, e.sha)
            if k in by_key:
                errors.append(f"{e.key}: same tokens as {by_key[k].key}; skipped")
                continue
            if e.key in names:
                errors.append(f"{e.key}: duplicate set/window_id; skipped")
                continue
            by_key[k] = e
            names[e.key] = e
        self.by_key, self.errors = by_key, errors
        self.lengths = {k[0] for k in by_key}
        self.signature = sig or registry_signature(self.root)

    def status(self) -> dict:
        return {
            "signature": self.signature,
            "n_entries": len(self.by_key),
            "entries": {e.key: {"n_tokens": e.n_tokens, "tokens_sha256": e.sha,
                                "n_rows": int(e.rows.size)}
                        for e in sorted(self.by_key.values(), key=lambda x: x.key)},
            "errors": self.errors,
        }


# ------------------------------------------------------------- safetensors

def build_header(n_rows: int, vocab: int, meta: dict) -> tuple[bytes, int]:
    """Safetensors header for logprobs F32 [n_rows, vocab], rows I32 [n_rows],
    tokens_sha256 U8 [32].  Returns (header bytes incl. 8-byte length, data offset).
    The header is space-padded so tensor data starts 8-byte aligned."""
    a = n_rows * vocab * 4
    b = a + n_rows * 4
    c = b + 32
    body = {
        "__metadata__": {k: str(v) for k, v in meta.items()},
        "logprobs": {"dtype": "F32", "shape": [n_rows, vocab], "data_offsets": [0, a]},
        "rows": {"dtype": "I32", "shape": [n_rows], "data_offsets": [a, b]},
        "tokens_sha256": {"dtype": "U8", "shape": [32], "data_offsets": [b, c]},
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    raw += b" " * ((-(8 + len(raw))) % 8)
    return len(raw).to_bytes(8, "little") + raw, 8 + len(raw)


def data_bytes(n_rows: int, vocab: int) -> int:
    return n_rows * vocab * 4 + n_rows * 4 + 32


_ST_DT = {"F32": np.float32, "I32": np.int32, "U8": np.uint8, "F16": np.float16,
          "U32": np.uint32, "I64": np.int64}


def read_safetensors(path: str, mmap: bool = True):
    """Minimal reader (numpy only). Returns (tensors dict, metadata dict)."""
    with open(path, "rb") as f:
        n = int.from_bytes(f.read(8), "little")
        hdr = json.loads(f.read(n))
    base = 8 + n
    meta = hdr.pop("__metadata__", {}) or {}
    out = {}
    for k, v in hdr.items():
        s, e = v["data_offsets"]
        dt = np.dtype(_ST_DT[v["dtype"]])
        shape = tuple(v["shape"])
        cnt = (e - s) // dt.itemsize
        if mmap:
            arr = np.memmap(path, dtype=dt, mode="r", offset=base + s, shape=(cnt,))
        else:
            arr = np.fromfile(path, dtype=dt, count=cnt, offset=base + s)
        out[k] = arr.reshape(shape)
    return out, meta


class Dump:
    """One window's output file, filled row-slot by row-slot."""

    def __init__(self, out_dir: str, entry: Entry, vocab: int, extra_meta: dict):
        set_dir = os.path.join(out_dir, entry.set)
        os.makedirs(set_dir, exist_ok=True)
        self.path = os.path.join(set_dir, f"{entry.window_id}.safetensors")
        self.tmp = self.path + ".partial"
        if os.path.exists(self.path):
            raise FileExistsError(f"{self.path} already exists in staging; the driver "
                                  "must move or delete it before re-capturing")
        n_rows = int(entry.rows.size)
        meta = {"window_id": entry.window_id, "set": entry.set,
                "n_tokens": entry.n_tokens, "tokens_sha256": entry.sha,
                "n_rows": n_rows, "rows_first": int(entry.rows[0]),
                "rows_last": int(entry.rows[-1]), "row_convention": ROW_CONVENTION,
                "logprob_method": LOGPROB_METHOD, "producer": PRODUCER, **extra_meta}
        hdr, off = build_header(n_rows, vocab, meta)
        with open(self.tmp, "wb") as f:
            f.write(hdr)
            f.truncate(off + data_bytes(n_rows, vocab))
            f.seek(off + n_rows * vocab * 4)
            f.write(entry.rows.astype("<i4").tobytes())
            f.write(bytes.fromhex(entry.sha))
        self.data_offset = off
        self.n_rows, self.vocab = n_rows, vocab
        self.mm = np.memmap(self.tmp, dtype=np.float32, mode="r+", offset=off,
                            shape=(n_rows, vocab))
        self.slot_of_row = np.full(entry.n_tokens - 1, -1, dtype=np.int32)
        self.slot_of_row[entry.rows] = np.arange(n_rows, dtype=np.int32)
        self.covered = np.zeros(n_rows, dtype=bool)
        self.writes = np.zeros(n_rows, dtype=np.int32)

    def write(self, slot_lo: int, arr: np.ndarray):
        k = arr.shape[0]
        self.mm[slot_lo:slot_lo + k] = arr
        self.covered[slot_lo:slot_lo + k] = True
        self.writes[slot_lo:slot_lo + k] += 1

    def reset(self):
        self.covered[:] = False
        self.writes[:] = 0

    def close(self, complete: bool) -> str:
        self.mm.flush()
        del self.mm
        if complete:
            os.replace(self.tmp, self.path)
            return self.path
        return self.tmp


def write_json_atomic(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)
