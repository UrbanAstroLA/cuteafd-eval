#!/usr/bin/env python3
"""G2 scorer (CPU, numpy). Reads plugin-0.3 reduced dumps per arm and scores the stop decision (PLAN.md, reading rule).

    python3 score_stop.py --dumps <capture out>/runs --reg <traces/reg> --base k6 --ref all --out <file.json>
                          [--teacher <datasets>/glm53-flash-teacher-logits] [--pa-meta <pa.meta.json>]

Per arm (a directory runs/<arm>/<set>/ of <window>.safetensors):
  finished traces (sets tr, on; kind finished; the last stored row predicts </think>):
    lp_close   log p(</think>) at the close row
    hazard     mean p(</think>) over the last 512 rows before the close (close row excluded)
    close_top1 share of traces where </think> is the arm's top-1 at the close row
  not-finished traces: max p(</think>) over stored rows; share of rows where </think> is top-1
  kl_ref     top-64 KL(ref arm || arm) over every stored trace row, and over the last 512 rows of finished traces:
             sum over the ref arm's top-64 ids of p_ref * (lp_ref - lp_arm), lp_arm taken from the arm's top-64 when present,
             else the arm's 64th value (an upper bound on its probability, so a lower bound on that term)
  P-A        top-64 KL(BF16 teacher || arm), same convention with the teacher's top-64; overall and per domain; mean NLL
Contrasts: arm - base for every measure, paired over traces (windows for P-A), 2,000-replicate bootstrap; for the stop
measures also closure = (arm - base) / (ref - base). A group "moves" a stop measure when closure >= 0.5 and the
bootstrap interval of (arm - base) excludes 0. Descriptive otherwise.
"""
import argparse, glob, json, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "capture", "plugin"))
from glm53_capture_plugin import core  # noqa: E402

THINK = 154842
NB, SEED = 2000, 20261102


def load_reg(reg):
    out = {}
    for f in glob.glob(os.path.join(reg, "*", "*.json")):
        d = json.load(open(f))
        out[(d["set"], d["window_id"])] = d
    return out


def read(path):
    t, meta = core.read_safetensors(path, mmap=False)
    sel = [int(x) for x in meta["sel_token_ids"].split(",")]
    return {k: np.asarray(v) for k, v in t.items()}, sel


def kl_top(ids_r, lp_r, ids_a, lp_a):
    """Top-k KL(ref || arm) per row with the floor convention (see docstring)."""
    n, k = ids_r.shape
    out = np.empty(n)
    for i in range(n):
        m = dict(zip(ids_a[i].tolist(), lp_a[i].tolist()))
        floor = lp_a[i, -1]
        la = np.array([m.get(t, floor) for t in ids_r[i].tolist()])
        p = np.exp(lp_r[i])
        out[i] = float(np.sum(p * (lp_r[i] - la)))
    return out


def trace_measures(arm_dir, reg):
    res = {}
    for set_ in ("tr", "on"):
        for f in sorted(glob.glob(os.path.join(arm_dir, set_, "*.safetensors"))):
            wid = os.path.basename(f)[:-len(".safetensors")]
            e = reg[(set_, wid)]
            t, sel = read(f)
            j = sel.index(THINK)
            lp_think = t["sel_logprobs"][:, j].astype(np.float64)
            top1 = t["topk_ids"][:, 0] == THINK
            kind = e["meta"]["kind"]
            m = {"set": set_, "kind": kind, "doc": e["meta"]["doc"], "rows": int(lp_think.size)}
            if kind == "finished":
                m["lp_close"] = float(lp_think[-1])
                m["hazard"] = float(np.mean(np.exp(lp_think[-513:-1])))
                m["close_top1"] = bool(top1[-1])
            else:
                m["max_p_think"] = float(np.exp(lp_think.max()))
                m["think_top1_share"] = float(top1.mean())
            res[f"{set_}/{wid}"] = (m, t)
    return res


def boot_paired(x, y):
    """mean(y - x) and its 95% interval, paired, bootstrap over items."""
    d = np.asarray(y) - np.asarray(x)
    rng = np.random.default_rng(SEED)
    b = d[rng.integers(0, d.size, size=(NB, d.size))].mean(1)
    return float(d.mean()), [float(np.quantile(b, .025)), float(np.quantile(b, .975))]


def pa_measures(arm_dir, teacher_top, doms):
    kl, nll, dom = [], [], []
    for f in sorted(glob.glob(os.path.join(arm_dir, "pa", "*.safetensors"))):
        wid = os.path.basename(f)[:-len(".safetensors")]
        t, _ = read(f)
        ti, tl = teacher_top[wid]
        k = kl_top(ti, tl, t["topk_ids"], t["topk_logprobs"].astype(np.float64))
        kl.append(float(k.mean())); nll.append(float(-t["chosen_logprobs"].astype(np.float64).mean())); dom.append(doms.get(wid))
    return {"windows": len(kl), "kl64_per_window": kl, "nll_per_window": nll, "domain": dom}


def teacher_tops(teacher, wids, k=64):
    out = {}
    for wid in wids:
        n = int(wid.split("-")[1])
        t, _ = core.read_safetensors(os.path.join(teacher, "logits", f"window-{n:04d}.safetensors"))
        z = np.asarray(t["logits"], dtype=np.float64)
        z = z - (z.max(1, keepdims=True) + np.log(np.exp(z - z.max(1, keepdims=True)).sum(1, keepdims=True)))
        part = np.argpartition(z, -k, axis=1)[:, -k:]
        v = np.take_along_axis(z, part, 1); o = np.argsort(-v, 1)
        out[wid] = (np.take_along_axis(part, o, 1), np.take_along_axis(v, o, 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dumps", required=True); ap.add_argument("--reg", required=True)
    ap.add_argument("--base", default="k6"); ap.add_argument("--ref", default="all")
    ap.add_argument("--teacher"); ap.add_argument("--pa-meta"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    reg = load_reg(a.reg)
    arms = sorted(d for d in os.listdir(a.dumps) if os.path.isdir(os.path.join(a.dumps, d)))
    T = {arm: trace_measures(os.path.join(a.dumps, arm), reg) for arm in arms}
    ref = T[a.ref]
    out = {"arms": arms, "base": a.base, "ref": a.ref, "per_arm": {}, "contrast_vs_base": {}, "pa": {}}
    for arm in arms:
        ms = {k: v[0] for k, v in T[arm].items()}
        fin = [m for m in ms.values() if m["kind"] == "finished"]
        non = [m for m in ms.values() if m["kind"] != "finished"]
        kl_all, kl_stop = [], []
        for key, (m, t) in T[arm].items():
            rt = ref[key][1]
            k = kl_top(rt["topk_ids"], rt["topk_logprobs"].astype(np.float64), t["topk_ids"], t["topk_logprobs"].astype(np.float64))
            kl_all.append(float(k.mean()))
            if m["kind"] == "finished":
                kl_stop.append(float(k[-512:].mean()))
        out["per_arm"][arm] = {
            "finished": len(fin), "not_finished": len(non),
            "lp_close_mean": float(np.mean([m["lp_close"] for m in fin])),
            "hazard_mean": float(np.mean([m["hazard"] for m in fin])),
            "close_top1_share": float(np.mean([m["close_top1"] for m in fin])),
            "max_p_think_mean": float(np.mean([m["max_p_think"] for m in non])) if non else None,
            "kl64_vs_ref_all_rows": float(np.mean(kl_all)), "kl64_vs_ref_stop_window": float(np.mean(kl_stop)),
            "per_trace": ms}
    keys_f = sorted(k for k, v in T[a.base].items() if v[0]["kind"] == "finished")
    keys_n = sorted(k for k, v in T[a.base].items() if v[0]["kind"] != "finished")
    for arm in arms:
        if arm == a.base:
            continue
        c = {}
        for name, keys, field in (("lp_close", keys_f, "lp_close"), ("hazard", keys_f, "hazard"),
                                  ("max_p_think", keys_n, "max_p_think")):
            if not keys:
                continue
            x = [T[a.base][k][0][field] for k in keys]; y = [T[arm][k][0][field] for k in keys]
            d, ci = boot_paired(x, y)
            gap = float(np.mean([T[a.ref][k][0][field] for k in keys]) - np.mean(x))
            clo = d / gap if gap else None
            c[name] = {"delta": d, "ci95": ci, "ref_gap": gap, "closure": clo,
                       "moves": bool(clo is not None and clo >= 0.5 and (ci[0] > 0 or ci[1] < 0))}
        out["contrast_vs_base"][arm] = c
    if a.teacher:
        wids = sorted(os.path.basename(f)[:-len(".safetensors")] for f in glob.glob(os.path.join(a.dumps, a.base, "pa", "*.safetensors")))
        doms = {}
        if a.pa_meta:
            meta = json.load(open(a.pa_meta))
            doms = {w["window_id"]: w["domain"] for w in meta["windows"]}
        tt = teacher_tops(a.teacher, wids)
        P = {arm: pa_measures(os.path.join(a.dumps, arm), tt, doms) for arm in arms}
        for arm in arms:
            p = P[arm]; o = {"kl64_mean": float(np.mean(p["kl64_per_window"])), "nll_mean": float(np.mean(p["nll_per_window"]))}
            if arm != a.base:
                o["kl64_delta_vs_base"] = boot_paired(P[a.base]["kl64_per_window"], p["kl64_per_window"])
                for dm in sorted({d for d in p["domain"] if d}):
                    idx = [i for i, d in enumerate(p["domain"]) if d == dm]
                    o[f"kl64_delta_{dm}"] = boot_paired([P[a.base]["kl64_per_window"][i] for i in idx],
                                                        [p["kl64_per_window"][i] for i in idx])
            out["pa"][arm] = o
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({arm: {k: v for k, v in out["per_arm"][arm].items() if k != "per_trace"} for arm in arms}, indent=1))
    print(json.dumps({arm: {m: (round(v["delta"], 4), round(v["closure"], 2) if v["closure"] is not None else None, v["moves"])
                            for m, v in c.items()} for arm, c in out["contrast_vs_base"].items()}, indent=1))


if __name__ == "__main__":
    main()
