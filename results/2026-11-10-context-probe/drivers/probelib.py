"""Shared definitions for the context probe (../PROTOCOL-DRAFT.md). Standard library only.

Reuses, read-only, the K3.25 comparison's Stage 0 client (nonce scheme and nonce line) after the same hash-prefix
check the v4 and endurance runs make; no bytecode is written into that folder. Nothing here retries: an error is
recorded on the request and returned to the caller.

Request settings, identical on every arm: thinking on, temperature 1.0, top_p 0.95, top_k -1 (sent explicitly:
CuteAFD is greedy without them), a distinct seed per request, chat_template_kwargs clear_thinking=false (so a
history turn re-renders its reasoning, as the engine generated it).
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.dont_write_bytecode = True

RUN = Path(__file__).resolve().parent.parent
ITEMS = RUN / "items"
STAGE0 = Path("<run>/stage0")
DRIVERS0 = STAGE0 / "drivers"
K325_CLIENT_SHA256_PREFIX = "232f9668"
BASE_URL = "http://127.0.0.1:8001"
KEY_FILE = "<secrets>/bench-api-key"

TEMPERATURE, TOP_P, TOP_K = 1.0, 0.95, -1
TEMPLATE_KWARGS = {"enable_thinking": True, "clear_thinking": False}
SALT = "CONTEXT-PROBE-2026-11-10"
# Request seeds. No overlap with earlier runs (730M-885M) or harness seeds (2000 + pass). The same request has the
# same seed (and nonce) on every arm, so arms are paired by item and seed; repeats differ by `rep`.
SEED_BASE = {"single": 900_000_000, "turns": 910_000_000, "turncheck": 920_000_000, "depth": 930_000_000}
FAMILY_INDEX = {"ledger": 0, "join": 1, "trace": 2}
LENGTH_INDEX = {"4k": 0, "16k": 1, "64k": 2, "128k": 3}


def seed_for(kind: str, rep: int, family: str, index: int, length: str, turn: int = 0) -> int:
    """64 seed slots per (item, length): turn 0..63. rep moves the whole block by 1,000,000."""
    assert 0 <= turn < 64 and 0 <= index < 1000 and 0 <= rep < 10
    ordinal = (FAMILY_INDEX[family] * 1000 + index) * 4 + LENGTH_INDEX[length]
    return SEED_BASE[kind] + rep * 1_000_000 + ordinal * 64 + turn


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_json_atomic(path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")
    os.replace(tmp, path)


class JsonlWriter:
    """Thread-safe append-only JSONL file, flushed per line (a crash loses at most the line being written)."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "a", buffering=1)
        self._lock = threading.Lock()

    def write(self, obj: dict) -> None:
        line = json.dumps(obj, separators=(",", ":"))
        with self._lock:
            self._f.write(line + "\n")
            self._f.flush()

    def close(self) -> None:
        with self._lock:
            self._f.close()


def read_jsonl(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def stage0_client():
    """The K3.25 Stage 0 client module (nonce_for, with_nonce, gpu_snapshot), after the hash-prefix check."""
    if not sha256_file(DRIVERS0 / "client.py").startswith(K325_CLIENT_SHA256_PREFIX):
        sys.exit("reused Stage 0 client.py differs from the one the K3.25 receipts recorded")
    if str(DRIVERS0) not in sys.path:
        sys.path.insert(0, str(DRIVERS0))
    import client  # noqa: E402
    return client


def read_key(path):
    if not path:
        return None
    return Path(path).read_text().strip() or None


def headers(key) -> dict:
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def get_json(url: str, key=None, timeout=60):
    req = urllib.request.Request(url, headers=headers(key))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def post_json(url: str, payload: dict, key=None, timeout=1800.0):
    """(HTTP status, raw body bytes, seconds). An HTTP error returns its status and the head of its body."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers=headers(key))
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:2000], time.perf_counter() - t0


def models_doc(base: str, key=None) -> dict:
    return get_json(base.rstrip("/") + "/v1/models", key)


def chat_body(model, messages, max_tokens, seed, stream=True) -> dict:
    body = {"model": model, "messages": messages, "max_tokens": int(max_tokens), "temperature": TEMPERATURE,
            "top_p": TOP_P, "top_k": TOP_K, "seed": int(seed), "stream": stream,
            "chat_template_kwargs": dict(TEMPLATE_KWARGS)}
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def classify_error(e: BaseException) -> str:
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(e, (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, http.client.RemoteDisconnected)):
        return "connection"
    return "exception"


def stream_chat(base: str, body: dict, *, key=None, read_timeout=3600.0,
                stop_event: threading.Event | None = None) -> dict:
    """One streaming POST /v1/chat/completions. Never raises; returns a record with the reply text.

    status: "ok" (HTTP 200 and a finish reason), "cancelled" (stop_event), "error" (error_kind: http, timeout,
    connection, stream, incomplete, exception). The engine's whole `usage` object is kept (v5 reports the loop
    abort as finish_reason=length with usage.finish_detail="repetition", and the cache source in
    usage.prefix_cache_source). Times: wall_start (epoch s), ttft_s / dur_s (perf_counter differences).
    """
    u = urlparse(base)
    rec = {"status": None, "error_kind": None, "error": None, "http_status": None, "finish_reason": None,
           "usage": None, "chunks": 0, "ttft_s": None, "dur_s": None}
    content, reasoning = [], []
    t_first = t_last = None
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=read_timeout)
    rec["wall_start"] = time.time()
    t0 = time.perf_counter()
    try:
        conn.request("POST", (u.path.rstrip("/") or "") + "/v1/chat/completions", body=json.dumps(body),
                     headers=headers(key))
        resp = conn.getresponse()
        rec["http_status"] = resp.status
        if resp.status != 200:
            rec["status"], rec["error_kind"] = "error", "http"
            rec["error"] = f"HTTP {resp.status}: {resp.read()[:500]!r}"
            return rec
        for raw in resp:
            line = raw.strip()
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            ev = json.loads(data)
            if ev.get("error"):
                rec["status"], rec["error_kind"] = "error", "stream"
                rec["error"] = f"stream error: {json.dumps(ev['error'])[:500]}"
                break
            if ev.get("usage"):
                rec["usage"] = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                txt = d.get("content") or ""
                rs = d.get("reasoning_content") or d.get("reasoning") or ""
                if txt or rs or d.get("tool_calls"):
                    now = time.perf_counter()
                    t_first = t_first or now
                    t_last = now
                    rec["chunks"] += 1
                    content.append(txt)
                    reasoning.append(rs)
                if ch.get("finish_reason"):
                    rec["finish_reason"] = ch["finish_reason"]
            if stop_event is not None and stop_event.is_set():
                rec["status"], rec["error"] = "cancelled", "stopped by driver"
                break
    except Exception as e:  # recorded, never hidden
        rec["status"], rec["error_kind"], rec["error"] = "error", classify_error(e), repr(e)[:500]
    finally:  # every exit path closes the socket
        try:
            if conn.sock is not None:
                conn.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()
        t_end = time.perf_counter()
        rec["dur_s"] = round(t_end - t0, 4)
        if t_first is not None:
            rec["ttft_s"] = round(t_first - t0, 4)
        if rec["status"] is None:
            if rec["finish_reason"]:
                rec["status"] = "ok"
            else:
                rec["status"], rec["error_kind"] = "error", "incomplete"
                rec["error"] = rec["error"] or "stream ended without a finish reason"
        u2 = rec["usage"] or {}
        rec["prompt_tokens"] = u2.get("prompt_tokens")
        rec["completion_tokens"] = u2.get("completion_tokens")
        rec["reasoning_tokens"] = (u2.get("completion_tokens_details") or {}).get("reasoning_tokens")
        rec["cached_tokens"] = (u2.get("prompt_tokens_details") or {}).get("cached_tokens",
                                                                          u2.get("prompt_cache_hit_tokens"))
        rec["finish_detail"] = u2.get("finish_detail")
        rec["prefix_cache_source"] = u2.get("prefix_cache_source")
        ct = rec["completion_tokens"]
        if ct and ct > 1 and t_first is not None and t_last is not None and t_last > t_first:
            rec["decode_tok_s"] = round((ct - 1) / (t_last - t_first), 3)
        else:
            rec["decode_tok_s"] = None
        rec["content"], rec["reasoning"] = "".join(content), "".join(reasoning)
    return rec


def finish_class(rec: dict) -> str:
    """stop | cap (length, no detail) | repetition (v5 loop abort) | error | other:<reason>."""
    if rec.get("status") != "ok":
        return "error"
    fr, fd = rec.get("finish_reason"), rec.get("finish_detail")
    if fr == "stop":
        return "stop"
    if fr == "length":
        return "repetition" if fd == "repetition" else "cap"
    return f"other:{fr}"


# ---- recorded rows: full-vocabulary dumps and top-k comparisons ----

def dump_index(dump_dir) -> dict:
    """{predicted position: file} from an engine row dump's manifest.jsonl ({} when there is none)."""
    d = Path(dump_dir) if dump_dir else None
    if d is None or not (d / "manifest.jsonl").exists():
        return {}
    return {int(m["position"]): d / m["file"] for m in map(json.loads, (d / "manifest.jsonl").read_text().splitlines())}


def read_logprob_row(path):
    """One dumped row: a safetensors file holding a single little-endian f32 `log_probs[vocab]` tensor."""
    import struct
    import numpy as np
    raw = Path(path).read_bytes()
    (n,) = struct.unpack("<Q", raw[:8])
    meta = json.loads(raw[8:8 + n])["log_probs"]
    if meta["dtype"] != "F32":
        raise ValueError(f"{path}: dtype {meta['dtype']}")
    lo, hi = meta["data_offsets"]
    return np.frombuffer(raw, dtype="<f4", count=(hi - lo) // 4, offset=8 + n + lo).astype("float64")


def exact_kl(file_a, file_b) -> float:
    """KL(a || b) in nats over the full vocabulary, from two dumped rows."""
    import numpy as np
    la, lb = read_logprob_row(file_a), read_logprob_row(file_b)
    pa = np.exp(la)
    keep = pa > 0
    return float(np.sum(pa[keep] * (la[keep] - lb[keep])))


def lumped_kl(top_a, top_b):
    """A lower bound on KL(a || b), nats: the ids present in both top-k lists keep their own bins and everything
    else is lumped into one tail bin (coarse-graining never raises KL). Returns (kl, ids kept)."""
    import math
    lb = {int(i): lp for i, lp in top_b}
    pa_sum = pb_sum = kl = 0.0
    kept = 0
    for i, la in top_a:
        if int(i) not in lb:
            continue
        kept += 1
        pa, pb = math.exp(la), math.exp(lb[int(i)])
        pa_sum, pb_sum = pa_sum + pa, pb_sum + pb
        kl += pa * (la - lb[int(i)])
    ta, tb = max(1.0 - pa_sum, 0.0), max(1.0 - pb_sum, 1e-12)
    if ta > 1e-12:
        kl += ta * math.log(ta / tb)
    return max(kl, 0.0), kept
