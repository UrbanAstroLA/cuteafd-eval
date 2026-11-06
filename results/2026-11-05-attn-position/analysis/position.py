#!/usr/bin/env python3
"""Exploratory (NOTE.md): does the divergence between arms, and the stop-decision difference, grow with position?
CPU, numpy (kld venv). Reads reduced dumps of the vLLM G2 screen and the CuteAFD core-swap step 2. Writes POSITION.json."""
import collections, glob, json, os, sys
import numpy as np

TL = "<tl-run>"; CS = "<cs-run>"
sys.path.insert(0, f"{TL}/analysis"); sys.path.insert(0, f"{TL}/capture/plugin")
from score_stop import load_reg, read, THINK  # noqa: E402

NB, SEED = 2000, 20261105
BINS = [0, 1024, 4096, 16384, 65536, 1 << 30]
reg = load_reg(f"{TL}/traces/reg")


def kl_rows(r, a):
    """top-64 KL(ref || arm) per row, arm value = floor (its 64th) when absent; vectorised score_stop.kl_top."""
    ir, lr = r["topk_ids"].astype(np.int64), r["topk_logprobs"].astype(np.float64)
    ia, la = a["topk_ids"].astype(np.int64), a["topk_logprobs"].astype(np.float64)
    n = ir.shape[0]; off = (np.arange(n, dtype=np.int64) << 20)[:, None]
    o = np.argsort(ia, 1); sa = np.take_along_axis(ia, o, 1) + off; sl = np.take_along_axis(la, o, 1)
    flat, fl = sa.ravel(), sl.ravel(); q = (ir + off).ravel()
    pos = np.clip(np.searchsorted(flat, q), 0, flat.size - 1); hit = flat[pos] == q
    floor = np.repeat(la.min(1), ir.shape[1])
    lav = np.where(hit, fl[pos], floor).reshape(ir.shape)
    return (np.exp(lr) * (lr - lav)).sum(1)


def load(root, arm):
    out = {}
    for f in sorted(glob.glob(f"{root}/{arm}/[ot][nr]/*.safetensors")):
        s = os.path.basename(os.path.dirname(f)); w = os.path.basename(f)[:-len(".safetensors")]
        t, sel = read(f); e = reg[(s, w)]
        t["lp_think"] = t["sel_logprobs"][:, sel.index(THINK)].astype(np.float64)
        out[f"{s}/{w}"] = (t, e["meta"]["kind"], str(e["meta"]["doc"]))
    return out


def slope(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float); x = x - x.mean()
    return float((x * (y - y.mean())).sum() / (x * x).sum()) if (x * x).sum() > 0 else np.nan


def cboot(vals, docs, fn=np.mean):
    """statistic and 95% interval, bootstrap over questions (clusters)."""
    by = collections.defaultdict(list)
    for v, d in zip(vals, docs):
        by[d].append(v)
    keys = sorted(by); rng = np.random.default_rng(SEED); bs = []
    for _ in range(NB):
        pick = rng.integers(0, len(keys), len(keys))
        bs.append(fn(np.concatenate([by[keys[i]] for i in pick])))
    return [float(fn(np.asarray(vals))), float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]


def contrast(R, A):
    """M1 per-trace slopes of KL on log2(position) and binned KL; M2 per-trace deltas (arm - ref) with close position."""
    sl, docs, binsum, bincnt = [], [], np.zeros(len(BINS) - 1), np.zeros(len(BINS) - 1)
    m2 = []
    for k, (r, kind, doc) in R.items():
        a = A[k][0]; assert np.array_equal(r["rows"], a["rows"])
        kl = kl_rows(r, a); x = np.log2(r["rows"].astype(float) + 1)
        sl.append(slope(x, kl)); docs.append(doc)
        b = np.digitize(r["rows"] + 1, BINS) - 1
        np.add.at(binsum, b, kl); np.add.at(bincnt, b, 1)
        if kind == "finished":
            m2.append((doc, float(np.log2(r["rows"][-1] + 1)), a["lp_think"][-1] - r["lp_think"][-1],
                       float(np.mean(a["lp_think"][-513:-1] - r["lp_think"][-513:-1])), float(kl.mean())))
    d2 = [m[0] for m in m2]; X = np.array([m[1] for m in m2]); Y = np.array([m[2] for m in m2]); H = np.array([m[3] for m in m2])
    idx = np.arange(len(m2))
    def sfn(Z):
        return lambda ii: slope(X[ii.astype(int)], Z[ii.astype(int)])
    return {"m1_slope_kl_per_log2pos": cboot(sl, docs),
            "m1_kl_by_bin": {f"{BINS[i]}-{BINS[i+1]}": (float(binsum[i] / bincnt[i]) if bincnt[i] else None, int(bincnt[i])) for i in range(len(BINS) - 1)},
            "m1_kl_mean_per_trace": cboot([float(kl_rows(R[k][0], A[k][0]).mean()) for k in R], docs),
            "m2_lp_close_delta": cboot(Y, d2), "m2_lp_close_slope_per_log2pos": cboot(idx.astype(float), d2, sfn(Y)),
            "m2_last512_logp_delta": cboot(H, d2), "m2_last512_slope_per_log2pos": cboot(idx.astype(float), d2, sfn(H)),
            "_per_trace_slopes": sl, "_docs": docs}


def diff(c1, c2, docs):
    """slope difference c1 - c2 per trace, clustered bootstrap."""
    return cboot(np.asarray(c1["_per_trace_slopes"]) - np.asarray(c2["_per_trace_slopes"]), docs)


out = {"note": "exploratory; see NOTE.md", "vllm": {}, "cuteafd": {}}
V = f"{TL}/dumps/runs"
vk6 = load(V, "k6"); vr = {}
for g in ["k6r2", "all", "mla_q_b", "mla_o", "kda_o", "kda_qkv", "mla_a", "shared_gu", "shared_down", "dense", "lm_head"]:
    vr[g] = contrast(vk6, load(V, g)); print("vllm", g, vr[g]["m1_slope_kl_per_log2pos"], vr[g]["m2_lp_close_slope_per_log2pos"], flush=True)
docs = vr["k6r2"]["_docs"]
for g, c in vr.items():
    if g != "k6r2":
        c["m1_slope_minus_k6r2"] = diff(c, vr["k6r2"], docs)
out["vllm"] = vr
C = f"{CS}/s2/runs"; ck6, ck6x, ck4, ck6r2 = (load(C, a) for a in ("C-K6", "C-K6x", "C-K4", "C-K6r2"))
cc = {"core": contrast(ck6, ck6x), "experts": contrast(ck6x, ck4), "launch": contrast(ck6, ck6r2)}
cc["core"]["m1_slope_minus_experts"] = diff(cc["core"], cc["experts"], cc["core"]["_docs"])
out["cuteafd"] = cc
for c in list(vr.values()) + list(cc.values()):
    c.pop("_per_trace_slopes"); c.pop("_docs")
json.dump(out, open("<ap-run>/POSITION.json", "w"), indent=1)
print("done")
