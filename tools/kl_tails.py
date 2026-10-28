#!/usr/bin/env python3
"""Tail and position statistics of the Block Q per-position scores (panels P-A, P-B and Q2).

    python3 tools/kl_tails.py                  # every per-position file present -> results/<run>/q/tails/<panel>-tails.json
    python3 tools/kl_tails.py --check          # recompute and compare with the published tails files; exit 1 on a difference
    python3 tools/kl_tails.py --pa FILE        # P-A input from elsewhere (its per-position file is not in this repository)
    python3 tools/kl_tails.py --run k4         # one run only: k325 (the K3.25 comparison) or k4; default both

Inputs are the per-position CSV files described in results/<run>/q/rows/README.md: one row per scored position, with the
window, the row index r (row r predicts token r+1), the context behind the scored token (r + 1 tokens), and per arm the
KL of that position, the engine's NLL of the actual next token and a top-1 agreement flag (1 = the engine's most likely
token is the reference's). Panels without a file are skipped.

What is computed, per panel and per arm:
  scored          windows, tokens per window, scored positions per window, total, context behind each scored position
                  (min / median / max over the selected positions). The last scored position of every window is its last
                  token, so tokens per window = largest context + 1.
  tails           per-position KL: mean, p50, p90, p99, p99.9 and max; top-1 agreement; confident top-1 (top-1 agreement
                  over positions where the reference's top probability is at least 0.5) where the panel records it.
  by_position     mean KL, p99 and p99.9 KL and top-1 per position band: P-A rows 0-255, 256-1023 and 1024-2046; P-B its
                  own length buckets (labels of the windows, so a bucket's context can run past its nominal bound); Q2
                  its 32K / 64K / 128K windows.
Selection: P-A all 2,047 positions of each window; P-B the generated positions (role "gen", the panel's primary rows);
Q2 all scored positions. Q2 has no reference: its KL is between two engines (disagreement, not distance from BF16).

Quantiles: linear interpolation between order statistics (Hyndman and Fan type 7, numpy's default): for sorted values
x[0..n-1] and q in [0, 1], h = (n - 1) q, value = x[floor h] + (h - floor h) (x[floor h + 1] - x[floor h]). Means use
math.fsum. The CSV values are rounded to 7 significant digits, so means differ from the published summaries (computed
from float64 rows) by about 1e-8; each tails file records that difference against the arm's published mean.

KL values are not comparable across panels: P-A is full-vocabulary KL against a BF16 teacher, P-B is tpurtell's coarse
top-1024-plus-tail KL (a lower bound on full-vocabulary KL), and NLL is per tokenizer and per text.

K4 run (results/2026-10-27-k4-vllm-cuteafd): the same panels and statistics, on the top-20 measures that run scored
(its q/rows/README.md): P-A KL20 (column kl20_<arm>), P-B KL_pb20 (klpb20_<arm>), Q2 KL20n between two arms
(kl20n_<a>_<b>). These are top-20 truncations, not full-vocabulary KL: never compare them with the K3.25 numbers as the
same quantity.
Standard library only (Python 3.10+).
"""
import argparse, csv, hashlib, json, math, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = "2026-10-26-cuteafd-vs-vllm"
Q = ROOT / "results" / RUN / "q"
ROWS, OUT = Q / "rows", Q / "tails"
QS = [("p50", 0.5), ("p90", 0.9), ("p99", 0.99), ("p99.9", 0.999)]

PANELS = {
    "pa": {"title": "P-A, BF16 teacher panel (brandonmusic)", "file": "pa-rows.csv",
           "metric": "full-vocabulary KL(teacher || engine), float64, nats", "selection": "all 2,047 positions of every window",
           "select": lambda r: True, "confident": "teacher_confident",
           "bands": [("rows 0-255", lambda r: int(r["row"]) <= 255), ("rows 256-1023", lambda r: 256 <= int(r["row"]) <= 1023),
                     ("rows 1024-2046", lambda r: int(r["row"]) >= 1024)],
           "summary": lambda a: Q / "pa" / f"pa-{a}.json", "summary_kl": lambda d: d["overall"]["kl"]["value"],
           "summary_alt": lambda a: Q / "pa-v2" / f"pa-{a}.json"},
    "pb": {"title": "P-B, tpurtell's cuteafd-fidelity panel (glm5_flash v2)", "file": "pb-rows.csv",
           "metric": "coarse KL(reference || engine) over the reference's top 1,024 ids plus one tail bin, nats "
                     "(tpurtell's rule; a lower bound on full-vocabulary KL)",
           "selection": "generated positions (role gen), the panel's primary rows", "select": lambda r: r["role"] == "gen",
           "confident": "ref_confident",
           "bands": [(b, (lambda b: lambda r: r["bucket"] == b)(b)) for b in ("0-2K", "2-8K", "8-16K")],
           "summary": lambda a: Q / "pb" / f"pb-{a}.json", "summary_kl": lambda d: d["summary"]["gen"]["overall"]["kl"]["value"]},
    "q2": {"title": "Q2, long human-written text (no reference)", "file": "q2-rows.csv",
           "metric": "NLL of the actual next token per engine; full-vocabulary KL between two engines (disagreement only)",
           "selection": "the last 4,096 positions of every window", "select": lambda r: True, "confident": None,
           "bands": [(b, (lambda b: lambda r: r["length"] == b)(b)) for b in ("32K", "64K", "128K")]},
}


RUN4 = "2026-10-27-k4-vllm-cuteafd"
Q4 = ROOT / "results" / RUN4 / "q"
ARM4 = {"Vr1": "V-r1", "Vr1b": "V-r1b", "Vr2": "V-r2", "Cr1": "C-r1"}     # CSV label -> the run's arm name
PANELS4 = {
    "pa": {**PANELS["pa"], "metric": "KL20: top-20 KL(teacher || engine) on the engine's 20 ids plus the actual token plus one "
           "rest cell, nats (a lower bound; about 0.8 of full-vocabulary KL on this panel)", "kl": "kl20_",
           "summary": lambda a: Q4 / "pa20.json", "summary_kl": lambda d, a: d["per_arm"][ARM4[a]]["kl_e20"]["value"],
           "summary_alt": None},
    "pb": {**PANELS["pb"], "metric": "KL_pb20: top-20 truncation of tpurtell's top-1,024-plus-tail rule, nats (about 0.98-0.99 "
           "of the published rule's KL on generated rows)", "kl": "klpb20_",
           "summary": lambda a: Q4 / "pb20.json", "summary_kl": lambda d, a: d["per_arm"][ARM4[a]]["gen"]["kl_pb20"]["value"]},
    "q2": {**PANELS["q2"], "metric": "NLL of the actual next token per arm; KL20n between two arms (top-20 intersection cells "
           "plus rest; disagreement only)"},
}
RUNS = {"k325": (RUN, PANELS, ROWS, OUT), "k4": (RUN4, PANELS4, Q4 / "rows", Q4 / "tails")}


def quantile(xs, q):
    """xs sorted ascending; type 7."""
    h = (len(xs) - 1) * q; lo = math.floor(h)
    return xs[lo] if lo + 1 >= len(xs) else xs[lo] + (h - lo) * (xs[lo + 1] - xs[lo])


def mmm(xs):
    s = sorted(xs)
    return {"min": s[0], "median": quantile(s, 0.5), "max": s[-1]}


def mean(xs): return math.fsum(xs) / len(xs)


def share_top(s, frac):
    """Share of the summed KL carried by the highest-KL `frac` of positions (s sorted ascending)."""
    k = max(1, int(len(s) * frac)); tot = math.fsum(s)
    return math.fsum(s[-k:]) / tot if tot else 0.0


def tails(kl):
    s = sorted(kl)
    return {"n": len(s), "kl_mean": mean(s), **{f"kl_{k}": quantile(s, q) for k, q in QS}, "kl_max": s[-1],
            "kl_share_top1pct": share_top(s, 0.01), "kl_share_top5pct": share_top(s, 0.05),
            "kl_share_top10pct": share_top(s, 0.10)}


def arms_of(header, prefix="kl_"):
    return [h[len(prefix):] for h in header if h.startswith(prefix) and h.count("_") == 1]


def read(path):
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        return rd.fieldnames, list(rd)


def scored(rows, sel):
    by_w = {}
    for r in rows: by_w.setdefault(r["window"], []).append(r)
    chosen = {w: [r for r in rs if sel(r)] for w, rs in by_w.items()}
    with_rows = [len(v) for v in chosen.values() if v]
    ctx = [int(r["context"]) for v in chosen.values() for r in v]
    return {"windows": len(by_w), "windows_with_selected_positions": len(with_rows),
            "tokens_per_window": mmm([max(int(r["context"]) for r in rs) + 1 for rs in by_w.values()]),
            "scored_positions_per_window": mmm([len(rs) for rs in by_w.values()]),
            "selected_positions_per_window": mmm(with_rows), "selected_positions_total": len(ctx), "context": mmm(ctx)}


def arm_stats(rows, arm, conf_col, klp="kl_"):
    kl = [float(r[f"{klp}{arm}"]) for r in rows]
    top1 = [int(r[f"top1_{arm}"]) for r in rows]
    out = {**tails(kl), "nll_mean": mean([float(r[f"nll_{arm}"]) for r in rows]), "top1": mean(top1)}
    if conf_col:
        c = [t for r, t in zip(rows, top1) if r[conf_col] == "1"]
        out["confident_top1"] = mean(c); out["confident_positions"] = len(c)
    return out


def panel_pa_pb(key, path, P=None):
    P = P or PANELS[key]; klp = P.get("kl", "kl_")
    header, rows = read(path)
    sel = [r for r in rows if P["select"](r)]
    arms = arms_of(header, klp)
    res = {"panel": P["title"], "metric": P["metric"], "selection": P["selection"], "scored": scored(rows, P["select"]),
           "arms": {}, "by_position": []}
    for a in arms:
        st = arm_stats(sel, a, P["confident"], klp)
        for get in (P["summary"], P.get("summary_alt")):
            sp = get(a) if get else None
            if sp and sp.exists():
                d = json.loads(sp.read_text())
                pub = P["summary_kl"](d, a) if "kl" in P else P["summary_kl"](d)
                st["published_kl_mean"] = pub; st["kl_mean_minus_published"] = st["kl_mean"] - pub
                break
        res["arms"][a] = st
    for label, f in P["bands"]:
        b = [r for r in sel if f(r)]
        res["by_position"].append({"band": label, "positions": len(b), "context": mmm([int(r["context"]) for r in b]),
                                   "arms": {a: {k: v for k, v in arm_stats(b, a, None, klp).items()
                                                if k in ("kl_mean", "kl_p99", "kl_p99.9", "top1")} for a in arms}})
    return res


def panel_q2(path):
    P = PANELS["q2"]
    header, rows = read(path)
    engines = [h[4:] for h in header if h.startswith("nll_")]
    def pair(col, agree, rs):
        rs = [r for r in rs if r[col] != ""]
        if not rs: return None
        return {**tails([float(r[col]) for r in rs]), "top1_agree": mean([int(r[agree]) for r in rs])}
    res = {"panel": P["title"], "metric": P["metric"], "selection": P["selection"], "scored": scored(rows, P["select"]),
           "nll_mean": {e: mean([float(r[f"nll_{e}"]) for r in rows]) for e in engines},
           "between_engines": {"KL(C1 || V1)": pair("kl_C1_V1", "top1_C1_V1", rows)},
           "within_engine": {"KL(V1 || V1r)": pair("kl_V1_V1r", "top1_V1_V1r", rows)}, "by_position": []}
    for label, f in P["bands"]:
        b = [r for r in rows if f(r)]
        res["by_position"].append({"band": label, "positions": len(b), "context": mmm([int(r["context"]) for r in b]),
                                   "nll_mean": {e: mean([float(r[f"nll_{e}"]) for r in b]) for e in engines},
                                   "KL(C1 || V1)": pair("kl_C1_V1", "top1_C1_V1", b)})
    return res


def panel_q2_k4(path):
    """K4 Q2: NLL per arm; KL20n between the vLLM launches and CuteAFD, and between the two vLLM launches (floor)."""
    P = PANELS4["q2"]
    header, rows = read(path)
    engines = [h[4:] for h in header if h.startswith("nll_")]
    def pair(col, agree, rs):
        return {**tails([float(r[col]) for r in rs]), "top1_agree": mean([int(float(r[agree])) for r in rs])}
    cross = [h for h in header if h.startswith("kl20n_") and not h.endswith("_Vr2") ]
    lab = lambda h: "KL20n({} || {})".format(*[ARM4[x] for x in h[6:].split("_")])
    res = {"panel": P["title"], "metric": P["metric"], "selection": P["selection"], "scored": scored(rows, P["select"]),
           "nll_mean": {ARM4[e]: mean([float(r[f"nll_{e}"]) for r in rows]) for e in engines},
           "between_engines": {lab(h): pair(h, "top1" + h[5:], rows) for h in cross},
           "within_engine": {lab("kl20n_Vr1_Vr2"): pair("kl20n_Vr1_Vr2", "top1_Vr1_Vr2", rows)}, "by_position": []}
    for label, f in P["bands"]:
        b = [r for r in rows if f(r)]
        res["by_position"].append({"band": label, "positions": len(b), "context": mmm([int(r["context"]) for r in b]),
                                   "nll_mean": {ARM4[e]: mean([float(r[f"nll_{e}"]) for r in b]) for e in engines},
                                   **{lab(h): pair(h, "top1" + h[5:], b) for h in cross + ["kl20n_Vr1_Vr2"]}})
    return res


def build(key, path, run="k325"):
    rid, panels = RUNS[run][:2]
    if run == "k4": res = panel_q2_k4(path) if key == "q2" else panel_pa_pb(key, path, panels[key])
    else: res = panel_q2(path) if key == "q2" else panel_pa_pb(key, path)
    pub = path.resolve().is_relative_to(ROOT) if hasattr(path, "resolve") else False
    return {"about": "Computed by tools/kl_tails.py from the per-position file named in 'input' (definitions in the tool's "
                     "docstring and results/" + rid + "/q/rows/README.md).",
            "input": (path.resolve().relative_to(ROOT).as_posix() if pub else f"{panels[key]['file']} (not in this repository)"),
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "input_published": pub,
            "quantiles": "type 7 (linear interpolation between order statistics)", **res}


def dump(obj): return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for k in PANELS: ap.add_argument(f"--{k}", type=Path, default=ROWS / PANELS[k]["file"], help=f"{k} per-position CSV (K3.25 run)")
    ap.add_argument("--out", type=Path, default=OUT, help="output directory (K3.25 run)")
    ap.add_argument("--run", choices=("k325", "k4", "all"), default="all")
    ap.add_argument("--check", action="store_true", help="compare with the published files instead of writing")
    a = ap.parse_args(argv)
    bad = 0
    for run, (rid, panels, rows_dir, out_dir) in RUNS.items():
        if a.run not in (run, "all"): continue
        for k in panels:
            src = getattr(a, k) if run == "k325" else rows_dir / panels[k]["file"]
            out = a.out if run == "k325" else out_dir
            if not src.exists(): print(f"{run} {k}: no per-position file ({src.name}); skipped"); continue
            text = dump(build(k, src, run)); dst = out / f"{k}-tails.json"
            if a.check:
                same = dst.exists() and dst.read_text() == text
                print(f"{run} {k}: {'reproduced' if same else 'DIFFERS from'} {dst.name}"); bad += not same
            else:
                dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(text); print(f"{run} {k}: wrote {dst.name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
