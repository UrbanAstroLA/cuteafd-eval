#!/usr/bin/env python3
"""End-to-end CPU test of capture.py against a fake OpenAI server that runs the
image's real PromptLogprobsWorker with the glm53_capture plugin armed.

Runs inside the image with --network none (server and driver share the
container's loopback).  Every engine step also carries one background decode
request with 3 drafts, so the window never sits at batch row 0.  Chunked
prefill uses a 2,045-token budget minus the decode rows, as DFlash K3 does.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_capture_cpu as T  # noqa: E402  (CPU Triton stand-ins + synthetic model)

V = 2048
CAP = os.environ.get("CAP_ROOT", "/cap")
BUDGET = 2045


class Fake:
    def __init__(self, model):
        self.model = model
        self.lock = threading.Lock()
        self.n = 0

    def complete(self, body):
        toks = np.asarray(body["prompt"], dtype=np.int32)
        plp = body.get("prompt_logprobs")
        with self.lock:
            self.n += 1
            eng = T.Engine(self.model, max_reqs=4, max_len=len(toks) + 64)
            w = T.pl.PromptLogprobsWorker(4)
            eng.workers = [w]
            eng.add("bg", T.rand_tokens(30, V, 99), None, computed=40)
            rid = f"cmpl-{self.n}"
            eng.add(rid, toks, plp)
            done, result = 0, None
            while done < len(toks):
                n = min(BUDGET - 4, len(toks) - done)
                outs, _ = eng.step({"bg": 4, rid: n}, [w], drafts={"bg": [1, 2, 3]})
                done += n
                if rid in outs[0]:
                    result = outs[0][rid]
        plist = None
        if plp is not None:
            ids = result.logprob_token_ids[:, 0].tolist()
            lps = result.logprobs[:, 0].tolist()
            plist = [None] + [{str(i): {"logprob": lp, "rank": 1, "decoded_token": ""}}
                              for i, lp in zip(ids, lps)]
        return {"choices": [{"index": 0, "text": "x", "prompt_logprobs": plist}],
                "usage": {"prompt_tokens": int(len(toks)), "completion_tokens": 1,
                          "total_tokens": int(len(toks)) + 1,
                          "prompt_tokens_details": {"cached_tokens": 0}}}


def serve(fake):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, payload, ctype="application/json"):
            b = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/v1/models":
                self._send(200, {"data": [{"id": "fake-model"}]})
            elif self.path == "/metrics":
                self._send(200, b'vllm:num_requests_running{model_name="f"} 0.0\n'
                                b'vllm:num_requests_waiting{model_name="f"} 0.0\n', "text/plain")
            else:
                self._send(404, {})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            try:
                self._send(200, fake.complete(body))
            except Exception as exc:  # surface to the driver
                import traceback
                traceback.print_exc()
                self._send(500, {"error": str(exc)})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def drv(args, env, check=True):
    p = subprocess.run([sys.executable, os.path.join(CAP, "capture.py")] + args,
                       env=env, capture_output=True, text=True)
    out = p.stdout + p.stderr
    if check and p.returncode != 0:
        raise AssertionError(f"capture.py {' '.join(args)} failed rc={p.returncode}:\n{out}")
    return p.returncode, out


def main():
    torch.set_num_threads(1)
    tmp = tempfile.mkdtemp(prefix="e2e-")
    reg, out, src = (os.path.join(tmp, x) for x in ("reg", "out", "src"))
    for d in (reg, out, src):
        os.makedirs(d)
    model = T.Model(V)
    # two Q2-style inputs: a bare id list and a {window_id, tokens, rows} object
    long_doc = T.rand_tokens(5000, V, 11)
    json.dump([int(x) for x in long_doc], open(os.path.join(src, "doc-5k.json"), "w"))
    obj = T.rand_tokens(1500, V, 12)
    json.dump({"window_id": "obj1", "tokens": [int(x) for x in obj],
               "rows": list(range(3, 1499, 7))}, open(os.path.join(src, "obj1.json"), "w"))

    os.environ.update({"GLM53_CAP_ENABLE": "1", "GLM53_CAP_REGISTRY": reg,
                       "GLM53_CAP_OUT": os.path.join(out, "staging"),
                       "GLM53_CAP_VOCAB": str(V), "GLM53_CAP_HOST_THREADS": "2"})
    import glm53_capture_plugin as cap
    T.pl.PromptLogprobsWorker.compute_prompt_logprobs = T.ORIG_METHOD
    cap._tp_rank = lambda: 0
    cap.register()
    srv = serve(Fake(model))
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    env = dict(os.environ, CAPTURE_VOCAB=str(V))
    common = ["--registry", reg, "--out-dir", out]
    results = []

    _, o = drv(common + ["register", "--set", "q2", "--json", os.path.join(src, "*.json"),
                         "--last-rows", "1024"], env)
    results.append(("register generic JSON", "PASS", o.strip().splitlines()[-1]))
    rc, o = drv(common + ["register", "--set", "dup", "--json", os.path.join(src, "obj1.json")],
                env, check=False)
    assert rc != 0 and "already registered" in o, o
    results.append(("register refuses duplicate tokens", "PASS", o.strip().splitlines()[-1]))

    _, o = drv(common + ["capture", "--set", "q2", "--run-tag", "r1", "--base-url", base,
                         "--verify-chosen", "6"], env)
    man = json.load(open(os.path.join(out, "runs", "r1", "q2", "capture-manifest.json")))
    w = man["windows"]
    assert set(w) == {"doc-5k", "obj1"} and all(x["ok"] for x in w.values()), w
    assert w["doc-5k"]["n_steps"] == 3 and w["doc-5k"]["chunk_lens"] == [2041, 2041, 918], w["doc-5k"]
    assert w["doc-5k"]["steps_with_other_requests"] == 3
    assert w["doc-5k"]["chosen_check_api"]["max_abs_diff"] < 1e-5
    # the dumped rows equal the independently computed expectation
    from glm53_capture_plugin import core
    for wid, toks, rows, code in (("doc-5k", long_doc, np.arange(5000 - 1 - 1024, 4999), 2),
                                  ("obj1", obj, np.arange(3, 1499, 7), 2)):
        t, _ = core.read_safetensors(os.path.join(out, "runs", "r1", "q2", f"{wid}.safetensors"))
        assert np.array_equal(np.asarray(t["rows"]), rows.astype(np.int32)), wid
        assert np.array_equal(np.asarray(t["logprobs"]), model.expected(code, rows)), wid
    assert not [f for f in os.listdir(os.path.join(out, "staging", "q2"))], "staging not emptied"
    results.append(("capture + --verify-chosen", "PASS",
                    "; ".join(l for l in o.splitlines() if "] " in l)))

    _, o = drv(common + ["capture", "--set", "q2", "--run-tag", "r1", "--base-url", base], env)
    assert o.count("skipping") == 2, o
    _, o = drv(common + ["capture", "--set", "q2", "--run-tag", "r2", "--base-url", base,
                         "--only", "obj1"], env)
    results.append(("resume skips; second run tag recaptures", "PASS", o.strip().splitlines()[-1]))

    _, o = drv(common + ["verify", "--set", "q2", "--run-tag", "r1"], env)
    f = os.path.join(out, "runs", "r1", "q2", "obj1.safetensors")
    t, _ = core.read_safetensors(f)
    off = int.from_bytes(open(f, "rb").read(8), "little") + 8
    with open(f, "r+b") as fh:          # corrupt one row: shift slot 5 by +0.5 nats
        fh.seek(off + 5 * V * 4)
        row = np.frombuffer(fh.read(V * 4), dtype=np.float32) + np.float32(0.5)
        fh.seek(off + 5 * V * 4)
        fh.write(row.tobytes())
    rc, o2 = drv(common + ["verify", "--set", "q2", "--run-tag", "r1", "--sample", "214"],
                 env, check=False)
    assert rc == 1 and "BAD     obj1" in o2 and "logsumexp" in o2, o2
    results.append(("verify passes clean, flags a corrupted row", "PASS",
                    o2.strip().splitlines()[0][:120]))

    srv.shutdown()
    shutil.rmtree(tmp)
    for name, st, d in results:
        print(f"{st:5s} {name:42s} {d}")
    print("ALL PASS")


if __name__ == "__main__":
    main()
