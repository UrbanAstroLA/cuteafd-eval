#!/usr/bin/env python3
"""New-question replication (PROTOCOL.md): log p(</think>) at the close on on-policy K4-Core-K6 traces of 30 GPQA
questions not used before (set nq). kld venv python (numpy). Writes analysis/NQ.json.

vLLM launches: k6-a, k6-b (K4-Core-K6, route b), qbo-a, qbo-b (mla_q_b, mla_o, kda_o native BF16), all (whole core BF16).
CuteAFD (if scored): C-K6 (6-bit core), C-K6x (BF16 core, FP8 at load); deterministic, one launch each.
Every difference is the BF16 side minus the 6-bit side (positive = more ready to stop where the trace stopped).
Primary: qbo - k6, launch means, per finished trace; 95% bootstrap clustered by question (2000, seed 20261106).
Pooled sets add the 93 earlier traces (11 questions) scored by the same arms.
Descriptive (not part of any rule): the generation's thinking length, finish classes, accuracy (local-gpqa-score's
frozen extractor on the reply text) and per-request speed, per question; per scoring arm, the trace NLL (mean chosen-token
-log p over stored rows), top-1 agreement and top-64 KL against k6-a, on every nq trace."""
import ast, collections, glob, itertools, json, os, re, statistics as st, sys
import numpy as np

TL = "<tl-run>"; N = "<nq-run>"
AP = "<ap-run>"; CS = "<cs-run>"
sys.path.insert(0, f"{TL}/analysis"); sys.path.insert(0, f"{TL}/capture/plugin")
from score_stop import load_reg, read, THINK  # noqa: E402

NB, SEED = 2000, 20261106
REG_NEW, REG_OLD = load_reg(f"{N}/traces/reg"), load_reg(f"{TL}/traces/reg")


def load(root, sets, reg):
    out = {}
    for s in sets:
        for f in sorted(glob.glob(f"{root}/{s}/*.safetensors")):
            w = os.path.basename(f)[:-len(".safetensors")]; e = reg[(s, w)]
            if e["meta"]["kind"] != "finished":
                continue
            t, sel = read(f); lp = t["sel_logprobs"][:, sel.index(THINK)].astype(np.float64)
            out[f"{s}/{w}"] = (lp, str(e["meta"]["doc"]))
    return out


_g = open("<setup>/eval/local-gpqa-score").read()
PATTERNS = ast.literal_eval(_g[_g.index("PATTERNS = [") + len("PATTERNS = "):_g.index("\n]", _g.index("PATTERNS = [")) + 2])
SAMPLES = ("<runs>/gpqa/glm53-flash-exl3-k3.25@tpurtell__pass1/wrldsuksgo2mars__GLM-5.3-Flash-EXL3-K3.25-v1/"
           "samples_gpqa_diamond_thinking_2026-09-29T10-34-37.597068.jsonl")


def extract(text):
    hits = [(m.start(), m.group(1).upper()) for pat in PATTERNS for m in re.finditer(pat, text, flags=re.I)]
    return max(hits)[1] if hits else None


def kl_rows(r, a):
    """top-64 KL(ref || arm) per row, arm value = its 64th (floor) when absent (score_stop.kl_top, vectorised)."""
    ir, lr = r["topk_ids"].astype(np.int64), r["topk_logprobs"].astype(np.float64)
    ia, la = a["topk_ids"].astype(np.int64), a["topk_logprobs"].astype(np.float64)
    n = ir.shape[0]; off = (np.arange(n, dtype=np.int64) << 20)[:, None]
    o = np.argsort(ia, 1); sa = np.take_along_axis(ia, o, 1) + off; sl = np.take_along_axis(la, o, 1)
    flat, fl = sa.ravel(), sl.ravel(); q = (ir + off).ravel()
    pos = np.clip(np.searchsorted(flat, q), 0, flat.size - 1); hit = flat[pos] == q
    lav = np.where(hit, fl[pos], np.repeat(la.min(1), ir.shape[1])).reshape(ir.shape)
    return (np.exp(lr) * (lr - lav)).sum(1)


def generation():
    tgt = {}
    for line in open(SAMPLES):
        d = json.loads(line); tgt[d["doc_id"]] = d["target"].strip("() ")
    gen = [json.load(open(p)) for p in sorted(glob.glob(f"{N}/gen/doc*_rep*.json"))]
    rows = []
    for g in gen:
        ct = (g.get("usage") or {}).get("completion_tokens")
        ans = extract(g.get("content") or "") if g["cls"] == "ok" else None
        rows.append({"doc": g["doc"], "rep": g["rep"], "seed": g["seed"], "cls": g["cls"], "completion_tokens": ct,
                     "reasoning_chars": g.get("reasoning_chars"), "secs": g.get("secs"),
                     "tok_per_s": round(ct / g["secs"], 1) if ct and g.get("secs") else None,
                     "answer": ans, "correct": (ans == tgt[g["doc"]]) if g["cls"] == "ok" else None})
    ok = [r for r in rows if r["cls"] == "ok"]
    byq = {}
    for d in sorted({r["doc"] for r in rows}):
        rr = [r for r in rows if r["doc"] == d]; f = [r for r in rr if r["cls"] == "ok"]
        byq[str(d)] = {"samples": len(rr), "finished": len(f), "correct": sum(bool(r["correct"]) for r in f),
                       "completion_tokens": [r["completion_tokens"] for r in rr], "classes": [r["cls"] for r in rr]}
    return {"samples": len(rows), "by_class": dict(collections.Counter(r["cls"] for r in rows)),
            "finished_correct": sum(bool(r["correct"]) for r in ok), "finished_no_answer_extracted": sum(r["answer"] is None for r in ok),
            "accuracy_over_finished": (sum(bool(r["correct"]) for r in ok) / len(ok)) if ok else None,
            "accuracy_over_all_samples": (sum(bool(r["correct"]) for r in ok) / len(rows)) if rows else None,
            "completion_tokens_finished": {"median": st.median([r["completion_tokens"] for r in ok]) if ok else None,
                                           "min": min((r["completion_tokens"] for r in ok), default=None),
                                           "max": max((r["completion_tokens"] for r in ok), default=None)},
            "median_tok_per_s_finished": st.median([r["tok_per_s"] for r in ok if r["tok_per_s"]]) if ok else None,
            "by_question": byq, "per_sample": rows}


def trace_metrics(dirs):
    """dirs: {arm: dir holding nq/*.safetensors}. All nq traces (finished and not)."""
    T = {}
    for a, d in dirs.items():
        T[a] = {os.path.basename(f)[:-len(".safetensors")]: read(f)[0] for f in sorted(glob.glob(f"{d}/nq/*.safetensors"))}
    ref = T.get("k6-a")
    out = {}
    for a, tt in T.items():
        o = {"traces": len(tt), "nll_mean_per_trace": float(np.mean([-t["chosen_logprobs"].astype(np.float64).mean() for t in tt.values()]))}
        if ref is not None and a != "k6-a":
            ks = sorted(set(tt) & set(ref))
            o["top1_agree_vs_k6a"] = float(np.mean(np.concatenate([tt[k]["topk_ids"][:, 0] == ref[k]["topk_ids"][:, 0] for k in ks])))
            o["kl_top64_vs_k6a_mean_per_trace"] = float(np.mean([kl_rows(ref[k], tt[k]).mean() for k in ks]))
        out[a] = o
    return out


def cboot(vals, docs):
    by = collections.defaultdict(list)
    for v, d in zip(vals, docs):
        by[d].append(v)
    keys = sorted(by); rng = np.random.default_rng(SEED); bs = []
    for _ in range(NB):
        bs.append(np.mean(np.concatenate([by[keys[i]] for i in rng.integers(0, len(keys), len(keys))])))
    return [float(np.mean(vals)), float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]


def tboot(d):
    d = np.asarray(d); rng = np.random.default_rng(SEED); b = d[rng.integers(0, d.size, (NB, d.size))].mean(1)
    return [float(d.mean()), float(np.quantile(b, .025)), float(np.quantile(b, .975))]


lpc = lambda lp: lp[-1]
haz = lambda lp: float(np.mean(np.exp(lp[-513:-1])))
l512 = lambda lp: float(np.mean(lp[-513:-1]))
MEAS = (("lp_close", lpc), ("hazard", haz), ("last512_logp", l512))


def mean_of(arms, keys, f):
    return np.array([np.mean([f(a[k][0]) for a in arms]) for k in keys])


def contrast(hi, lo, f):
    keys = sorted(set.intersection(*[set(a) for a in hi + lo]))
    docs = [hi[0][k][1] for k in keys]
    d = mean_of(hi, keys, f) - mean_of(lo, keys, f)
    return d, docs, keys


def main():
    out = {"note": "PROTOCOL.md (frozen before the first launch)", "questions_drawn": json.load(open(f"{N}/questions.json"))["docs"]}
    V = {t: load(f"{N}/dumps/runs/{t}", ["nq"], REG_NEW) for t in ("k6-a", "k6-b", "qbo-a", "qbo-b", "all")
         if os.path.isdir(f"{N}/dumps/runs/{t}/nq")}
    out["vllm_launches"] = {t: len(v) for t, v in V.items()}
    K = [V[t] for t in ("k6-a", "k6-b") if t in V]; Q = [V[t] for t in ("qbo-a", "qbo-b") if t in V]
    if len(K) == 2 and len(Q) == 2:
        d, docs, keys = contrast(Q, K, lpc)
        out["finished_traces"], out["questions_with_finished_traces"] = len(keys), len(set(docs))
        p = {"delta_by_question": cboot(d, docs), "delta_by_trace": tboot(d)}
        p["launch_k6_b_minus_a"] = float(np.mean([lpc(V["k6-b"][k][0]) - lpc(V["k6-a"][k][0]) for k in keys]))
        p["launch_qbo_b_minus_a"] = float(np.mean([lpc(V["qbo-b"][k][0]) - lpc(V["qbo-a"][k][0]) for k in keys]))
        p["cross_pairings"] = {f"{q}-{k}": float(np.mean([lpc(V[q][kk][0]) - lpc(V[k][kk][0]) for kk in keys]))
                               for q, k in itertools.product(("qbo-a", "qbo-b"), ("k6-a", "k6-b"))}
        band = max(abs(p["launch_k6_b_minus_a"]), abs(p["launch_qbo_b_minus_a"]))
        r = {"launch_band": band, "ci_excludes_0_positive": p["delta_by_question"][1] > 0,
             "ci_excludes_0_negative": p["delta_by_question"][2] < 0,
             "exceeds_launch_band": abs(p["delta_by_question"][0]) > band,
             "all_cross_pairings_positive": all(v > 0 for v in p["cross_pairings"].values())}
        r["verdict"] = ("replicated" if r["ci_excludes_0_positive"] and r["exceeds_launch_band"] and r["all_cross_pairings_positive"]
                        else "opposite direction" if r["ci_excludes_0_negative"] and r["exceeds_launch_band"]
                        else "not replicated at this size")
        r["earlier_estimate_inside_new_ci"] = p["delta_by_question"][1] <= 0.0118 <= p["delta_by_question"][2]
        out["primary_qbo_minus_k6"] = p; out["reading_rule"] = r
        out["secondary"] = {}
        for name, f in MEAS[1:]:
            d2, docs2, _ = contrast(Q, K, f); out["secondary"][f"qbo_minus_k6_{name}"] = cboot(d2, docs2)
        if "all" in V:
            for name, hi, lo in (("qbo_minus_all", Q, [V["all"]]), ("all_minus_k6", [V["all"]], K)):
                for m, f in MEAS:
                    d2, docs2, _ = contrast(hi, lo, f); out["secondary"][f"{name}_{m}"] = cboot(d2, docs2)
        # pooled with the 93 earlier traces (qbo run launches on the old trace sets)
        O = {t: load(f"{AP}/dumps/runs/{t}", ["tr", "on"], REG_OLD) for t in ("k6-a", "k6-b", "qbo-a", "qbo-b")}
        d_old, docs_old, _ = contrast([O["qbo-a"], O["qbo-b"]], [O["k6-a"], O["k6-b"]], lpc)
        out["pooled_qbo_minus_k6_lp_close"] = cboot(np.concatenate([d_old, d]), ["o" + x for x in docs_old] + ["n" + x for x in docs])
        out["pooled_questions"] = len(set(docs_old)) + len(set(docs))
        out["per_question_new"] = {q: float(np.mean([v for v, dd in zip(d, docs) if dd == q])) for q in sorted(set(docs), key=int)}
    C = {a: load(f"{N}/dumps/cuteafd/{a}", ["nq"], REG_NEW) for a in ("C-K6", "C-K6x") if os.path.isdir(f"{N}/dumps/cuteafd/{a}/nq")}
    if len(C) == 2:
        c = {}
        for m, f in MEAS:
            d2, docs2, keys2 = contrast([C["C-K6x"]], [C["C-K6"]], f); c[f"core_bf16_minus_6bit_{m}"] = cboot(d2, docs2)
        d2, docs2, keys2 = contrast([C["C-K6x"]], [C["C-K6"]], lpc)
        c["rule_ci_excludes_0"] = c["core_bf16_minus_6bit_lp_close"][1] > 0 or c["core_bf16_minus_6bit_lp_close"][2] < 0
        CO = {a: load(f"{CS}/s2/runs/{a}", ["tr", "on"], REG_OLD) for a in ("C-K6", "C-K6x")}
        do, dco, _ = contrast([CO["C-K6x"]], [CO["C-K6"]], lpc)
        c["pooled_core_lp_close"] = cboot(np.concatenate([do, d2]), ["o" + x for x in dco] + ["n" + x for x in docs2])
        if len(K) == 2 and "all" in V:   # same traces, same contrast (whole core BF16 minus 6-bit) on both engines
            dv, _, kv = contrast([V["all"]], K, lpc); m = dict(zip(kv, dv)); kk = [k for k in keys2 if k in m]
            a = np.array([m[k] for k in kk]); b = np.array([d2[keys2.index(k)] for k in kk])
            c["cross_engine_core_lp_close"] = {"vllm_all_minus_k6": float(a.mean()), "cuteafd_k6x_minus_k6": float(b.mean()),
                                               "per_trace_correlation": float(np.corrcoef(a, b)[0, 1]), "traces": len(kk)}
        out["cuteafd"] = c
    out["generation"] = generation()
    dirs = {t: f"{N}/dumps/runs/{t}" for t in V} | {a: f"{N}/dumps/cuteafd/{a}" for a in C}
    out["trace_metrics"] = trace_metrics(dirs)
    json.dump(out, open(f"{N}/analysis/NQ.json", "w"), indent=1)
    brief = {k: v for k, v in out.items() if k not in ("per_question_new", "generation")}
    brief["generation"] = {k: v for k, v in out["generation"].items() if k not in ("by_question", "per_sample")}
    print(json.dumps(brief, indent=1))


if __name__ == "__main__":
    main()
