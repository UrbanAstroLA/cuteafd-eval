#!/usr/bin/env python3
"""F2 (FOLLOWUPS.md): does vLLM v0.9.2 reuse its prefix cache on an identical repeated prompt?

For each length in 1,024 / 4,352 / 8,192 / 8,704 / 17,408 tokens: an exact-length token prompt (from a public-domain
PG-19 book, tokenized by the server's own /tokenize), sent 3 times in sequence to /v1/completions with max_tokens 16.
Records usage cached tokens, TTFT (streamed), and the /metrics prefix-cache counters before and after each request.
Standard library only.  Usage: f2_prefix_cache.py --text BOOK.txt --out f2.json [--base-url http://127.0.0.1:8001]"""
import argparse
import json
import re
import time
import urllib.request

LENGTHS = [1024, 4352, 8192, 8704, 17408]


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode()


def post(url, body, stream=False):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=3600)


def metrics(base):
    out = {}
    for line in get(base + "/metrics").splitlines():
        if line.startswith("#"):
            continue
        m = re.match(r"^(vllm:[a-z_]*prefix_cache[a-z_]*)(\{[^}]*\})?\s+([0-9.eE+-]+)$", line)
        if m:
            out[m.group(1)] = out.get(m.group(1), 0.0) + float(m.group(3))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    model = json.loads(get(base + "/v1/models"))["data"][0]["id"]
    text = open(a.text, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    ids = json.loads(post(base + "/tokenize", {"model": model, "prompt": text[:400000],
                                                "add_special_tokens": False}).read())["tokens"]
    report = {"model": model, "lengths": LENGTHS, "source_chars": 400000, "runs": [],
              "metrics_names": sorted(metrics(base))}
    for n in LENGTHS:
        assert len(ids) >= n, (len(ids), n)
        prompt = ids[:n]
        for rep in range(3):
            before = metrics(base)
            t0 = time.perf_counter(); t_first = None; usage = None
            resp = post(base + "/v1/completions", {"model": model, "prompt": prompt, "max_tokens": 16,
                                                    "temperature": 0, "stream": True,
                                                    "stream_options": {"include_usage": True}})
            for raw in resp:
                line = raw.strip()
                if not line.startswith(b"data:") or line[5:].strip() == b"[DONE]":
                    continue
                ev = json.loads(line[5:])
                if ev.get("usage"):
                    usage = ev["usage"]
                if t_first is None and any((c.get("text") or "") for c in ev.get("choices") or []):
                    t_first = time.perf_counter()
            after = metrics(base)
            rec = {"length": n, "rep": rep, "ttft_s": (t_first - t0) if t_first else None, "usage": usage,
                   "metrics_delta": {k: after.get(k, 0) - before.get(k, 0) for k in after}}
            report["runs"].append(rec)
            cached = ((usage or {}).get("prompt_tokens_details") or {}).get("cached_tokens")
            print(f"len {n:6d} rep {rep}  ttft {rec['ttft_s']:.3f}s  cached {cached}  "
                  f"metrics {{{', '.join(f'{k.split(':')[1]}: {v:g}' for k, v in rec['metrics_delta'].items())}}}", flush=True)
            json.dump(report, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
