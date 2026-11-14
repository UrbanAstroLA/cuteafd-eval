"""Named tables for the pages: each function takes the repository root and returns HTML built from published data."""
import json
from html import escape as E


def _j(repo, path):
    return json.loads((repo / path).read_text())


def htable(head, rows, num=()):
    th = "".join(f"<th>{h}</th>" for h in head)
    tb = "".join("<tr>" + "".join(f'<td{" class=n" if i in num else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'


def ci(v, nd=3, sign=True):
    f = (lambda x: f"{x:+.{nd}f}") if sign else (lambda x: f"{x:.{nd}f}")
    return (f"{f(v[0])} [{f(v[1])}, {f(v[2])}]").replace("-", "−")


# ------------------------------------------------------------------ CuteAFD v5.0.0 study (2026-11-10-context-probe)
CP = "results/2026-11-10-context-probe/SUMMARY.json"
ARMS4 = ("anchor", "hqa", "compact", "exlr8-k4")
ARMS5 = ARMS4 + ("k325-fp8",)
LENGTHS = (("4k", "4K"), ("16k", "16K"), ("64k", "64K"), ("128k", "127K"))


def _by_length(S, arm):
    return S["amendment_2"]["by_length"][arm] if arm == "k325-fp8" else {L: S["four_pass"]["by_length"][arm]["p1234"][L] for L, _ in LENGTHS}


def v5_configs(repo):
    S = _j(repo, CP)
    what = {"anchor": S["arms"]["anchor"]["what"], "hqa": S["arms"]["hqa"]["what"], "compact": S["arms"]["compact"]["what"],
            "exlr8-k4": "a different quantization of the whole model (EXLR8, 4-bit experts); added after the three-arm results were read",
            "k325-fp8": S["amendment_2"]["what"]}
    ck = {"anchor": S["arms"]["anchor"]["checkpoint"], "hqa": S["arms"]["hqa"]["checkpoint"], "compact": S["arms"]["compact"]["checkpoint"],
          "exlr8-k4": S["reference"]["checkpoint"], "k325-fp8": S["amendment_2"]["checkpoint"]}
    passes = {"anchor": "2 + 2 (+ eight-turn)", "hqa": "2 + 2 (+ eight-turn)", "compact": "2 + 2 (+ eight-turn)", "exlr8-k4": "2 + 2", "k325-fp8": "4"}
    bw = S["bits_per_weight"]["arms"]
    rows = [[f"<strong>{a}</strong>", E(what[a]), f"<code>{E(ck[a])}</code>", f"{bw[a]['bits_per_weight']:.2f}", passes[a]] for a in ARMS5]
    return htable(["Configuration", "What it is", "Checkpoint", "Bits per weight (stored)", "Single-message passes"], rows, num=(3,))


def v5_by_length(repo):
    S = _j(repo, CP)
    rows = []
    for a in ARMS5:
        bl = _by_length(S, a)
        rows.append([f"<strong>{a}</strong>"] + [f"{bl[L]['score'][0]:.3f} <span class=muted>[{bl[L]['score'][1]:.3f}, {bl[L]['score'][2]:.3f}]</span>" for L, _ in LENGTHS]
                    + [str(sum(bl[L]["unfinished"] for L, _ in LENGTHS))])
    return htable(["Configuration"] + [lab for _, lab in LENGTHS] + ["Unfinished of 960"], rows, num=(1, 2, 3, 4, 5))


def v5_unfinished(repo):
    S = _j(repo, CP)
    src = dict(S["endings"]["unfinished"]["by_arm_family_length"])
    src["k325-fp8"] = S["amendment_2"]["unfinished"]["by_family_length"]["k325-fp8"]
    rows = []
    for fam in ("join", "ledger", "trace"):
        for L, lab in LENGTHS:
            vals = [src[a][fam][L] for a in ARMS5]
            if any(vals):
                rows.append([fam, lab] + [str(v) for v in vals])
    return htable(["Family", "Length"] + list(ARMS5), rows, num=tuple(range(2, 7)))


def v5_bf16(repo):
    S = _j(repo, CP)
    arms = dict(S["bf16_distance"]["arms"])
    arms["k325-fp8"] = S["amendment_2"]["bf16_distance"]["arms"]["k325-fp8"]
    f = lambda v: f"{v[0]:.4f} <span class=muted>[{v[1]:.4f}, {v[2]:.4f}]</span>"
    rows = [[f"<strong>{a}</strong>", f(arms[a]["fidelity_set"]["kl"]), f(arms[a]["teacher_panel"]["kl"])] for a in ARMS5]
    return htable(["Configuration", "Fidelity set, coarse KL (to 14.4K)", "Teacher panel, full-vocabulary KL (2K)"], rows, num=(1, 2))


def v5_bits(repo):
    S = _j(repo, CP)
    bw = S["bits_per_weight"]["arms"]
    rows = [[f"<strong>{a}</strong>", f"{bw[a]['bits_per_weight']:.2f}", f"{100 * bw[a]['relative_to_bf16']:.1f}%", f"{bw[a]['stored_gib']:.1f}",
             f"{bw[a]['outside_routed_experts_bits_per_weight']:.2f}"] for a in ARMS5]
    return htable(["Configuration", "Bits per weight", "Of BF16", "GiB as stored", "Bits per weight outside the routed experts"], rows, num=(1, 2, 3, 4))


# ------------------------------------------------------------------ precision page
V4 = "results/2026-10-30-cuteafd-v4/SUMMARY.json"


def precision_teacher(repo):
    """Full-vocabulary KL from BF16 on the teacher panel: the one distance measure taken the same way in every study."""
    v4, cp = _j(repo, V4)["precision_fullvocab_pa"], _j(repo, CP)
    eng, ck = v4["cuteafd_minus_vllm"], v4["checkpoints_cuteafd"]
    b5 = dict(cp["bf16_distance"]["arms"])
    b5["k325-fp8"] = cp["amendment_2"]["bf16_distance"]["arms"]["k325-fp8"]
    f = lambda v: f"{v[0]:.4f} <span class=muted>[{v[1]:.4f}, {v[2]:.4f}]</span>"
    one = lambda x: f"{x:.4f}"
    run = lambda r, label: f'<a href="https://github.com/UrbanAstroLA/cuteafd-eval/tree/main/results/{r}">{label}</a>'
    R4, R5 = "2026-10-30-cuteafd-v4", "2026-11-10-context-probe"
    rows = [
        ["K3.25-v1", "3.25-bit (K3.25)", "BF16", "vLLM fork v0.9.2", one(eng["K3.25"]["kl"]["a"]), run(R4, "v4 run")],
        ["K3.25-Core-FP8", "3.25-bit (K3.25)", "FP8 projections, rest BF16; engine FP8 defaults", "CuteAFD v3.0.1, v4.0.0", one(eng["K3.25"]["kl"]["b"]), run(R4, "v4 run")],
        ["k325-fp8 (= K3.25-Core-FP8)", "3.25-bit (K3.25)", "as above", "CuteAFD v5.0.0", f(b5["k325-fp8"]["teacher_panel"]["kl"]), run(R5, "v5 study")],
        ["K4", "4-bit (K4)", "BF16", "vLLM fork v0.9.2", one(eng["K4"]["kl"]["a"]), run(R4, "v4 run")],
        ["K4", "4-bit (K4)", "BF16 converted to FP8 at load", "CuteAFD v4.0.0", one(eng["K4"]["kl"]["b"]), run(R4, "v4 run")],
        ["K4-Core-K6", "4-bit (K4-Core-K6)", "K6", "CuteAFD v4.0.0", one(ck["K4-Core-K6 - K4"]["kl"]["b"]), run(R4, "v4 run")],
        ["compact", "4-bit (K4-Core-K6)", "K6 core and head", "CuteAFD v5.0.0", f(b5["compact"]["teacher_panel"]["kl"]), run(R5, "v5 study")],
        ["hqa", "4-bit (K4-Core-K6)", "K6, BF16 q_b_proj and o_proj", "CuteAFD v5.0.0", f(b5["hqa"]["teacher_panel"]["kl"]), run(R5, "v5 study")],
        ["anchor", "4-bit (K4-Core-K6)", "BF16 core and head, FP8 conversions off", "CuteAFD v5.0.0", f(b5["anchor"]["teacher_panel"]["kl"]), run(R5, "v5 study")],
        ["exlr8-k4", "4-bit (EXLR8)", "its own (4-bit trellis and FP8 parts)", "CuteAFD v5.0.0", f(b5["exlr8-k4"]["teacher_panel"]["kl"]), run(R5, "v5 study")],
    ]
    return htable(["Checkpoint or configuration", "Routed experts", "Core as run", "Engine", "KL from BF16 [95% interval]", "Run"], rows, num=(4,))


# ------------------------------------------------------------------ data tables (rendered from published files, no prose)
def _n(x, nd=1):
    return "" if x is None else f"{x:,.{nd}f}"


def speed_cells(repo, path):
    """Per-cell speed from a T-COMPARE file: median decode, aggregate and first token per arm, ratios against the vLLM fork."""
    T = _j(repo, path)
    arms = [a for a in ("V", "C", "K") if any(a in c for c in T["cells"].values())]
    name = {"V": "vLLM fork", "C": "CuteAFD", "K": "K4-Core-K6 (CuteAFD)"}
    head = ["Input", "Content", "Streams"] + [f"{name[a]} decode" for a in arms] + [f"{name[a]} aggregate" for a in arms] \
        + [f"{name[a]} first token s" for a in arms] + [f"{name[a]} / vLLM aggregate" for a in arms if a != "V"]
    rows = []
    for key, c in T["cells"].items():
        inp, content, streams = key.strip("()").replace("'", "").split(", ")
        r = [f"{int(inp) // 1024}K", content, streams]
        r += [_n(c[a]["decode_med"]) if a in c else "" for a in arms]
        r += [_n(c[a]["aggregate"]) if a in c else "" for a in arms]
        r += [_n(c[a]["ttft_med"], 2) if a in c else "" for a in arms]
        r += [f'{c[a]["aggregate_ratio_vs_V"]:.2f} ({c[a]["aggregate_reading"]})' if a in c and "aggregate_ratio_vs_V" in c[a] else ""
              for a in arms if a != "V"]
        rows.append(r)
    band = ", ".join(f"{name[a]} {v:.4g}" for a, v in T.get("band", {}).items())
    return (htable(head, rows, num=set(range(3, len(head)))) +
            f'<p class="muted">From {path}: medians over three replicates; decode per stream, tok/s. Band: {E(band)}.</p>')


def kl_tails(repo, run):
    """Distribution of per-position KL from BF16, per arm and panel (tools/kl_tails.py output)."""
    rows = []
    for panel in ("pa", "pb", "q2"):
        p = repo / "results" / run / "q" / "tails" / f"{panel}-tails.json"
        if not p.exists():
            continue
        T = json.loads(p.read_text())
        for arm, a in T.get("arms", {}).items():      # Q2 has no BF16 reference, so no per-arm KL from BF16
            rows.append([E(T["panel"].split(",")[0]), E(arm), f'{a["n"]:,}'] +
                        [f'{a[k]:.4g}' if isinstance(a.get(k), (int, float)) else "" for k in
                         ("kl_mean", "kl_p50", "kl_p90", "kl_p99", "kl_p99.9", "kl_max", "kl_share_top1pct")])
    return htable(["Panel", "Arm", "Positions", "Mean", "p50", "p90", "p99", "p99.9", "Max", "Share in worst 1%"], rows,
                  num=set(range(2, 10))) + f'<p class="muted">From results/{run}/q/tails/ (computed by tools/kl_tails.py).</p>'


def pb_buckets(repo, path):
    """Fidelity-set generated positions by context bucket: both arms' levels and the paired difference."""
    P = _j(repo, path)["gen"]
    rows = []
    for b, v in [("all", P["overall"])] + sorted(P["by_bucket"].items()):
        for m in ("kl", "top1", "nll"):
            if m in v:
                x = v[m]
                rows.append([E(b), m, str(v.get("rows", "")), f'{x["A"]:.4f}', f'{x["B"]:.4f}', ci([x["B_minus_A"], *x["ci95"]], 4)])
    return htable(["Bucket", "Measure", "Rows", "A", "B", "B − A [95%]"], rows, num={2, 3, 4, 5}) + \
        f'<p class="muted">From {path}: A and B as named in the file; window-clustered bootstrap.</p>'


def v5_parts(repo):
    """Bits per weight by component, per configuration (v5 study)."""
    A = _j(repo, CP)["bits_per_weight"]["arms"]
    comps = list(next(iter(A.values()))["by_component"])
    rows = [[E(c)] + [f'{A[a]["by_component"][c]["bits_per_weight"]:.2f}' for a in A] for c in comps]
    rows.append(["<strong>all language-model weights</strong>"] + [f'<strong>{A[a]["bits_per_weight"]:.2f}</strong>' for a in A])
    return htable(["Component"] + [E(a) for a in A], rows, num=set(range(1, len(A) + 1))) + \
        '<p class="muted">From the v5 study SUMMARY.json /bits_per_weight; formats per component are in the same file.</p>'


def kl_tails_position(repo, run, panel="pa"):
    """KL from BF16 by position band within the window, per arm (tools/kl_tails.py output)."""
    T = _j(repo, f"results/{run}/q/tails/{panel}-tails.json")
    rows = []
    for b in T["by_position"]:
        for arm, a in b["arms"].items():
            rows.append([E(b["band"]), f'{b["context"]["median"]:g}', E(arm)] +
                        [f'{a[k]:.4g}' if isinstance(a.get(k), (int, float)) else "" for k in ("kl_mean", "kl_p99", "kl_p99.9", "top1")])
    return htable(["Band", "Median history", "Arm", "Mean KL", "p99", "p99.9", "Top-1"], rows, num={1, 3, 4, 5, 6}) + \
        f'<p class="muted">From results/{run}/q/tails/{panel}-tails.json.</p>'


def v5_bf16_buckets(repo):
    """Distance from BF16 on the fidelity set by context bucket and text block, per v5 configuration."""
    S = _j(repo, CP)
    arms = dict(S["bf16_distance"]["arms"])
    arms["k325-fp8"] = S["amendment_2"]["bf16_distance"]["arms"]["k325-fp8"]
    fs = {a: v["fidelity_set"] for a, v in arms.items()}
    rows = []
    for part in ("by_bucket", "by_block"):
        keys = list(next(iter(fs.values())).get(part, {}))
        for k in keys:
            rows.append([("bucket " if part == "by_bucket" else "block ") + E(k)] +
                        [ci(fs[a][part][k]["kl"], 4, sign=False) if k in fs[a].get(part, {}) else "" for a in fs])
    return htable(["Positions"] + [E(a) for a in fs], rows, num=set(range(1, len(fs) + 1))) + \
        '<p class="muted">Coarse KL from BF16 with 95% intervals; from the v5 study SUMMARY.json /bf16_distance.</p>'
