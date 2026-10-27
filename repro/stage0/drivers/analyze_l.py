#!/usr/bin/env python3
"""Block L analysis: stop vs cap, loop onset and exact period, decode rate by position, correctness.

Two modes.
  Host (default; standard library only):
      analyze_l.py RECEIPT.json [RECEIPT2.json ...] --out ANALYSIS.json [--skip-code]
    1. per receipt, runs this file with --inner in a CPU-only, no-network container of the CPU image
       (tokenizers, numpy, jsonschema), receipt directory read-only;
    2. runs the code checker (../prompts/checkers/code_check.py) on every code reply: pytest in a
       --network none sandbox container, no GPU;
    3. merges, summarizes per (label, stage, content), and pairs requests across labels by
       (stage, content, prompt, rep) when two or more receipts are given.
  Inner (inside the container): tokenization, loops, math, json, prose length.

Definitions (ported, not changed, from the long-reply investigation; see the cited files):
  ids          re-tokenization of the saved reasoning text followed by the saved content text (generation order),
               K3.25 tokenizer, add_special_tokens=False. drift = completion_tokens - len(ids) is reported.
  onset        trajectory.py (discovery/scripts): R50 = share of positions in a sliding 4,096-token window whose
               50-gram occurred earlier; onset = start of the final run with R50 >= 0.5, only if R50 at the end of
               the reply is >= 0.5 (a terminal loop); None otherwise. Sensitivity at thresholds 0.3 and 0.7.
  period       periods.py (same directory): lag match rate m(p) = share of i with t[i] == t[i-p], screened for
               p <= 65,536 by random-phase FFT autocorrelation (3 phases, rng 12345) and computed exactly for the
               top 40 candidates; exact period = smallest p with m(p) >= 0.8, on the post-onset region (>= 1,024
               tokens). Added here (separate field): exact_period_m08_divisor_refined also tests the divisors of
               that period, because every multiple of a short period ties at m = 1.0 and the screen can miss it. Also the longest repeated substring (suffix array + LCP) of the whole reply and post-onset.
  stop vs cap  finish_reason and completion_tokens >= cap.
  position     decode tok/s per 2,048-token bucket from chunk timestamps, positions exact via token offsets.
  correctness  math: checkers/math_check.check; json: checkers/json_check.check; code: checkers/code_check.check;
               prose: words in the final text (whitespace split) vs the prompt's required words (ratio; not pass/fail).
"""
import argparse
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE0 = HERE.parent
PROMPTS = STAGE0 / "prompts"
CPU_IMAGE = "sha256:392db7c0bdd39ec5aacda800f9a3ada70342721a2357ad1ec09ad0ef5981459a"
REPO = "<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K3.25-v1"
TOK_IN_CONTAINER = "/repo/snapshots/0490d2f708b12145f6516555ab066aaeb401cd21/tokenizer.json"
W, THR, SENS, NGRAM, MAXLAG, BUCKET = 4096, 0.5, (0.3, 0.7), 50, 65536, 2048


# ---------------------------------------------------------------- inner (container) ----
def inner(receipt_path, out_path):
    import numpy as np
    from tokenizers import Tokenizer
    sys.path.insert(0, str(PROMPTS / "checkers"))
    import json_check
    import math_check

    tok = Tokenizer.from_file(TOK_IN_CONTAINER)
    rc = json.loads(Path(receipt_path).read_text())
    text_dir = Path(receipt_path).parent / rc["text_dir"]
    schema = json.loads((PROMPTS / "authored" / "json_task.json").read_text())["record_schema"]
    prompts = {}
    for c in json.loads((PROMPTS / "L" / "index.json").read_text())["prompts"]:
        prompts[c["id"]] = json.loads((PROMPTS / c["file"]).read_text())

    def ngram_hash(t, n):
        m = len(t) - n + 1
        if m <= 0:
            return np.zeros(0, dtype=np.uint64)
        x = t.astype(np.uint64) + np.uint64(1)
        h = np.zeros(m, dtype=np.uint64)
        B = np.uint64(1000003)
        with np.errstate(over="ignore"):
            for k in range(n):
                h = h * B + x[k:k + m]
        return h

    def rep_flags(h):
        m = len(h)
        idx = np.arange(m)
        order = np.lexsort((idx, h))
        hs = h[order]
        prev_s = np.full(m, -1, dtype=np.int64)
        same = hs[1:] == hs[:-1]
        prev_s[1:][same] = order[:-1][same]
        prev = np.empty(m, dtype=np.int64)
        prev[order] = prev_s
        return prev >= 0

    def onset_of(R, thr):
        if len(R) == 0:
            return None
        hi = R >= thr
        if not hi[-1]:
            return None
        lo = np.where(~hi)[0]
        return int(lo[-1] + 1) if len(lo) else 0

    def suffix_array(t):
        n = len(t)
        _, rank = np.unique(t, return_inverse=True)
        rank = rank.astype(np.int64)
        k = 1
        while True:
            r2 = np.full(n, -1, dtype=np.int64)
            r2[:n - k] = rank[k:]
            sa = np.lexsort((r2, rank))
            key = rank[sa] * (n + 2) + (r2[sa] + 1)
            new = np.empty(n, dtype=np.int64)
            new[sa] = np.concatenate([[0], np.cumsum(key[1:] != key[:-1])])
            rank = new
            if rank.max() == n - 1:
                break
            k *= 2
        return sa

    def lrs(t):
        n = len(t)
        if n < 2:
            return {"len": 0, "start_a": None, "start_b": None, "offset": None}
        sa = suffix_array(t)
        rank = np.empty(n, dtype=np.int64)
        rank[sa] = np.arange(n)
        tl, sal, rk = t.tolist(), sa.tolist(), rank.tolist()
        h, best, bi = 0, 0, -1
        for i in range(n):
            r = rk[i]
            if r > 0:
                j = sal[r - 1]
                while i + h < n and j + h < n and tl[i + h] == tl[j + h]:
                    h += 1
                if h > best:
                    best, bi = h, r
                if h > 0:
                    h -= 1
            else:
                h = 0
        if bi < 0:
            return {"len": 0, "start_a": None, "start_b": None, "offset": None}
        a_, b_ = sorted((sal[bi], sal[bi - 1]))
        return {"len": int(best), "start_a": int(a_), "start_b": int(b_), "offset": int(b_ - a_)}

    def lag_profile(t):
        n = len(t)
        maxlag = min(MAXLAG, n // 2)
        if maxlag < 2:
            return None
        rng = np.random.default_rng(12345)
        acc = np.zeros(maxlag + 1)
        L = 1 << int(np.ceil(np.log2(2 * n)))
        for _ in range(3):
            u = rng.random(int(t.max()) + 1)
            z = np.exp(2j * np.pi * u[t])
            F = np.fft.fft(z, L)
            acc += np.fft.ifft(F * np.conj(F))[: maxlag + 1].real
        acc /= 3
        m = acc[1:] / (n - np.arange(1, maxlag + 1))
        cand = np.argsort(-m)[:40] + 1
        exact = {int(p): float((t[p:] == t[:-p]).mean()) for p in sorted(set(int(c) for c in cand))}
        top = sorted(exact.items(), key=lambda kv: -kv[1])[:5]
        per = min([p for p, v in exact.items() if v >= 0.8], default=None)
        # addition (not in periods.py): for a short exact loop every multiple of the period ties at m = 1.0 and
        # the top-40 screen can miss the period itself, so the divisors of `per` are also checked exactly
        ref = per
        if per is not None:
            for d in range(1, per):
                if per % d == 0 and float((t[d:] == t[:-d]).mean()) >= 0.8:
                    ref = d
                    break
        return {"top_lags": [[p, round(v, 4)] for p, v in top], "exact_period_m08": per,
                "exact_period_m08_divisor_refined": ref}

    def exact_position_rates(payload, r_offs, c_offs, n_r):
        import bisect
        cum_r = cum_c = 0
        t_at = []
        for t, n, k in zip(payload["chunk_t"], payload["chunk_chars"], payload["chunk_kind"]):
            if k == "r":
                cum_r += n
                pos = bisect.bisect_right(r_offs, cum_r)
            else:
                cum_c += n
                pos = n_r + bisect.bisect_right(c_offs, cum_c)
            b = pos // BUCKET
            while len(t_at) <= b:
                t_at.append(t)
        out = []
        for k in range(1, len(t_at)):
            dt = t_at[k] - t_at[k - 1]
            out.append({"start": (k - 1) * BUCKET, "tok_s": round(BUCKET / dt, 2) if dt > 0 else None})
        return {"bucket_tokens": BUCKET, "method": "exact token positions (re-tokenized)", "buckets": out}

    results = []
    for st in rc["stages"]:
        for rec in st["requests"]:
            res = {"request_id": rec["request_id"], "label": rc["label"], "stage": rec["stage"], "cap": rec["cap"],
                   "content": rec["content"], "prompt_index": rec["prompt_index"], "rep": rec["rep"],
                   "seed": rec["seed"], "finish_reason": rec["finish_reason"],
                   "completion_tokens": rec["completion_tokens"], "hit_cap": rec["hit_cap"], "error": rec["error"],
                   "reasoning_chars": rec["reasoning_chars"], "content_chars": rec["content_chars"],
                   "content_has_think_close": rec.get("content_has_think_close"),
                   "decode_tok_s": rec.get("decode_tok_s")}
            res["stop"] = ("error" if rec["error"] else "cap" if rec["hit_cap"] or rec["finish_reason"] == "length"
                           else "stop" if rec["finish_reason"] == "stop" else str(rec["finish_reason"]))
            f = text_dir / rec["text_file"]
            payload = json.loads(gzip.decompress(f.read_bytes()))
            er = tok.encode(payload["reasoning"], add_special_tokens=False)
            ec = tok.encode(payload["content"], add_special_tokens=False)
            ids = np.array(er.ids + ec.ids, dtype=np.int64)
            N = len(ids)
            res.update(reasoning_tokens=len(er.ids), content_tokens=len(ec.ids), retokenized_tokens=N,
                       drift=(rec["completion_tokens"] - N) if rec["completion_tokens"] is not None else None)
            loop = {"onset": None, "sensitivity": {}, "lrs_full": lrs(ids) if N >= 2 else None}
            if N >= W + NGRAM:
                r50 = rep_flags(ngram_hash(ids, NGRAM)).astype(np.float64)
                cs = np.concatenate([[0.0], np.cumsum(r50)])
                R50 = (cs[W:] - cs[:-W]) / W
                loop["onset"] = onset_of(R50, THR)
                loop["sensitivity"] = {str(t): onset_of(R50, t) for t in SENS}
                loop["R50_final"] = round(float(R50[-1]), 4)
                loop["R50_max"] = round(float(R50.max()), 4)
            else:
                loop["note"] = f"reply shorter than {W + NGRAM} tokens: R50 undefined, onset not assessed"
            o = loop["onset"]
            if o is not None and N - o >= 1024:
                reg = ids[o:]
                lp = lrs(reg)
                for k in ("start_a", "start_b"):
                    if lp[k] is not None:
                        lp[k] += o
                loop["lrs_post_onset"] = lp
                loop["lag_post_onset"] = lag_profile(reg)
                loop["onset_in"] = "reasoning" if o < len(er.ids) else "content"
            end = o if o is not None else N
            reg = ids[max(0, end - 32768):end]
            loop["lag_last32k_before_onset_or_end"] = lag_profile(reg) if len(reg) >= 2048 else None
            res["loop"] = loop
            res["position_rates_exact"] = exact_position_rates(
                payload, [x[1] for x in er.offsets], [x[1] for x in ec.offsets], len(er.ids))
            ck = prompts[rec["prompt_id"]]["checker"]
            if ck["kind"] == "math":
                res["check"] = math_check.check(payload["content"], ck["answer"], payload["reasoning"])
            elif ck["kind"] == "json":
                res["check"] = json_check.check(payload["content"], ck["n"], schema)
            elif ck["kind"] == "prose":
                words = len(json_check.final_text(payload["content"]).split())
                res["check"] = {"words": words, "required_words": ck["required_words"],
                                "ratio": round(words / ck["required_words"], 4)}
            else:
                res["check"] = {"pending": "code (host sandbox)"}
            results.append(res)
            print(res["request_id"], res["stop"], N, "onset", loop["onset"], flush=True)
    Path(out_path).write_text(json.dumps({"label": rc["label"], "results": results,
                                          "not_started": [x | {"stage": st["stage"]} for st in rc["stages"]
                                                          for x in st["not_started"]]}, indent=1) + "\n")


# ---------------------------------------------------------------- host ----
def summarize(results):
    import statistics
    groups = {}
    for r in results:
        groups.setdefault((r["label"], r["stage"], r["content"]), []).append(r)
    out = []
    for (label, stage, content), rs in sorted(groups.items()):
        ok = [r for r in rs if not r["error"]]
        s = {"label": label, "stage": stage, "content": content, "n": len(rs), "errors": len(rs) - len(ok),
             "stop": sum(r["stop"] == "stop" for r in rs), "cap": sum(r["stop"] == "cap" for r in rs),
             "terminal_loops": sum(r["loop"]["onset"] is not None for r in rs),
             "content_has_think_close": sum(bool(r.get("content_has_think_close")) for r in rs)}
        toks = [r["completion_tokens"] for r in ok if r["completion_tokens"] is not None]
        if toks:
            s["completion_tokens_median"] = statistics.median(toks)
            s["completion_tokens_min_max"] = [min(toks), max(toks)]
        rates = [r["decode_tok_s"] for r in ok if r.get("decode_tok_s")]
        if rates:
            s["decode_tok_s_median"] = round(statistics.median(rates), 2)
        chk = [r["check"] for r in rs]
        if content in ("reasoning",):
            s["correct"] = sum(bool(c.get("correct")) for c in chk)
        elif content == "json":
            s["valid"] = sum(bool(c.get("valid")) for c in chk)
        elif content == "code":
            s["all_pass"] = sum(bool(c.get("all_pass")) for c in chk)
            s["tests_passed_total"] = sum(c.get("passed") or 0 for c in chk)
        elif content == "prose":
            ratios = [c["ratio"] for c in chk if "ratio" in c]
            if ratios:
                s["words_ratio_median"] = statistics.median(ratios)
        out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("receipts", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--image", default=CPU_IMAGE)
    ap.add_argument("--skip-code", action="store_true")
    ap.add_argument("--inner", action="store_true")
    ap.add_argument("--receipt")
    a = ap.parse_args()
    if a.inner:
        inner(a.receipt, a.out)
        return
    if not a.receipts or not a.out:
        ap.error("give one or more receipts and --out")
    sys.path.insert(0, str(PROMPTS / "checkers"))
    import code_check

    out_path = Path(a.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_results, not_started = [], []
    for rp in map(lambda p: Path(p).resolve(), a.receipts):
        inner_out = out_path.parent / (rp.stem + ".inner.json")
        cmd = ["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
               "-e", "CUDA_VISIBLE_DEVICES=", "--entrypoint", "python3",
               "-v", f"{HERE}:{HERE}:ro", "-v", f"{PROMPTS}:{PROMPTS}:ro", "-v", f"{REPO}:/repo:ro",
               "-v", f"{rp.parent}:/run_in:ro", "-v", f"{out_path.parent}:/run_out", a.image,
               str(HERE / "analyze_l.py"), "--inner", "--receipt", f"/run_in/{rp.name}",
               "--out", f"/run_out/{inner_out.name}"]
        p = subprocess.run(cmd)
        if p.returncode != 0:
            sys.exit(f"inner analysis failed for {rp} (exit {p.returncode})")
        inner_res = json.loads(inner_out.read_text())
        rc = json.loads(rp.read_text())
        text_dir = rp.parent / rc["text_dir"]
        prompts = {c["id"]: json.loads((PROMPTS / c["file"]).read_text())
                   for c in json.loads((PROMPTS / "L" / "index.json").read_text())["prompts"]}
        by_id = {r["request_id"]: r for st in rc["stages"] for r in st["requests"]}
        for res in inner_res["results"]:
            if res["content"] != "code" or a.skip_code:
                continue
            if res["error"]:
                res["check"] = {"status": "not checked: request error", "all_pass": False}
                continue
            rec = by_id[res["request_id"]]
            ck = prompts[rec["prompt_id"]]["checker"]
            payload = json.loads(gzip.decompress((text_dir / rec["text_file"]).read_bytes()))
            res["check"] = code_check.check(payload["content"], ck["project"], ck["package"],
                                            PROMPTS / ck["tests_dir"])
            print(res["request_id"], "code", res["check"]["status"], res["check"].get("passed"), "/",
                  res["check"].get("tests"), flush=True)
        all_results += inner_res["results"]
        not_started += [x | {"label": inner_res["label"]} for x in inner_res["not_started"]]
    pairs = []
    labels = sorted({r["label"] for r in all_results})
    if len(labels) >= 2:
        idx = {}
        for r in all_results:
            idx.setdefault((r["stage"], r["content"], r["prompt_index"], r["rep"]), {})[r["label"]] = r
        for k in sorted(idx):
            row = {"stage": k[0], "content": k[1], "prompt_index": k[2], "rep": k[3]}
            for lab in labels:
                r = idx[k].get(lab)
                row[lab] = None if r is None else {
                    "stop": r["stop"], "completion_tokens": r["completion_tokens"], "onset": r["loop"]["onset"],
                    "period": (r["loop"].get("lag_post_onset") or {}).get("exact_period_m08"),
                    "period_refined": (r["loop"].get("lag_post_onset") or {}).get("exact_period_m08_divisor_refined"),
                    "correct": r["check"].get("correct", r["check"].get("valid", r["check"].get("all_pass")))}
            pairs.append(row)
    report = {"receipts": [str(p) for p in a.receipts], "labels": labels, "summary": summarize(all_results),
              "not_started": not_started, "pairs": pairs, "results": all_results,
              "definitions": __doc__}
    out_path.write_text(json.dumps(report, indent=1) + "\n")
    for s in report["summary"]:
        print(json.dumps(s))


if __name__ == "__main__":
    main()
