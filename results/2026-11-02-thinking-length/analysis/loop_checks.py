#!/usr/bin/env python3
"""Loop checks a and b (LOOP-CHECKS.md), and the per-sample table of G1b and G4. Post hoc, exploratory. Standard library only.

    python3 loop_checks.py --run <this run> --lie <local-inference-evals checkout> --out LOOP-CHECKS.json --samples samples.csv

a  Cap hits (completion tokens >= 327,680) on the seven knife-edge questions: every GPQA record of local-inference-evals
   (tools/analyze.py gpqa(); grouped by checkpoint, all engine versions together) against this run's G1b and G4 samples.
   Records without token counts (older runs) are left out of the rates; a second count uses an empty answer as a proxy
   for them.
   Two-sided Fisher exact test, K4 against K4-Core-K6 (G1b).
b  The looping investigation's early-stop detector on every G1b and G4 reasoning text: the last 30,000 characters are
   checked every 10,000 characters from 30,000 on (zlib ratio of their UTF-8 bytes), and a request stops after three
   consecutive checks below 0.10. Reported per reply: where it would fire, and the lowest check.
The reasoning texts stay local; the outputs hold counts, positions and ratios only.
"""
import argparse, csv, glob, json, math, os, re, sys, zlib

CAP = 327680
KNIFE = (186, 12, 81, 120, 86, 74, 13)
WIN, STEP, THR, RUN_OF = 30000, 10000, 0.10, 3
GOLD12 = "D"   # question 12 only, as in analyze_g4.py


def ratio(s):
    b = s.encode()
    return len(zlib.compress(b)) / len(b)


def detector(text):
    checks, below, fire = [], 0, None
    for end in range(WIN, len(text) + 1, STEP):
        r = ratio(text[end - WIN:end]); checks.append(r)
        below = below + 1 if r < THR else 0
        if below == RUN_OF and fire is None:
            fire = end
    return fire, (min(checks) if checks else None), len(checks)


def fisher2(a, n1, b, n2):
    """Two-sided Fisher exact p for a/n1 vs b/n2 (sum of tables no more likely than the observed one)."""
    k = a + b; N = n1 + n2
    def pmf(x): return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(N, k)
    p0 = pmf(a)
    return min(1.0, sum(pmf(x) for x in range(max(0, k - n2), min(k, n1) + 1) if pmf(x) <= p0 * (1 + 1e-9)))


def letter(content):
    m = re.findall(r"\(([A-D])\)|boxed\{[^}]*?\b([A-D])\b", content or "")
    return (m[-1][0] or m[-1][1]) if m else None


def samples(run):
    out = []
    for src, d in (("G1b", "g1b"), ("G4 6-bit core", "g4/k6"), ("G4 BF16 core", "g4/all")):
        for f in sorted(glob.glob(os.path.join(run, d, "doc*_rep*.json"))):
            r = json.load(open(f))
            txt = open(f[:-len(".json")] + ".reasoning.txt").read()
            fire, lo, n = detector(txt)
            out.append({"source": src, "doc": r["doc"], "rep": r["rep"], "seed": r["seed"], "finish_reason": r["finish_reason"],
                        "class": r["cls"], "completion_tokens": (r.get("usage") or {}).get("completion_tokens"),
                        "reasoning_chars": len(txt), "content_chars": r.get("content_chars"), "secs": r.get("secs"),
                        "correct": (letter(r.get("content")) == GOLD12) if r["doc"] == 12 else None,
                        "detector_fires_at_char": fire, "detector_lowest_check": round(lo, 4) if lo is not None else None,
                        "detector_checks": n})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True); ap.add_argument("--lie", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--samples", required=True)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(a.lie, "tools"))
    import analyze  # local-inference-evals
    recs = {"K3.25": [], "K4": []}
    for cfg, m in analyze.gpqa().items():
        recs["K3.25" if cfg.startswith("k3.25") else "K4"].append((cfg, m["rows"]))
    S = samples(a.run)
    A = {}
    for ck, runs in recs.items():
        rows = [r for _, rs in runs for r in rs]
        ke = [r for r in rows if r["doc_id"] in KNIFE]
        kt = [r for r in ke if r["completion_tokens"] is not None]; at = [r for r in rows if r["completion_tokens"] is not None]
        A[ck] = {"configs": [c for c, _ in runs], "configs_without_token_counts": [c for c, rs in runs if any(r["completion_tokens"] is None for r in rs)],
                 "knife_requests": len(kt), "knife_cap_hits": sum(r["completion_tokens"] >= CAP for r in kt),
                 "all_requests": len(at), "all_cap_hits": sum(r["completion_tokens"] >= CAP for r in at),
                 # proxy for records without token counts: an empty answer (where tokens were logged, 42 of 43 empty
                 # answers are cap hits and every cap hit is empty)
                 "knife_with_proxy": [sum(r["completion_tokens"] >= CAP if r["completion_tokens"] is not None else r["empty"] for r in ke), len(ke)],
                 "all_with_proxy": [sum(r["completion_tokens"] >= CAP if r["completion_tokens"] is not None else r["empty"] for r in rows), len(rows)]}
    logged = [r for _, rs in recs["K3.25"] + recs["K4"] for r in rs if r["completion_tokens"] is not None]
    proxy_check = {"cap_and_empty": sum(r["completion_tokens"] >= CAP and r["empty"] for r in logged),
                   "cap_not_empty": sum(r["completion_tokens"] >= CAP and not r["empty"] for r in logged),
                   "empty_not_cap": sum(r["completion_tokens"] < CAP and r["empty"] for r in logged)}
    for src in ("G1b", "G4 6-bit core", "G4 BF16 core"):
        ss = [s for s in S if s["source"] == src]
        A[src] = {"knife_requests": len(ss), "knife_cap_hits": sum((s["completion_tokens"] or 0) >= CAP for s in ss),
                  "by_doc": {d: sum((s["completion_tokens"] or 0) >= CAP for s in ss if s["doc"] == d) for d in sorted({s["doc"] for s in ss})}}
    g, k4 = A["G1b"], A["K4"]
    A["proxy_check"] = proxy_check
    A["fisher_k4_vs_k4core_k6_g1b"] = fisher2(k4["knife_cap_hits"], k4["knife_requests"], g["knife_cap_hits"], g["knife_requests"])
    q12_6 = sum(1 for s in S if s["doc"] == 12 and s["source"] in ("G1b", "G4 6-bit core") and (s["completion_tokens"] or 0) >= CAP)
    n12_6 = sum(1 for s in S if s["doc"] == 12 and s["source"] in ("G1b", "G4 6-bit core"))
    q12_b = A["G4 BF16 core"]["knife_cap_hits"]; n12_b = A["G4 BF16 core"]["knife_requests"]
    A["question_12"] = {"6-bit core": [q12_6, n12_6], "BF16 core": [q12_b, n12_b], "fisher": fisher2(q12_6, n12_6, q12_b, n12_b)}
    fin = [s for s in S if s["class"] == "ok"]
    B = {"rule": f"last {WIN} characters every {STEP} from {WIN}; stop after {RUN_OF} consecutive zlib ratios below {THR}",
         "finished_replies": len(fin), "finished_stopped": sum(s["detector_fires_at_char"] is not None for s in fin),
         "finished_lowest_check": min(s["detector_lowest_check"] for s in fin if s["detector_lowest_check"] is not None),
         "not_finished": [{k: s[k] for k in ("source", "doc", "rep", "class", "reasoning_chars", "detector_fires_at_char",
                                              "detector_lowest_check")} for s in S if s["class"] != "ok"]}
    json.dump({"about": "post hoc, exploratory (LOOP-CHECKS.md); computed after G4 was read", "a_cap_hits": A, "b_detector": B},
              open(a.out, "w"), indent=1)
    with open(a.samples, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(S[0])); w.writeheader(); w.writerows(S)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "configs"} if isinstance(v, dict) else v for k, v in A.items()}, indent=1))
    print(json.dumps(B, indent=1))


if __name__ == "__main__":
    main()
