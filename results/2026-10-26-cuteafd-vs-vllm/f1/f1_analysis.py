# F1 analysis (FOLLOWUPS.md): per arm, generated-row precision by bucket vs C1 (paired, same engine) and vs the vLLM
# mean (V1, V1r), plus speed vs F1-base per Block T cell. Standard library only.
import json, random, statistics, glob, os
R = "<run>"
def cli(path):
    return {(r["window"], r["position"]): r for r in json.load(open(path))["score"]["records"] if r["window"] != "legacy"}
def port(path):  # our port's records (V1, V1r): same record keys as his CLI
    d = json.load(open(path)); recs = d["records"] if isinstance(d, dict) else d
    return {(r["window"], r["position"]): r for r in recs if r["window"] != "legacy"}
C1 = cli(f"{R}/q/cli/pb-C1-rep2-prefill.json")
V = [port(f"{R}/q/score/final/pb/pb-V1.records.json"), port(f"{R}/q/score/final/pb/pb-V1r.records.json")]
arms = {"C1": C1}
for a in ("f1a", "f1b", "f1c", "f1d"):
    p = f"{R}/f1/pb-F1-{a}-prefill.json"
    if os.path.exists(p): arms[a] = cli(p)
gen = [k for k, r in C1.items() if r["role"] == "gen"]
def bucket(k): return C1[k]["bucket"]
def vmean(k, f): return sum(f(v[k]) for v in V) / len(V)
def paired(A, ks, f, ref):  # mean(A - ref) with window bootstrap
    wins = sorted({k[0] for k in ks}); byw = {w: [k for k in ks if k[0] == w] for w in wins}
    d = lambda kk: sum(f(A[k]) - ref(k) for k in kk) / len(kk)
    est = d(ks); rng = random.Random(7); bs = sorted(d([k for w in (rng.choice(wins) for _ in wins) for k in byw[w]]) for _ in range(2000))
    return est, bs[50], bs[1949]
F = {"kl": lambda r: r["kl"], "top1": lambda r: float(r["agree"]), "nll": lambda r: r["nll"]}
out = {"precision": {}, "speed": {}}
for a, A in arms.items():
    for b in ("all", "0-2K", "2-8K", "8-16K"):
        ks = [k for k in gen if b == "all" or bucket(k) == b]
        row = {m: sum(F[m](A[k]) for k in ks) / len(ks) for m in F}
        row["vs_vllm_mean"] = {m: paired(A, ks, F[m], lambda k, f=F[m]: vmean(k, f)) for m in F}
        if a != "C1": row["vs_C1"] = {m: paired(A, ks, F[m], lambda k, f=F[m]: f(C1[k])) for m in F}
        out["precision"].setdefault(a, {})[b] = row
def tcells(p):
    d = json.load(open(p)); c = {}
    for b in d["batches"]:
        if b["kind"] == "measured": c.setdefault((b["length"], b["content"], b["level"]), []).append(b["summary"])
    return c
base = tcells(f"{R}/f1/speed-F1-base.json")
for a in ("f1a", "f1b", "f1c", "f1d"):
    p = f"{R}/f1/speed-F1-{a}.json"
    if not os.path.exists(p): continue
    c = tcells(p)
    for k in sorted(base):
        if k in c:
            for m in ("decode_tok_s_per_stream_median", "aggregate_tok_s", "ttft_median_s"):
                rb = statistics.median(s[m] for s in base[k]); ra = statistics.median(s[m] for s in c[k])
                out["speed"].setdefault(a, {}).setdefault(f"{k[0]//1024}K {k[1]} c{k[2]}", {})[m] = ra / rb
json.dump(out, open(f"{R}/f1/F1-RESULTS.json", "w"), indent=1)
print("precision, generated rows (absolute; then paired vs vLLM mean and vs C1, 95% window bootstrap)")
for a, rows in out["precision"].items():
    for b, r in rows.items():
        vv = r["vs_vllm_mean"]; s = f"{a:4s} {b:6s} KL {r['kl']:.4f} top1 {r['top1']:.4f} nll {r['nll']:.4f} | vs vLLM KL {vv['kl'][0]:+.4f} [{vv['kl'][1]:+.4f},{vv['kl'][2]:+.4f}] top1 {vv['top1'][0]:+.4f}"
        if "vs_C1" in r: c = r["vs_C1"]; s += f" | vs C1 KL {c['kl'][0]:+.4f} [{c['kl'][1]:+.4f},{c['kl'][2]:+.4f}] top1 {c['top1'][0]:+.4f}"
        print(s)
print("\nspeed, ratio arm / F1-base (median of 2 reps)")
for a, cells in out["speed"].items():
    dec = [v["decode_tok_s_per_stream_median"] for v in cells.values()]; agg = [v["aggregate_tok_s"] for v in cells.values()]
    print(f"{a}: decode per-stream ratio median {statistics.median(dec):.3f} (range {min(dec):.3f}-{max(dec):.3f}); aggregate median {statistics.median(agg):.3f} ({min(agg):.3f}-{max(agg):.3f})")
