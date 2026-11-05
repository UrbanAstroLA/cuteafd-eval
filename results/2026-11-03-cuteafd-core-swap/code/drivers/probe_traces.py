#!/usr/bin/env python3
"""Core-swap step 2: score the thinking-length investigation's 93 fixed traces on CuteAFD's bench probe and write each
as the reduced dump the vLLM captures wrote (capture plugin 0.3 layout), so analysis/score_stop.py of that run scores
both engines unchanged and the traces pair one to one. Needs numpy (run with the kld venv python).

One POST /v1/bench/probe per trace (scoring launch: ENABLE_BENCH=on, API_KEY_FILE, FULL_PREFILL_LOGITS=on), the
geometry of the v4 run's capture_probe.py:
  spec = {prompt_ids: tokens[:last row + 2], cold, no_speculation, score_path prefill, score_from: first row + 1,
          score_positions: [r + 1 for each stored row], top_k: 64, want: {r + 1: [154842, 154827, tokens[r + 1]]}}
Row r is the distribution after tokens[0..r]; it predicts tokens[r + 1] (the vLLM capture's convention).

Written per trace: <out>/<set>/<window_id>.safetensors (topk_ids, topk_logprobs, sel_logprobs [</think>, <think>],
chosen_logprobs, rows, tokens_sha256) and <window_id>.receipt.json (seconds, engine checks, per-row FNV hashes of the
raw logits for the cross-launch bit-identity check). Existing outputs are kept (resume). Any HTTP or shape error stops
the run (exit 2).

  probe_traces.py --reg <reg dir> --out <dumps>/runs/<arm> --api-key-file KEY [--sets tr,on] [--only ID,ID] [--dry-run]
"""
import argparse, hashlib, json, os, sys, time, urllib.error, urllib.request
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, "<tl-run>/capture/plugin")
from glm53_capture_plugin import core  # noqa: E402

THINK, THINK_OPEN, K = 154842, 154827, 64
SEL = (THINK, THINK_OPEN)


def load(reg, sets):
    out = []
    for s in sets:
        d = os.path.join(reg, s)
        for f in sorted(os.listdir(d)):
            if f.endswith(".json"):
                e = json.load(open(os.path.join(d, f)))
                out.append(e)
    return out


def spec_of(e):
    rows = sorted(e["rows"]); t = e["tokens"]
    want = {str(r + 1): list(dict.fromkeys([THINK, THINK_OPEN, t[r + 1]])) for r in rows}
    return {"prompt_ids": t[:rows[-1] + 2], "cold": True, "no_speculation": True, "score_from": rows[0] + 1,
            "score_path": "prefill", "score_positions": [r + 1 for r in rows], "top_k": K, "want": want}


def payload(e):
    return {"body": {"messages": [{"role": "user", "content": "score"}], "max_tokens": 1, "temperature": 1.0,
                     "top_p": 0.95, "top_k": -1, "seed": 1}, "spec": spec_of(e)}


def parse(reply, e):
    pr = reply.get("probe") or {}
    if pr.get("error"):
        raise ValueError(f"probe error: {pr['error']}")
    rows = sorted(e["rows"]); t = e["tokens"]
    checks = {"engine": pr.get("engine"), "cold": pr.get("cold"), "no_speculation": pr.get("no_speculation"),
              "cached_tokens": pr.get("cached_tokens"), "score_path": pr.get("score_path"),
              "scored_prefill_chunks": pr.get("scored_prefill_chunks"),
              "prompt_ids_match": pr.get("prompt_ids") == t[:rows[-1] + 2]}
    if not (checks["engine"] and checks["cold"] is True and checks["no_speculation"] is True
            and checks["cached_tokens"] == 0 and checks["prompt_ids_match"] and checks["score_path"] == "prefill"):
        raise ValueError(f"engine did not honour cold, drafts-off, prefill scoring of these ids: {checks}")
    by = {}
    for row in pr.get("rows") or []:
        p = int(row["position"])
        if p in by:
            raise ValueError(f"position {p} returned twice")
        by[p] = row
    n = len(rows)
    ids = np.zeros((n, K), np.int32); lps = np.zeros((n, K), np.float32)
    sel = np.zeros((n, len(SEL)), np.float32); ch = np.zeros(n, np.float32); hashes = []
    for i, r in enumerate(rows):
        row = by.get(r + 1)
        if row is None:
            raise ValueError(f"position {r + 1} missing from the reply")
        if row.get("finite") is False:
            raise ValueError(f"position {r + 1}: non-finite logits")
        top = row["top"]
        if len(top) != K:
            raise ValueError(f"position {r + 1}: {len(top)} top entries, expected {K}")
        ids[i] = [int(a) for a, _ in top]; lps[i] = [b for _, b in top]
        w = {int(a): b for a, b in row.get("wanted") or []}
        for j, tok in enumerate(SEL):
            sel[i, j] = w[tok]
        ch[i] = w[t[r + 1]]
        hashes.append(row.get("hash"))
    return {"topk_ids": ids, "topk_logprobs": lps, "sel_logprobs": sel, "chosen_logprobs": ch,
            "rows": np.asarray(rows, np.int32)}, checks, hashes


def write_dump(path, arrs, e):
    tsha = hashlib.sha256(np.asarray(e["tokens"], np.int32).tobytes()).digest()
    meta = {"window_id": e["window_id"], "set": e["set"], "n_tokens": len(e["tokens"]), "n_rows": len(e["rows"]),
            "row_convention": "row r = log-softmax of the logits after tokens[0..r] inclusive; it predicts tokens[r+1]",
            "logprob_method": "CuteAFD bench probe: f64 log-softmax of the f32 logits row, returned as f32",
            "producer": "cuteafd probe_traces.py", "reduced": 1, "topk": K, "sel_token_ids": ",".join(map(str, SEL))}
    hdr, _, _, _ = core.build_reduced_header(len(e["rows"]), K, len(SEL), meta)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(hdr)
        for name in ("topk_ids", "topk_logprobs", "sel_logprobs", "chosen_logprobs", "rows"):
            f.write(np.ascontiguousarray(arrs[name]).tobytes())
        f.write(tsha)
    os.replace(tmp, path)
    t, m = core.read_safetensors(path, mmap=False)            # read back through the scorer's own reader
    for name in ("topk_ids", "topk_logprobs", "sel_logprobs", "chosen_logprobs", "rows"):
        if not np.array_equal(np.asarray(t[name]), arrs[name]):
            raise ValueError(f"{path}: {name} did not read back equal")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reg", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8001"); ap.add_argument("--api-key-file")
    ap.add_argument("--sets", default="tr,on"); ap.add_argument("--only"); ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    E = load(a.reg, a.sets.split(","))
    if a.only:
        keep = set(a.only.split(",")); E = [e for e in E if e["window_id"] in keep]
    print(f"{len(E)} traces, {sum(len(e['rows']) for e in E):,} scored rows, "
          f"{sum(e['rows'][-1] + 2 for e in E):,} prompt tokens, longest {max(e['rows'][-1] + 2 for e in E):,}", flush=True)
    if a.dry_run:
        b = json.dumps(payload(max(E, key=lambda e: len(e["tokens"])))).encode()
        print(f"largest request body {len(b) / 2**20:.1f} MiB (limit 64 MiB)"); return 0
    key = open(a.api_key_file).read().strip() if a.api_key_file else None
    hdr = {"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}
    for e in E:
        d = os.path.join(a.out, e["set"]); os.makedirs(d, exist_ok=True)
        path = os.path.join(d, e["window_id"] + ".safetensors")
        if os.path.exists(path):
            continue
        req = urllib.request.Request(a.base_url + "/v1/bench/probe", data=json.dumps(payload(e)).encode(), headers=hdr, method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=a.timeout) as r:
                reply = json.load(r)
        except urllib.error.HTTPError as x:
            print(f"{e['window_id']}: HTTP {x.code} {x.read()[:500]!r}", flush=True); return 2
        except Exception as x:
            print(f"{e['window_id']}: {type(x).__name__}: {x}", flush=True); return 2
        secs = time.perf_counter() - t0
        try:
            arrs, checks, hashes = parse(reply, e)
            write_dump(path, arrs, e)
        except Exception as x:
            print(f"{e['window_id']}: {x}", flush=True); return 2
        json.dump({"window_id": e["window_id"], "set": e["set"], "secs": round(secs, 2), "prompt_tokens": e["rows"][-1] + 2,
                   "rows": len(e["rows"]), "checks": checks, "row_hashes": hashes},
                  open(path[:-len(".safetensors")] + ".receipt.json", "w"))
        print(f"{e['window_id']}: {secs:.1f} s, {e['rows'][-1] + 2:,} tokens, {len(e['rows'])} rows", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
