#!/usr/bin/env python3
"""CPU stub of CuteAFD's POST /v1/bench/probe reply shape (probe.rs ProbeRow fields), for testing probe_traces.py.
Logits are a fixed pseudo-random function of (STUB_ARM, position): two arms give different, reproducible rows.
    STUB_ARM=a python3 stub_probe.py 18011"""
import json, math, os, random, sys, zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
ARM = os.environ.get("STUB_ARM", "a"); V = 154880

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        s = req["spec"]; rows = []
        for p in s["score_positions"]:
            rng = random.Random(f"{ARM}:{p}")
            ids = rng.sample(range(V), 200); z = [rng.gauss(0, 3) for _ in ids]
            want_ids = [int(x) for x in s["want"].get(str(p), [])]
            for w in want_ids:
                if w not in ids: ids.append(w); z.append(rng.gauss(-4, 1))
            m = max(z); lse = m + math.log(sum(math.exp(v - m) for v in z) + (V - len(z)) * math.exp(-20 - m))
            lp = {i: v - lse for i, v in zip(ids, z)}
            top = sorted(lp.items(), key=lambda kv: (-kv[1], kv[0]))[:s["top_k"]]
            rows.append({"position": p, "hash": zlib.crc32(f"{ARM}:{p}".encode()), "argmax": top[0][0], "top": top,
                         "wanted": [[w, lp[w]] for w in want_ids], "finite": True})
        out = {"probe": {"engine": "stub", "cold": True, "no_speculation": True, "cached_tokens": 0, "score_path": "prefill",
                         "scored": len(rows), "scored_prefill_chunks": 1, "prompt_ids": s["prompt_ids"], "rows": rows}}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
