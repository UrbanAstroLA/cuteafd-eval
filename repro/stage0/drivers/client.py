"""Shared streaming client for block_t.py and block_l.py (standard library only).

One request = one streaming POST /v1/chat/completions. Timing uses time.perf_counter() on the client.
Nothing here retries: an error is recorded on the request and returned to the caller.
"""
import hashlib
import http.client
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

STAGE0 = Path(__file__).resolve().parent.parent
PROMPTS = STAGE0 / "prompts"
NONCE_GROUPS = json.loads((PROMPTS / "nonce_groups.json").read_text())["groups"]
NONCE_FMT = json.loads((PROMPTS / "authored" / "wrappers.json").read_text())["nonce_line"]
# author's generation_config.json (K3.25-v1 0490d2f7): temperature 1.0, top_p 0.95
DEFAULT_TEMPERATURE = 1.0
DEFAULT_TOP_P = 0.95


def read_key(path):
    if not path:
        return None
    return Path(path).read_text().strip() or None


def headers(key):
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def model_id(base, key):
    req = urllib.request.Request(base.rstrip("/") + "/v1/models", headers=headers(key))
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"][0]["id"]


def nonce_for(salt, seed):
    return "".join(NONCE_GROUPS[int(hashlib.sha256(f"{salt}:{seed}:{k}".encode()).hexdigest(), 16)
                                % len(NONCE_GROUPS)] for k in range(4))


def with_nonce(messages, nonce):
    msgs = [dict(m) for m in messages]
    msgs[0]["content"] = NONCE_FMT.replace("{nonce}", nonce) + "\n" + msgs[0]["content"]
    return msgs


def gpu_snapshot():
    """Best-effort record of GPU memory/utilization and compute apps (read-only nvidia-smi queries)."""
    out = {}
    for name, args in (("gpus", ["--query-gpu=index,memory.used,memory.total,utilization.gpu",
                                 "--format=csv,noheader"]),
                       ("compute_apps", ["--query-compute-apps=pid,process_name,used_memory",
                                         "--format=csv,noheader"])):
        try:
            p = subprocess.run(["nvidia-smi", *args], capture_output=True, text=True, timeout=20)
            out[name] = p.stdout.strip().splitlines()
        except Exception as e:  # recorded, never fatal
            out[name] = f"unavailable: {e!r}"
    out["note"] = "nvidia-smi --query-compute-apps misses graphics clients; check the full nvidia-smi output"
    return out


def stream_chat(base, key, body, keep_text=False, keep_chunks=False, read_timeout=1800):
    """Send one streaming chat request. Returns a record (never raises).

    Record fields: t_send, t_first, t_last (perf_counter seconds), finish_reason, usage, chunks,
    content_chars, reasoning_chars, http_status, error; with keep_text: content, reasoning;
    with keep_chunks: chunk_t (s since t_send), chunk_chars, chunk_kind ("r" reasoning, "c" content).
    """
    u = urlparse(base)
    rec = {"finish_reason": None, "usage": None, "chunks": 0, "content_chars": 0, "reasoning_chars": 0,
           "http_status": None, "error": None, "t_first": None, "t_last": None}
    content, reasoning = [], []
    ct, cc, ck = [], [], []
    tail, think_close = "", False
    conn = (http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection)(
        u.hostname, u.port, timeout=read_timeout)
    rec["t_send"] = t0 = time.perf_counter()
    rec["wall_send"] = time.time()
    try:
        conn.request("POST", (u.path.rstrip("/") or "") + "/v1/chat/completions", body=json.dumps(body),
                     headers=headers(key))
        resp = conn.getresponse()
        rec["http_status"] = resp.status
        if resp.status != 200:
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
                rec["error"] = f"stream error: {json.dumps(ev['error'])[:500]}"
                break
            if ev.get("usage"):
                rec["usage"] = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                txt = d.get("content") or ""
                rs = d.get("reasoning_content") or d.get("reasoning") or ""
                if txt or rs:
                    now = time.perf_counter()
                    rec["t_first"] = rec["t_first"] or now
                    rec["t_last"] = now
                    rec["chunks"] += 1
                    rec["content_chars"] += len(txt)
                    rec["reasoning_chars"] += len(rs)
                    if txt:
                        think_close = think_close or "</think>" in tail + txt
                        tail = (tail + txt)[-8:]
                    if keep_text:
                        if rs:
                            reasoning.append(rs)
                        if txt:
                            content.append(txt)
                    if keep_chunks:
                        if rs:
                            ct.append(round(now - t0, 4))
                            cc.append(len(rs))
                            ck.append("r")
                        if txt:
                            ct.append(round(now - t0, 4))
                            cc.append(len(txt))
                            ck.append("c")
                if ch.get("finish_reason"):
                    rec["finish_reason"] = ch["finish_reason"]
                    if ch.get("stop_reason") is not None:
                        rec["stop_reason"] = ch.get("stop_reason")
    except Exception as e:  # recorded, never hidden
        rec["error"] = repr(e)
    finally:  # runs on every exit path, including the early return on a non-200 status
        conn.close()
        rec["t_end"] = time.perf_counter()
        rec["content_has_think_close"] = think_close
        if keep_text:
            rec["content"], rec["reasoning"] = "".join(content), "".join(reasoning)
        if keep_chunks:
            rec["chunk_t"], rec["chunk_chars"], rec["chunk_kind"] = ct, cc, "".join(ck)
    return rec


def write_atomic(path, obj):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")
    os.replace(tmp, path)
