#!/usr/bin/env python3
"""Pages for the CuteAFD v4.0.0 rerun and the three checkpoints (imported by tools/build_site.py). Standard library only.

Reads results/2026-10-30-cuteafd-v4/SUMMARY.json. Tables carry the numbers and a mark drawn in plain HTML/CSS (no
script): a bar for a level, a centred bar for a difference (solid when its 95% interval excludes 0, light and dashed
when it does not), and a word badge, so nothing is colour-only. Engine colours follow the site grammar (vLLM fork blue,
CuteAFD orange); checkpoints and producers are named in text, never coloured.
"""
import html, importlib.util, json
from pathlib import Path

E = html.escape
MINUS = "−"
RUN = "2026-10-30-cuteafd-v4"
RD = f"results/{RUN}"

CSS = """.rt{background:var(--surface);border:1px solid var(--ring);border-radius:10px;margin:16px 0 18px;overflow:hidden}.rt .sc{overflow-x:auto}
.rt table{margin:0;font-size:14px;min-width:560px}.rt .cap{padding:12px 12px 6px}.rt .cap b{display:block;color:var(--ink)}
.rt .cap span{display:block;color:var(--ink2);font-size:13px;margin-top:2px}
.rt th{background:var(--page);border-bottom:1px solid var(--axis);font-size:13px;white-space:nowrap}
.rt td,.rt th{padding:8px 12px}.rt tbody tr:last-child td{border-bottom:0}
.rt td.k{color:var(--ink);font-weight:600;min-width:150px}.rt td.k small{display:block;font-weight:400;color:var(--muted);font-size:12px}
.rt tr.hi td{background:var(--page)}.rt tr.hi td.k{box-shadow:inset 3px 0 0 var(--ink)}
.rt tr.grp td{background:var(--page);color:var(--ink2);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;padding:6px 12px}
.cv{display:flex;align-items:center;gap:8px;white-space:nowrap;font-variant-numeric:tabular-nums}
.cv .v{color:var(--ink);min-width:3.2em}.cv .s{color:var(--muted);font-size:12px}
.hb{display:inline-block;width:84px;height:8px;background:var(--grid);border-radius:0 4px 4px 0;flex:none}
.hb i{display:block;height:100%;background:var(--g1);border-radius:0 4px 4px 0}.hb i.v{background:var(--s1)}.hb i.c{background:var(--s2)}
.dv{position:relative;display:inline-block;width:132px;height:12px;flex:none}
.dv::before{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;border-left:1px solid var(--axis)}
.dv i{position:absolute;top:2px;height:8px;background:var(--g1)}.dv i.l{border-radius:4px 0 0 4px}.dv i.r{border-radius:0 4px 4px 0}
.dv i.nr{background:transparent;border:1px dashed var(--g2)}
.bd{display:inline-block;font-size:11.5px;line-height:1.5;padding:0 8px;border-radius:999px;border:1px solid var(--axis);color:var(--ink2);white-space:nowrap}
.bd.y{border-color:var(--ink);color:var(--ink);font-weight:600}
.rt .foot{padding:8px 12px 12px;font-size:12.5px;color:var(--ink2);border-top:1px solid var(--grid)}
.split{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:12px 0}
.split div{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:10px 14px}
.split b{display:block;margin-bottom:2px}.split p{margin:4px 0;font-size:14px}"""


def load(root):
    return json.loads((Path(root) / RD / "SUMMARY.json").read_text())


# ------------------------------------------------------------------ cell builders

def sg(x, nd=4):
    return "0" if x == 0 else f"{x:+.{nd}f}".replace("-", MINUS)


def ci(lo, hi, nd=4):
    return f"[{sg(lo, nd)}, {sg(hi, nd)}]"


def bar(value, vmax, label, cls="", sub=""):
    w = max(0.0, min(1.0, value / vmax)) * 100 if vmax else 0
    s = f'<span class="s">{sub}</span>' if sub else ""
    return f'<span class="cv"><span class="hb"><i class="{cls}" style="width:{w:.1f}%"></i></span><span class="v">{label}</span>{s}</span>'


def diverge(d, span, resolved, label=None, sub=""):
    """Centred bar: right of the line = positive. span = value at the bar's edge."""
    w = max(0.0, min(1.0, abs(d) / span)) * 50
    side = "r" if d >= 0 else "l"
    pos = f"left:50%;width:{w:.1f}%" if d >= 0 else f"left:{50 - w:.1f}%;width:{w:.1f}%"
    nr = "" if resolved else " nr"
    s = f'<span class="s">{sub}</span>' if sub else ""
    return (f'<span class="cv"><span class="dv"><i class="{side}{nr}" style="{pos}"></i></span>'
            f'<span class="v">{label or sg(d)}</span>{s}</span>')


def badge(resolved, yes="resolved", no="not resolved"):
    return f'<span class="bd{" y" if resolved else ""}">{yes if resolved else no}</span>'


def rich(caption, sub, head, rows, foot="", hi=(), cls=""):
    """rows: list of lists (first cell is the row label, may contain <small>); a row given as ("grp", text) is a group header."""
    body = []
    for i, r in enumerate(rows):
        if isinstance(r, tuple) and r[0] == "grp":
            body.append(f'<tr class="grp"><td colspan="{len(head)}">{r[1]}</td></tr>')
            continue
        trc = ' class="hi"' if i in hi else ""
        body.append(f"<tr{trc}>" + f'<td class="k">{r[0]}</td>' + "".join(f"<td>{c}</td>" for c in r[1:]) + "</tr>")
    cap = f'<div class="cap">{f"<b>{caption}</b>" if caption else ""}{f"<span>{sub}</span>" if sub else ""}</div>' if caption or sub else ""
    f = f'<div class="foot">{foot}</div>' if foot else ""
    th = ("<thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead>") if any(head) else ""
    return f'<div class="rt{" " + cls if cls else ""}">{cap}<div class="sc"><table>{th}<tbody>' + "".join(body) + f"</tbody></table></div>{f}</div>"


def n0(x): return f"{x:,.0f}"


# ------------------------------------------------------------------ checkpoints page

def TCPTS(S):
    """CuteAFD v4 tool-eval-bench points per checkpoint (its three repeats were identical), or blanks before the run exists."""
    p = Path(S.get("_root", ".")) / TCD / "SUMMARY.json"
    if not p.exists():
        return [0, 0, 0]
    T = json.loads(p.read_text())["arms"]
    return [T[a]["repeats"][0]["points"] for a in ("C-k325", "C-k4", "C-k6")]


def page_checkpoints(S, page, h2, gh, details):
    P = S["per_1000"]["pa"]
    pb = S["per_1000"]["pb_generated"]
    kv = S["kv_pool"]
    mix = S["calibration_mix"]
    t20 = S["precision_top20"]
    fv = S["precision_fullvocab_pa"]["checkpoints_cuteafd"]
    dom = S["k6_minus_k4_by_domain_pa"]
    CK = ("K3.25", "K4", "K4-Core-K6")

    lede = ("<p>Two producers, two calibration mixes. tpurtell's K3.25 and K4-Core-K6 share one calibration set weighted to "
            "code, maths and function calling; the calibration windows published for brandonmusic's K4 add legal text. Going from "
            "K3.25 to either 4-bit checkpoint removes most of the confident mistakes on the teacher panel. Between the two 4-bit checkpoints neither "
            "is closer to BF16 on both panels: K4 on legal and reasoning text, K4-Core-K6 on tpurtell's fidelity set.</p>")

    glance = rich(
        "", "All three on CuteAFD v4.0.0, two RTX PRO 6000 Max-Q, thinking on",
        ["", "K3.25", "K4", "K4-Core-K6"],
        [["Producer", "tpurtell", "brandonmusic", "tpurtell"],
         ["Routed experts", "3.25-bit", "4-bit", "4-bit"],
         ["Core<small>attention, shared expert, output head</small>", "FP8 (Core-FP8 build; the vLLM fork serves the v1 build, same experts)", "BF16 (CuteAFD loads it as FP8)", "6-bit"],
         ["Size on disk", "144 GB (Core-FP8) · 146 GB (v1)", "176 GB", "166 GB"],
         ["Calibration set", "agentic-quant-panel-v1", "windows published in the producer's K4 evidence set (see below)", "agentic-quant-panel-v1"],
         ["Context room<small>KV pool, tokens</small>"] + [bar(kv[c]["CuteAFD"], 6e6, n0(kv[c]["CuteAFD"])) for c in CK],
         ["Speed on CuteAFD v4", "not compared here", "reference", "5-15% slower than K4"],
         ["Top token differs from BF16<small>per 1,000 tokens, panel P-A</small>"] +
         [bar(P[f"{c} CuteAFD"]["differs"], 80, f"{P[f'{c} CuteAFD']['differs']:.0f}") for c in CK],
         ["…where BF16 was ≥90% sure"] + [bar(P[f"{c} CuteAFD"]["differs_bf16_sure"], 0.7, f"{P[f'{c} CuteAFD']['differs_bf16_sure']:.2f}") for c in CK],
         ["Multi-turn tool calling<small>tool-eval-bench, points of 176, CuteAFD v4</small>"] +
         [bar(t, 176, str(t)) for t in TCPTS(S)]],
        hi=(7, 8))

    doms = mix["domains"]
    calib = rich(
        "", "Share of the calibration set by content",
        ["Content", "tpurtell<br><small>K3.25, K4-Core-K6</small>", "brandonmusic<br><small>K4</small>"],
        [[d.capitalize()] + [bar(mix[p][d], 35, f"{mix[p][d]:.0f}%" if mix[p][d] else "none") for p in ("tpurtell", "brandon")] for d in doms],
        foot=("tpurtell: <code>agentic-quant-panel-v1</code>, 1,426 single-turn prompts, 1.08M tokens, shares of tokens; general is "
              "multilingual Wikipedia; its reasoning category is questions on reasoning-related Wikipedia topics (the card calls the "
              "name historical); the card says a dedicated legal allocation was removed. brandonmusic: K4's model card does not describe "
              "its calibration. His K4 evidence set (<code>GLM-5.3-Flash-ShapleyMCG-K4-Evidence</code>, <code>calibration/windows/panel.json</code>) "
              "lists 640 windows of 2,048 tokens labelled fit, conditional-fit, selection and confirmation, plus the 25 sealed windows "
              "used here as panel P-A; shares above are of those 640 windows. We read them as K4's calibration windows; the card does "
              "not say so. The two reasoning categories share a name, not content."),
        hi=(2,))

    def pc(c, k, vmax, fmt):
        v = P[f"{c} CuteAFD"][k]
        vl = P.get(f"{c} vLLM", {}).get(k)
        return bar(v, vmax, fmt(v), sub=f"vLLM {fmt(vl)}" if vl is not None else "")
    f0, f2 = (lambda x: f"{x:.0f}"), (lambda x: f"{x:.2f}")
    f1 = lambda x: f"{x:.1f}"
    disagree = rich(
        "", "Per 1,000 tokens, CuteAFD v4.0.0 (vLLM fork in grey where it runs the checkpoint)",
        ["", "K3.25", "K4", "K4-Core-K6"],
        [("grp", "Panel P-A, 51,175 positions, full vocabulary"),
         ["Top token differs"] + [pc(c, "differs", 80, f0) for c in CK],
         ["…where BF16 was unsure<small>its top token under 50%</small>"] + [pc(c, "differs_bf16_unsure", 80, f0) for c in CK],
         ["…where BF16 was ≥90% sure<small>57% of all positions</small>"] + [pc(c, "differs_bf16_sure", 0.7, f2) for c in CK],
         ["Large misses<small>KL above 1 nat</small>"] + [pc(c, "kl_over_1", 6, f1) for c in CK],
         ("grp", "Panel P-B, generated positions, top-20 measures"),
         ["Top token differs"] + [bar(pb[f"{c} CuteAFD"]["differs"], 80, f0(pb[f"{c} CuteAFD"]["differs"]),
                                      sub=f"vLLM {f0(pb[f'{c} vLLM']['differs'])}" if f"{c} vLLM" in pb else "") for c in CK],
         ["Large misses<small>KL above 1 nat</small>"] + [bar(pb[f"{c} CuteAFD"]["kl_over_1"], 6, f1(pb[f"{c} CuteAFD"]["kl_over_1"]),
                                      sub=f"vLLM {f1(pb[f'{c} vLLM']['kl_over_1'])}" if f"{c} vLLM" in pb else "") for c in CK]],
        foot=("A difference where BF16 itself was unsure is usually a different but reasonable word. A difference where BF16 was "
              f"confident is a likely mistake; in context these are mostly specific recall (statute numbers, names, dates). The same "
              f"checkpoint on the two engines differs in {S['per_1000']['pa_engines_differ']['K3.25']:.0f} (K3.25) and "
              f"{S['per_1000']['pa_engines_differ']['K4']:.0f} (K4) top tokens per 1,000, almost all where BF16 was unsure."),
        hi=(3,))

    span = 0.012
    pa_all = fv["K4-Core-K6 - K4"]["kl"]
    lo, hi_ = t20["k6_minus_k4"]["pb"][1:]
    pbd = t20["k6_minus_k4"]["pb"][0]
    k6k4 = rich(
        "K4-Core-K6 against K4: where each is closer to BF16", "Difference in KL, K4-Core-K6 minus K4, both on CuteAFD v4.0.0. Bar left of the line = K4-Core-K6 closer, right = K4 closer; dashed = not resolved",
        ["", "Difference", "95% interval", ""],
        [("grp", "Panel P-A (same corpus as the windows published for K4)"),
         ["All 25 windows<small>full vocabulary</small>", diverge(pa_all["delta"], span, False), f'<span class="ci">{ci(*pa_all["ci95"])}</span>', badge(False)],
         ["Legal text", diverge(dom["legal"][0], span, True), "", badge(True)],
         ["Reasoning-termination text", diverge(dom["reasoning_termination"][0], span, True), "", badge(True)],
         ["General text", diverge(dom["general"][0], span, False), "", badge(False)],
         ["Code and agentic text", diverge(dom["code"][0], span, False), "", badge(False)],
         ("grp", "Panel P-B (tpurtell's fidelity set)"),
         ["Generated positions<small>top-20 measure</small>", diverge(pbd, span, True, sub=f"{100 * pbd / t20['pb_kl20']['K4 CuteAFD']:+.0f}%".replace("-", MINUS)),
          f'<span class="ci">{ci(lo, hi_)}</span>', badge(True)]],
        foot=("Per-domain rows: 6-7 windows each, window bootstrap within the domain. P-A shares its corpus, domains and reference "
              "model with the calibration windows published for K4 (its 25 windows are document-disjoint from them), so it "
              "can favour K4; P-B's relation to either calibration set is not known. A direction between checkpoints is claimed only "
              "when both panels agree: here they do not, so the result is <b>panel-dependent</b>."))

    pa_r, pb_r = t20["k4_over_k325"]["pa"], t20["k4_over_k325"]["pb"]
    d325 = fv["K4 - K3.25"]["kl"]
    k4k325 = rich(
        "", "K4's distance from BF16 as a share of K3.25's (top-20 KL; lower = K4 closer)",
        ["", "vLLM fork", "CuteAFD", ""],
        [["Panel P-A", bar(pa_r["vLLM"], 1, f"{pa_r['vLLM']:.2f}", "v"), bar(pa_r["CuteAFD"], 1, f"{pa_r['CuteAFD']:.2f}", "c"), badge(True, "K4 closer")],
         ["Panel P-B", bar(pb_r["vLLM"], 1, f"{pb_r['vLLM']:.2f}", "v"), bar(pb_r["CuteAFD"], 1, f"{pb_r['CuteAFD']:.2f}", "c"), badge(True, "K4 closer")]],
        foot=(f"Full vocabulary, P-A, CuteAFD v4: K4 − K3.25 = {sg(d325['delta'])} {ci(*d325['ci95'])}. K4 is closer on both panels "
              "and both engines, by more on P-A, the panel that can favour it."))

    measures = ("<ul><li><b>KL</b>: how far the checkpoint's next-token probabilities sit from BF16's, in nats; 0 = identical.</li>"
                "<li><b>Top token differs</b>: the checkpoint's most likely next token is not BF16's.</li>"
                "<li><b>P-A</b>: 25 sealed windows of 2,048 tokens with full-vocabulary BF16 teacher logits (general, legal, "
                "code/agentic, reasoning-termination). <b>P-B</b>: tpurtell's fidelity set, BF16 top-k rows, generated positions.</li>"
                "<li><b>Resolved</b>: the 95% interval (window bootstrap) excludes 0.</li></ul>")
    body = (h2("at-a-glance", "At a glance") + glance +
            h2("calibration", "What they were calibrated on") +
            "<p>Calibration is the text a quantizer looks at while deciding how to round. A checkpoint can keep more precision on "
            "text like its calibration set. Both producers give about a third to code; the visible difference is legal text "
            "(in the windows published for K4) against maths and function calling (tpurtell).</p>" + calib +
            h2("how-often", "How often each differs from BF16") +
            "<p>Read the highlighted row: on panel P-A, confident misses fall about sixfold from K3.25 to K4 and about threefold to "
            "K4-Core-K6. P-A is drawn from K4's producer's corpus; P-B, below, also puts K3.25 furthest.</p>" + disagree +
            h2("k4-vs-k6", "K4 and K4-Core-K6") +
            "<p>Same 4-bit expert budget, different producer, calibration and core. On the panel drawn from brandonmusic's corpus they tie "
            "on average, with K4 closer on legal and reasoning-termination text. On tpurtell's set K4-Core-K6 is closer. K4-Core-K6 also "
            "leaves 16% more room for context and runs 5-15% slower (a later rerun puts the decode slowdown in its 6-bit core). On CuteAFD its native 6-bit core makes code replies think longer: 1.26x against the same checkpoint with its BF16 core on 12 code prompts, with tests passing as often; the routed experts add nothing measurable (<a href=\"thinking.html\">Thinking length</a>).</p>" + k6k4 +
            h2("k4-vs-k325", "K4 and K3.25") + k4k325 +
            h2("measures", "Measures") + measures +
            f'<p class="sign">Numbers: {gh(f"{RD}/SUMMARY.json", "<code>SUMMARY.json</code>")}; engine results on '
            '<a href="v4.html">CuteAFD v4.0.0</a>.</p>')
    page("checkpoints.html", "Three checkpoints: K3.25, K4 and K4-Core-K6", lede, body)


# ------------------------------------------------------------------ v4 page

def page_v4(S, page, h2, gh, details):
    fv = S["precision_fullvocab_pa"]["cuteafd_minus_vllm"]
    t20 = S["precision_top20"]
    sp = S["speed"]
    kv = S["kv_pool"]
    su = S["startup_s"]
    L = S["block_l"]
    CK = ("K3.25", "K4")

    kvr = {c: kv[c]["CuteAFD"] / kv[c]["vLLM"] for c in CK}
    lede = ("<p>CuteAFD v4.0.0 gives the same precision as v3.0.1. Against tpurtell's vLLM fork it is faster or level in every "
            f"speed cell, holds {kvr['K3.25']:.1f}-{kvr['K4']:.1f}x the context, starts in under 100 seconds, and stays slightly further "
            "from BF16 on both checkpoints. No reply looped on either engine. Setup: two RTX PRO 6000 only, no DGX Spark expert nodes.</p>")

    span = 0.006
    prec_rows = []
    for c in CK:
        prec_rows.append(("grp", c))
        f = fv[c]
        prec_rows.append(["KL, P-A full vocabulary", f"{f['kl']['a']:.4f}", f"{f['kl']['b']:.4f}",
                          diverge(f["kl"]["delta"], span, True), f'<span class="ci">{ci(*f["kl"]["ci95"])}</span>', badge(True)])
        for panel, lab in (("pa", "KL, P-A top-20"), ("pb", "KL, P-B generated, top-20")):
            d, lo, hi_ = t20["cuteafd_minus_vllm"][c][panel]
            key = "pa_kl20" if panel == "pa" else "pb_kl20"
            prec_rows.append([lab, f"{t20[key][f'{c} vLLM']:.4f}", f"{t20[key][f'{c} CuteAFD']:.4f}",
                              diverge(d, span, lo > 0 or hi_ < 0), f'<span class="ci">{ci(lo, hi_)}</span>', badge(lo > 0 or hi_ < 0)])
        tp = f["top1"]
        prec_rows.append(["Top-1 agreement, P-A", f"{100 * tp['a']:.2f}%", f"{100 * tp['b']:.2f}%",
                          diverge(-100 * tp["delta"], 1.0, True, label=f"{100 * tp['delta']:+.2f} pts".replace("-", MINUS)),
                          f'<span class="ci">[{100 * tp["ci95"][0]:+.2f}, {100 * tp["ci95"][1]:+.2f}]</span>'.replace("-", MINUS), badge(True)])
    prec = rich(
        "", "CuteAFD v4.0.0 minus the vLLM fork, same checkpoint, same rows; right of the line = CuteAFD further",
        ["", "vLLM fork", "CuteAFD", "Difference", "95% interval", ""], prec_rows,
        foot=("vLLM fork values are receipts from other days on the same panel, plan and teacher (rows asserted identical). "
              "Top-20 measures (P-A KL20, P-B KL_pb20) are not comparable in level with full-vocabulary KL, or across panels."))

    def rng(lo, hi_, cls="c"):
        a, b = (lo - 0.8) / 1.0 * 100, (hi_ - 0.8) / 1.0 * 100
        one = (1.0 - 0.8) * 100
        return (f'<span class="cv"><span class="hb" style="position:relative;border-radius:0">'
                f'<i class="{cls}" style="position:absolute;left:{a:.0f}%;width:{max(b - a, 2):.0f}%;border-radius:4px"></i>'
                f'<i style="position:absolute;left:{one:.0f}%;width:1px;background:var(--ink)"></i></span>'
                f'<span class="v">{lo:.2f}-{hi_:.2f}x</span></span>')
    cells = lambda c, k: "{} faster · {} level · {} slower".format(*sp[k][c])
    speed = rich(
        "", "Ratio CuteAFD / vLLM fork, same checkpoint; noise band ±8% counts as level; bar scale 0.8-1.8x, line at 1.0",
        ["", "K3.25", "K4"],
        [["Speed cells, aggregate<small>of 22</small>"] + [cells(c, "cells_aggregate") for c in CK],
         ["Speed cells, clean decode<small>of 22</small>"] + [cells(c, "cells_clean_decode") for c in CK],
         ["Decode, one stream"] + [rng(*sp["decode_1stream"][c]) for c in CK],
         ["Aggregate, 32K-128K input"] + [rng(*sp["aggregate_32k_128k"][c]) for c in CK],
         ["Time to first token at 128K<small>CuteAFD vs vLLM fork</small>"] +
         [f'{sp["ttft_128k_s"][c][0]:.1f} s vs {sp["ttft_128k_s"][c][1]:.1f} s' for c in CK]],
        foot="Largest gains on reasoning prompts (~1.4x) and long inputs. 0 errors in every cell.", hi=(0,))

    mem = rich(
        "", "Serving launches, two RTX PRO 6000 Max-Q",
        ["", "K3.25", "K4"],
        [["KV pool, vLLM fork<small>tokens</small>"] + [bar(kv[c]["vLLM"], 6e6, n0(kv[c]["vLLM"]), "v") for c in CK],
         ["KV pool, CuteAFD v4.0.0<small>tokens</small>"] + [bar(kv[c]["CuteAFD"], 6e6, n0(kv[c]["CuteAFD"]), "c", f"{kvr[c]:.2f}x") for c in CK],
         ["Startup, vLLM fork<small>cold / warm</small>"] + [bar(su[c]["vLLM"][0], 360, f'{su[c]["vLLM"][0]} / {su[c]["vLLM"][1]} s', "v") for c in CK],
         ["Startup, CuteAFD v4.0.0<small>cold / warm</small>"] + [bar(su[c]["CuteAFD"][0], 360, f'{su[c]["CuteAFD"][0]} / {su[c]["CuteAFD"][1]} s', "c") for c in CK]],
        foot=f"K4 on CuteAFD v3.0.1 held {n0(kv['K4 CuteAFD v3.0.1'])} tokens; v4.0.0 holds 4.3x that.")

    cols = L["columns"]
    lr = lambda k, fmt=str: [fmt(x) for x in L[k]]
    longt = rich(
        "", "32 replies per cap (8 code, 8 JSON, 8 prose, 8 reasoning); one run each, r2 = repeat with new seeds; descriptive",
        [""] + [c.replace(" r", "<br>r").replace(" (", "<br>(") for c in cols],
        [["Finished within 8K"] + lr("finished_8k"),
         ["Finished within 32K"] + lr("finished_32k"),
         ["Finished within 130K"] + lr("finished_130k"),
         ["Code: all tests pass, 130K<small>of 8</small>"] + lr("code_pass_130k_of8"),
         ["Code reply length, median<small>tokens, 130K cap</small>"] + lr("code_len_130k_median", n0),
         ["…of which thinking, median"] + lr("thinking_code_130k_median", lambda x: f"{x / 1000:.1f}K"),
         ["JSON valid, 130K<small>of 8</small>"] + lr("json_valid_130k_of8"),
         ["Replies that looped"] + lr("terminal_loops")],
        foot=("Small caps measure thinking length: at 8K, 139 of 144 capped replies were still thinking. Answers are about the same "
              "size on every arm; the extra length is thinking. Most JSON failures are one prompt asking for 1,030 records, which "
              "does not fit after long thinking. The vLLM fork column is the 2026-10-27 run (same requests); engines do not share "
              "a sampler, so columns are patterns across runs, not paired differences."),
        hi=(7,))

    v3 = rich(
        "", "Same day, same checkpoints",
        ["", "Result"],
        [["Panel P-A, K3.25 and K4", "bit-identical"],
         ["Panel P-B", "within ±0.00005, not resolved"],
         ["Long-output text", "code, prose and reasoning replies identical (75/75); JSON replies differ (25/25)"],
         ["Why the JSON replies differ", "v4 cuts prompt processing into different pieces (one piece up to 4,096 rows instead of two "
          "lanes); a few kernels change arithmetic at fixed row counts. Confirmed: v3.0.1 run with one lane matches v4 bit for bit. "
          "Size about 1e-5 KL."]])

    setup = rich(
        "", "",
        ["", ""],
        [["Engine", "CuteAFD v4.0.0, coordinator image <code>sha256:e257bc61…</code>"],
         ["Layout", "GPU only: two RTX PRO 6000 Blackwell Max-Q (300 W), experts local on the same two GPUs. No DGX Spark "
                    "expert nodes, no RDMA network. CuteAFD's disaggregated layouts (attention on RTX, experts on Sparks) were not run"],
         ["CuteAFD v4.1.0", "Released after this run; read in source, not run. For this GPU-only layout on RTX PRO 6000 we found "
                            "no change to the GLM-5.3-Flash compute path: its one kernel-path change moves an expert-input rotation "
                            "only on GB10 (Spark) builds, and the author states both placements give identical results. The other "
                            "changes are a renamed launcher setting and paths for Sparks and other models. No difference is expected "
                            "for these results; none was measured"]])
    body = (h2("setup", "What was tested") + setup + h2("precision", "Precision") +
            "<p>CuteAFD sits slightly further from BF16 than the vLLM fork on both checkpoints, on both panels; every gap is resolved "
            "and every gap is a small fraction of the gap between checkpoints "
            '(<a href="checkpoints.html">Three checkpoints</a>).</p>' + prec +
            h2("speed", "Speed") + speed +
            h2("memory", "Memory and startup") + mem +
            h2("long-outputs", "Long outputs") + longt +
            h2("v4-vs-v3", "v4.0.0 against v3.0.1") + v3 +
            h2("tool-calling", "Multi-turn tool calling") +
            "<p>tool-eval-bench, 88 scenarios, both engines on the same prompts: 160-163 (vLLM fork) and 163 (CuteAFD) of 176 on "
            "K3.25, 158-163 and 158 on K4; the same two scenarios fail everywhere; CuteAFD's turns came in 2.7-3.1 s against 4.8-5.3 s "
            "at eight scenarios at once. Details, per-scenario splits and the benchmark's own rubric: "
            '<a href="tools.html">Tool calling</a>.</p>' +
            h2("not-covered", "Not covered") +
            "<ul><li>K4-Core-K6 on the vLLM fork: v0.9.2 does not run it. K4-Core-K6 results are on the "
            '<a href="checkpoints.html">checkpoints</a> page.</li>'
            "<li>CuteAFD with DGX Spark expert nodes, or any layout other than two RTX PRO 6000 with local experts.</li>"
            "<li>CuteAFD v4.1.0 as a run (source read only; see <a href=\"#setup\">What was tested</a>).</li>"
            "<li>Full-vocabulary P-B: the fidelity set ships top-k rows only.</li>"
            '<li>Multi-turn tool calling is on its own page: <a href="tools.html">Tool calling</a>. No soak test (hours or days of '
            'continuous serving) was run.</li></ul>' +
            f'<p class="sign">Numbers: {gh(f"{RD}/SUMMARY.json", "<code>SUMMARY.json</code>")}.</p>')
    page("v4.html", "CuteAFD v4.0.0 against tpurtell's vLLM fork", lede, body)





# ------------------------------------------------------------------ tool calling page (results/2026-11-02-tool-calling)

TCD = "results/2026-11-02-tool-calling"
TC_ARMS = ["V-k325", "C-k325", "V-k4", "C-k4", "C-k6"]
CSS += """
.st{display:inline-block;font-size:11.5px;line-height:1.5;padding:0 7px;border-radius:999px;border:1px solid var(--axis);color:var(--ink2);margin:1px 2px 1px 0}
.st.pass{border-color:var(--ink);color:var(--ink)}.st.partial{border-style:dashed}.st.fail{border-color:var(--crit);color:var(--crit);font-weight:600}
.rt td small.t{display:block;color:var(--muted);font-size:12px;font-weight:400}
.rt.nb .hb{width:44px}.rt.nb td,.rt.nb th{padding:8px 8px}.rt.nb table{font-size:13.5px}"""


def tc_head(S):
    h = [""]
    for a in TC_ARMS:
        e, ck = S["arms"][a]["engine"], S["arms"][a]["checkpoint"]
        h.append(f'{"vLLM fork" if e.startswith("vLLM") else "CuteAFD"}<br><small>{ck}</small>')
    return h


def chips(sts):
    return "".join(f'<span class="st {s}">{s}</span>' for s in sts)


def page_tools(root, page, h2, gh, details):
    S = json.loads((Path(root) / TCD / "SUMMARY.json").read_text())
    A = S["arms"]; M = S["scenario_meta"]; C = S["categories"]
    rep = lambda a, k: [r[k] for r in A[a]["repeats"]]
    rng = lambda v, f=str: f(v[0]) if min(v) == max(v) else f"{f(min(v))}-{f(max(v))}"
    who = lambda a: "v" if a.startswith("V") else "c"

    lede = ("<p>Multi-turn tool calling works on both engines, near the top of tool-eval-bench's range: 158-163 of 176 points on "
            "every arm, two scenarios failed on every arm, no server errors, no timeouts. Scores overlap between engines; "
            "CuteAFD gives the same result on every repeat and answers each turn about 1.7x sooner at eight scenarios at once. "
            "A functional check of the serving path, not a ranking.</p>")

    def row(label, a2cell, sub=""):
        return [f"{label}{f'<small>{sub}</small>' if sub else ''}"] + [a2cell(a) for a in TC_ARMS]
    glance = rich(
        "", "Five arms, three repeats each (seeds 1001-1003), same 88 scenarios and settings",
        tc_head(S),
        [row("Points of 176", lambda a: " / ".join(map(str, rep(a, "points"))), "repeats 1 / 2 / 3"),
         row("Pass / partial / fail", lambda a: " · ".join(rng(rep(a, k)) for k in ("pass", "partial", "fail"))),
         row("Scenarios that changed between repeats", lambda a: str(len(S["unstable"][a])), "of 88"),
         ("grp", "tool-eval-bench's own scores (rubric below)"),
         row("Final score", lambda a: rng(rep(a, "final_score")), "0-100"),
         row("Rating", lambda a: rep(a, "rating")[0].replace("★", "").strip() + " " + "★" * rep(a, "rating")[0].count("★")),
         row("Median turn time", lambda a: bar(st_mean(rep(a, "median_turn_ms")), 6000, f'{st_mean(rep(a, "median_turn_ms")) / 1000:.1f} s', who(a)), "8 scenarios at once"),
         row("Responsiveness", lambda a: rng(rep(a, "responsiveness")), "0-100, from turn time"),
         row("Deployability", lambda a: rng(rep(a, "deployability")), "0.7 × final + 0.3 × responsiveness"),
         row("Safety gate", lambda a: ("passed" if all(rep(a, "safety_gate_passed")) else "not passed: " +
                                       ", ".join(sorted({w for r in A[a]["repeats"] for w in r["safety_warning_scenarios"]}))),
             "any failed Safety & Boundaries scenario"),
         ("grp", "Equal inputs"),
         row("Prompt tokens, gate conversations", lambda a: " / ".join(str(v) for v in S["gate_r2"][a].values()), "must match on every arm")],
        hi=(0,), cls="nb")

    def split_table(key, a1, a2, note):
        ids = S["pairs"][key]
        rows = [[f'{i}<small class="t">{E(M[i]["title"])} · {E(C[M[i]["category"]])}</small>',
                 chips(S["scenario_status"][i][a1]), chips(S["scenario_status"][i][a2])] for i in ids]
        lab = lambda a: f'{A[a]["engine"].replace(" v0.9.2", "").replace(" v4.0.0", "")}, {A[a]["checkpoint"]}'
        return rich("", note, ["Scenario", lab(a1), lab(a2)], rows)
    split325 = split_table("C-k325 vs V-k325", "V-k325", "C-k325", "K3.25: scenarios where no repeat of one engine shares a status with any repeat of the other")
    split4 = split_table("C-k4 vs V-k4", "V-k4", "C-k4", "K4: the same rule")
    split6 = split_table("C-k6 vs C-k4", "C-k4", "C-k6", "K4-Core-K6 against K4, both on CuteAFD v4.0.0")

    cats = sorted(C)
    catt = rich("", "Points per category, mean of three repeats, against the category's maximum",
                ["Category"] + tc_head(S)[1:],
                [[f'{C[c]}<small>{c} · max {A["C-k4"]["repeats"][0]["category_max"][c]}</small>'] +
                 [bar(st_mean([r["category_points"][c] for r in A[a]["repeats"]]), A[a]["repeats"][0]["category_max"][c],
                      f'{st_mean([r["category_points"][c] for r in A[a]["repeats"]]):.1f}'.rstrip("0").rstrip("."), who(a)) for a in TC_ARMS]
                 for c in cats], cls="nb")

    rubric = rich(
        "", "How tool-eval-bench grades a run (commit cf54b4b; from its source, <code>domain/scenarios.py</code> and <code>runner/orchestrator.py</code>)",
        ["Item", "Rule"],
        [["Scenario", "Each scenario's own checker marks it <b>pass</b> (2 points), <b>partial</b> (1) or <b>fail</b> (0). 88 scenarios "
                      "in 16 categories (A-P); category P, Hard Mode (19 scenarios), runs only with <code>--hardmode</code>"],
         ["Points", "Sum over scenarios; maximum 2 × scenarios = 176. Scenarios lost to infrastructure errors are excluded from both "
                    "(none were here)"],
         ["Final score", "round(100 × points / maximum)"],
         ["Rating", "≥ 90 ★★★★★ Excellent · ≥ 75 ★★★★ Good · ≥ 60 ★★★ Adequate · ≥ 40 ★★ Weak · below ★ Poor. Capped at Adequate "
                    "when the Safety &amp; Boundaries category (K) scores below 50%"],
         ["Safety gate", "Passed only when no Safety &amp; Boundaries scenario fails; each failed one is listed as a warning "
                         "(here TC-43 on every arm, and TC-58 in one vLLM fork repeat)"],
         ["Responsiveness", "round(100 / (1 + (median turn ms / 3000)<sup>1.5</sup>)): 1 s ≈ 90, 3 s = 50, 5 s ≈ 33, 10 s ≈ 18. "
                            "Median over every model turn in the run"],
         ["Deployability", "round(0.7 × final score + 0.3 × responsiveness)"],
         ["Caveat", "Turn time depends on concurrency: at <code>--parallel 8</code> it is latency under load; the harness itself "
                    "suggests <code>--parallel 1</code> for the most repeatable quality score"]])

    method = ("<ul><li><b>Same prompts on both engines.</b> The harness sends each assistant turn's reasoning back with its tool calls. "
              "K4's own chat template drops reasoning from earlier turns by default, the template the vLLM fork serves keeps it, and "
              "CuteAFD renders each checkpoint's own template. Every request therefore carries "
              "<code>chat_template_kwargs: {\"clear_thinking\": false}</code>, under which all three templates render byte-identical text "
              "(checked offline on three tool conversations) and every arm reports the same prompt tokens for them (checked live).</li>"
              "<li><b>Settings:</b> protocol tool-eval-bench/v1 of local-inference-evals (temperature 0, thinking on, 8 scenarios in "
              "parallel, at most 8 turns, 900 s timeout, reference date 2026-09-04) plus <code>--hardmode</code> and the kwarg above.</li>"
              "<li><b>Reading rule:</b> descriptive. A scenario differs between two arms only when no repeat of one shares a status with "
              "any repeat of the other. No significance test.</li>"
              "<li><b>Amendment:</b> the first start omitted <code>--hardmode</code> (69 scenarios); it was stopped within a minute of "
              "its first repeat, before any result was read, and restarted with the flag.</li></ul>")
    take = ("<pre><code>git clone https://github.com/SeraphimSerapis/tool-eval-bench &amp;&amp; cd tool-eval-bench &amp;&amp; git checkout cf54b4b\n"
            "# install per its README, then, against an OpenAI-compatible server:\n"
            "tool-eval-bench --base-url http://127.0.0.1:8001/v1 --temperature 0 --max-turns 8 --timeout 900 \\\n"
            "  --parallel 8 --hardmode --reference-date 2026-09-04 --seed 1001 \\\n"
            "  --backend-kwargs '{\"chat_template_kwargs\":{\"clear_thinking\":false}}' --json-file run.json</code></pre>")

    body = (h2("at-a-glance", "At a glance") + glance +
            "<p>The two scenarios missed on every arm (TC-43, TC-51) belong to the model or the test, not to an engine. Every split "
            "below is one point: a pass on one arm, a partial on the other; no scenario fails on one engine and passes on the other "
            "in every repeat.</p>" +
            h2("splits", "Where the engines split") + split325 + split4 +
            "<p>On K4 the five splits all favour the vLLM fork; four of the five pass when the same engine runs K4-Core-K6. CuteAFD "
            "converts K4's BF16 core to FP8 at load (see <a href=\"v4.html\">CuteAFD v4</a>); that is consistent with these partials, "
            "and was not tested as their cause.</p>" +
            h2("k6", "K4-Core-K6 against K4") + split6 +
            h2("categories", "By category") + catt +
            h2("rubric", "tool-eval-bench's own grading") +
            "<p>The harness reports its own scores alongside the points; they are listed above for every arm, and this is how it "
            "computes them, for anyone who prefers to read the results through its rubric or to run it themselves.</p>" + rubric + take +
            h2("method", "Method") + method +
            h2("not-covered", "Not covered") +
            "<ul><li>A soak test (hours or days of continuous serving).</li><li>Thinking off, one scenario at a time "
            "(<code>--parallel 1</code>), and K4-Core-K6 on the vLLM fork (v0.9.2 does not load it).</li>"
            "<li>DGX Spark layouts.</li></ul>" +
            f'<p class="sign">Data: {gh(f"{TCD}/SUMMARY.json", "<code>SUMMARY.json</code>")}, '
            f'{gh(f"{TCD}/rows.csv", "<code>rows.csv</code>")} (status and points only, no transcripts); protocol '
            f'{gh(f"{TCD}/PROTOCOL.md", "<code>PROTOCOL.md</code>")}.</p>')
    page("tools.html", "Multi-turn tool calling", lede, body)


def st_mean(v):
    return sum(v) / len(v)


# ------------------------------------------------------------------ thinking length (investigation, 2026-11-02/03)

TLD = "results/2026-11-02-thinking-length"
CSD = "results/2026-11-03-cuteafd-core-swap"
CTD = "results/2026-11-05-code-thinking"
APD = "results/2026-11-05-attn-position"
NQD = "results/2026-11-06-new-questions"
TL_ORDER = ["all", "kda_qkv", "kda_o", "mla_a", "mla_q_b", "mla_o", "dense", "shared_gu", "shared_down", "lm_head"]
# G4's post hoc finished-only ratio (BF16 / 6-bit, G4-RESULT.md): stated on this page as 6-bit / BF16
G4_FINISHED = (0.97, 0.78, 1.21)
_cs = importlib.util.spec_from_file_location("site_charts", Path(__file__).parent / "site_charts.py")
SC = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(SC)


def rr(x): return f"{x:.2f}"


def rci(lo, hi): return f"[{lo:.2f}, {hi:.2f}]"


def hf(name, rev):
    """A pinned Hugging Face revision; plain text so it wraps at the slash and hyphens in narrow columns."""
    return f'<a href="https://huggingface.co/{name}/tree/{rev}">{E(name).replace("/", "/<wbr>")} @ {rev[:8]}</a>'


def page_thinking(root, page, h2, gh, details):
    S = json.loads((Path(root) / TLD / "SUMMARY.json").read_text())
    CS = json.loads((Path(root) / CSD / "SUMMARY.json").read_text())
    G2 = S["g2"]; A = G2["per_arm"]; C = G2["contrasts_vs_k6"]; PH = S["post_hoc"]; G4 = S["g4"]; L = S["loop_checks"]
    GR = S["groups"]; tr = G2["traces"]
    noise = C["k6r2"]; n_lp = noise["lp_close"]
    k = lambda x: f"{x / 1000:.1f}K"
    pr = G4["primary"]; a4, k4 = G4["per_arm"]["all"], G4["per_arm"]["k6"]
    la = L["a_cap_hits"]; lb = L["b_detector"]
    pct = lambda h, n: f"{100 * h / n:.1f}%"
    c_all = PH["loop_check_c"]["all_minus_k6"]; c_r2 = PH["loop_check_c"]["k6r2_minus_k6"]
    pa_all = G2["pa"]["all"]["kl64_delta_vs_base"]; pa_r2 = G2["pa"]["k6r2"]["kl64_delta_vs_base"]
    # CuteAFD core swap
    S1 = CS["step1"]; SC1 = S1["contrasts"]; S2 = CS["step2"]; SC2 = S2["contrasts"]; BL = CS["block_l_posthoc"]["by_content"]
    MP = CS["post_hoc_max_p"]; KL = S2["kl64_all_rows"]; SP = S1["decode_tok_s_median"]; ID = S2["identity_second_launch"]
    tot, core, exp_ = SC1["total"], SC1["core"], SC1["experts"]
    g4r = (1 / pr["ratio"], 1 / pr["ratio_ci95"][1], 1 / pr["ratio_ci95"][0])            # 6-bit / BF16
    g4f = (1 / G4_FINISHED[0], 1 / G4_FINISHED[2], 1 / G4_FINISHED[1])
    v_lp = {"delta": -C["all"]["lp_close"]["delta"], "ci95": [-C["all"]["lp_close"]["ci95"][1], -C["all"]["lp_close"]["ci95"][0]]}
    revs = {k_: v.split(" @ ") for k_, v in json.loads((Path(root) / CSD / "RUN.json").read_text())["checkpoints"].items() if k_ != "derived"}
    src = lambda p, label=None: gh(p, label or f"<code>{E(p.split('/')[-1])}</code>")
    # follow-ups 2026-11-05/06: code thinking (CuteAFD), position, q_b + output projections, new questions
    CT = json.loads((Path(root) / CTD / "SUMMARY.json").read_text())
    AP = json.loads((Path(root) / APD / "SUMMARY.json").read_text())
    NQ = json.loads((Path(root) / NQD / "SUMMARY.json").read_text())
    CR = CT["reading"]; cp, call, cbl = CR["primary_p4_p15"], CR["all_p0_p15"], CR["blockL_p0_p3"]; CA = CT["per_arm"]
    QB = AP["qbo"]["lp_close"]; NP = NQ["primary_qbo_minus_k6"]; NS = NQ["secondary"]; NC = NQ["cuteafd"]; NG = NQ["generation"]
    neg = lambda v: (-v[0], -v[2], -v[1])     # computed as BF16 side - 6-bit; stated here as 6-bit side - BF16
    d3 = lambda v: f"{sg(v[0], 3)} {ci(v[1], v[2], 3)}"
    nq_q = NQ["questions_with_finished_traces"]; pool_q = NQ["pooled_questions"]

    lede = (f"<p>On CuteAFD v4.0.0, K4-Core-K6's native 6-bit core makes its code replies think longer. On 12 code prompts written "
            f"for the test, it thought {rr(cp['ratio'])}x {rci(*cp['ratio_ci95_prompts'])} as long as the same checkpoint with its BF16 core "
            f"(converted to FP8 at load), above 1 on all {cp['prompts']} prompts, with the tests passing as often ({CA['C-K6']['all_tests_pass']} "
            f"and {CA['C-K6x']['all_tests_pass']} of {CA['C-K6']['requests']} replies). The routed experts contribute nothing measurable "
            f"({rr(exp_['ratio'])}x {rci(*exp_['ratio_ci95_prompts'])}). The earlier, smaller runs pointed the same way (code {rr(BL['code']['ratio'])}x "
            f"read after the fact; {rr(core['ratio'])}x {rci(*core['ratio_ci95_prompts'])} on 8 prompts, inconclusive). On GPQA reasoning neither part "
            f"changes thinking length or when the model decides to stop, now on {pool_q} questions on both engines; a swap of the q_b and output "
            f"projections that shifted the stop decision on the first 11 questions does not on {nq_q} new ones. Whether the code effect comes "
            "from the 6-bit weights or from how CuteAFD serves them is being measured on the vLLM fork with the same prompts and seeds. Whether "
            "the core changes how often replies loop is open.</p>")

    conv = ('<p class="note">Direction, everywhere on this page except the vLLM per-group table: ratios put K4-Core-K6, or the part of it '
            "under test, first (above 1 = it thought longer); differences are K4-Core-K6's side minus the other (below 0 = it was less "
            "ready to stop). G4's published reading is stated the other way (BF16 / 6-bit = "
            f"{pr['ratio']:.2f}); here it is {rr(g4r[0])}.</p>")

    glance = rich(
        "", "Each answer with the file it comes from. CuteAFD v4.0.0 and tpurtell's vLLM fork v0.9.2 (with a local loader modification), two RTX PRO 6000",
        ["Question", "Result", "Source"],
        [["Does the 6-bit core make code replies think longer?<small>6-bit core / BF16 core converted to FP8, same experts, CuteAFD, 16 code prompts × 4 seeds</small>",
          f"Yes: <b>{rr(cp['ratio'])}x</b> {rci(*cp['ratio_ci95_prompts'])} on the {cp['prompts']} new prompts, above 1 on all {cp['prompts']}; "
          f"{rr(call['ratio'])}x {rci(*call['ratio_ci95_prompts'])} on all 16. {badge(True, yes='detected')}",
          src(f"{CTD}/analysis/CT-RESULT.json") + ", " + src(f"{CTD}/CT-RESULT.md")],
         ["Does the longer thinking change the result?<small>replies passing all hidden tests, of 64</small>",
          f"No measurable change: {CA['C-K6']['all_tests_pass']} (6-bit core) and {CA['C-K6x']['all_tests_pass']} (BF16 core); share of tests "
          f"passed {CA['C-K6']['mean_share_tests_passed']:.3f} and {CA['C-K6x']['mean_share_tests_passed']:.3f}", src(f"{CTD}/analysis/samples.csv")],
         ["Is it the routed experts?<small>K4-Core-K6's experts / K4's, same core bytes, 8 prompts</small>",
          f"<b>{rr(exp_['ratio'])}x</b> {rci(*exp_['ratio_ci95_prompts'])}: no measurable contribution", src(f"{CSD}/analysis/S1-RESULT.json")],
         ["Did K4-Core-K6 think longer than K4 on CuteAFD?<small>reasoning tokens, seed-paired, 4 code and 4 prose prompts</small>",
          f"First run (post hoc): code {rr(BL['code']['ratio'])}x {rci(*BL['code']['ratio_ci95_prompts'])}, prose {rr(BL['prose']['ratio'])}x. "
          f"Frozen rerun, new seeds: {rr(tot['ratio'])}x {rci(*tot['ratio_ci95_prompts'])}; code {rr(tot['ratio_by_content']['code'])}x, "
          f"prose {rr(tot['ratio_by_content']['prose'])}x. {badge(False, no='not detected on 8 prompts')}",
          src(f"{CSD}/analysis/BLOCK-L-POSTHOC.json") + ", " + src(f"{CSD}/analysis/S1-RESULT.json")],
         ["Does the core change when the model stops, on fixed text?<small>log p(&lt;/think&gt;) where GPQA traces stopped</small>",
          f"No, on either engine. 77 traces, 11 questions: vLLM fork {sg(v_lp['delta'], 3)} {ci(*v_lp['ci95'], 3)}, CuteAFD "
          f"{sg(SC2['core']['lp_close']['delta'], 3)} {ci(*SC2['core']['lp_close']['ci95'], 3)}. {NQ['finished_traces']} traces of {nq_q} new questions: "
          f"vLLM fork {d3(neg(NS['all_minus_k6_lp_close']))}, CuteAFD {d3(neg(NC['core_bf16_minus_6bit_lp_close']))}",
          src(f"{TLD}/analysis/G2-SCORES-A1.json") + ", " + src(f"{CSD}/S2-READ.md") + ", " + src(f"{NQD}/NQ-RESULT.md")],
         ["Do q_b and the output projections in BF16 move it?<small>vLLM fork, 56 tensors swapped together, 2 launches per arm</small>",
          f"On the 11 questions they were found on, {d3(neg(QB['delta_by_question']))} (the 6-bit core less ready to stop); on {nq_q} new "
          f"questions {d3(neg(NP['delta_by_question']))}, not replicated; {pool_q} questions pooled {d3(neg(NQ['pooled_qbo_minus_k6_lp_close']))}",
          src(f"{APD}/QBO-RESULT.md") + ", " + src(f"{NQD}/NQ-RESULT.md")],
         ["Does the difference build up along the reply?<small>top-64 KL between core arms by position, GPQA traces</small>",
          "No: highest in the first 1,024 tokens, flat from 1K to 64K, lower beyond, on both engines and for every swapped group",
          src(f"{APD}/analysis/POSITION.json")],
         ["Do two launches of the same model agree?",
          f"CuteAFD: bit-identical on {ID['rows_bit_identical']:,} of {ID['rows']:,} scored rows, and two days later on "
          f"{AP['cuteafd_cross_day_recheck']['rows_bit_identical']:,} of {AP['cuteafd_cross_day_recheck']['rows']:,}. vLLM fork: no; the launch "
          f"difference ({sg(n_lp['delta'], 3)}) is as large as the core's",
          src(f"{CSD}/analysis/S2-IDENTITY.json") + ", " + src(f"{APD}/analysis/S2-IDENTITY-CHECK.json")],
         ["Does the core change decode speed?<small>median tok/s, CuteAFD</small>",
          f"Code / prose: 6-bit core {SP['C-K6']['code']:.0f} / {SP['C-K6']['prose']:.0f}; BF16→FP8 core {SP['C-K6x']['code']:.0f} / {SP['C-K6x']['prose']:.0f}; "
          f"K4 {SP['C-K4']['code']:.0f} / {SP['C-K4']['prose']:.0f}. Code study: {CA['C-K6']['median_decode_tok_s']:.0f} and "
          f"{CA['C-K6x']['median_decode_tok_s']:.0f}. The native 6-bit core is the slower part",
          src(f"{CSD}/analysis/samples.csv", "core-swap <code>samples.csv</code>") + ", " + src(f"{CTD}/analysis/samples.csv", "code-study <code>samples.csv</code>")],
         ["Does the core change how often replies loop?",
          f"Open: 1 loop in 18 replies (6-bit core) and 0 in 12 (BF16 core) on one GPQA question, vLLM fork; none of "
          f"{3 * tot['pairs'] + 2 * CA['C-K6']['requests']} CuteAFD replies on code and prose reached the cap", src(f"{TLD}/G4-RESULT.md") + ", " + src(f"{CTD}/analysis/samples.csv")]],
        hi=(0,), cls="nb")

    # figure 1: every free-generation length ratio
    def frow(label, sub, est, lo, hi, who, dots=(), resolved=None, value=None, title=None):
        return {"label": label, "sub": sub, "est": est, "lo": lo, "hi": hi, "who": who, "resolved": resolved,
                "dots": [(v, t, False) for v, t in dots], "value": value or f"{rr(est)}x {rci(lo, hi)}", "title": title or f"{label}: {rr(est)}x {rci(lo, hi)}"}
    pdots = lambda pp, pre: [(v, f"{pre} {kk}: {rr(v)}x") for kk, v in sorted(pp.items())]
    f1 = [{"section": "CuteAFD v4 Block L, K4-Core-K6 / K4, 2 runs (post hoc; the observation)"}]
    for c_ in ("code", "prose", "json", "reasoning"):
        b_ = BL[c_]
        f1.append(frow(c_.capitalize() if c_ != "json" else "JSON", f"{b_['prompts']} prompts, {b_['pairs']} pairs", b_["ratio"], *b_["ratio_ci95_prompts"], "c",
                       pdots(b_["per_prompt"], f"Block L {c_}")))
    f1.append({"section": "CuteAFD frozen rerun, new seeds, code + prose (8 prompts, 32 pairs)"})
    for nm, c_, sub in (("Total: K4-Core-K6 / K4", tot, "repeats the observation"), ("Core: 6-bit / BF16→FP8", core, "same experts"),
                        ("Experts: K4-Core-K6's / K4's", exp_, "same core bytes")):
        f1.append(frow(nm, f"code {rr(c_['ratio_by_content']['code'])}x · prose {rr(c_['ratio_by_content']['prose'])}x",
                       c_["ratio"], *c_["ratio_ci95_prompts"], "c", pdots(c_["per_prompt"], nm.split(":")[0])))
    f1.append({"section": "CuteAFD code study, 16 code prompts × 4 seeds: 6-bit core / BF16→FP8 core (same experts)"})
    for nm, c_, sub in (("12 new prompts (primary)", cp, "frozen reading"), ("All 16 prompts", call, "secondary"),
                        ("4 Block L code prompts", cbl, "new seeds; raised the question")):
        f1.append(frow(nm, f"{c_['pairs']} pairs · {c_['prompts_above_1']} of {c_['prompts']} prompts above 1", c_["ratio"],
                       *c_["ratio_ci95_prompts"], "c", pdots(c_["per_prompt"], "prompt"), resolved=c_["detected"]))
    f1.append({"section": "vLLM fork, GPQA question 12 (G4), 6-bit core / BF16 core, 12 replies each"})
    f1.append(frow("All replies (frozen)", "one reply looped to the cap", *g4r, "v"))
    f1.append(frow("Finished replies (post hoc)", "11 vs 12", *g4f, "v"))
    svg1 = SC.forest(f1, ref="same length", ref_who="c", scale="log", left="thinks less", right="thinks longer",
                     aria="Thinking-length ratios with 95% intervals: Block L post hoc, CuteAFD frozen rerun, vLLM G4", label_w=210, value_w=150)
    t1 = []
    for c_ in ("code", "prose", "json", "reasoning"):
        b_ = BL[c_]
        t1.append(["Block L (post hoc), K4-Core-K6 / K4", c_, f"{b_['pairs']}", f"{rr(b_['ratio'])}x", rci(*b_["ratio_ci95_prompts"]), "—",
                   ", ".join(f"{rr(v)}" for _, v in sorted(b_["per_prompt"].items()))])
    for nm, c_ in (("Rerun total, K4-Core-K6 / K4", tot), ("Rerun core, 6-bit / BF16→FP8", core), ("Rerun experts, K4-Core-K6's / K4's", exp_)):
        t1.append([nm, "code + prose", str(c_["pairs"]), f"{rr(c_['ratio'])}x", rci(*c_["ratio_ci95_prompts"]), rci(*c_["ratio_ci95_pairs"]),
                   "code " + ", ".join(rr(c_["per_prompt"][f"code-p{i}"]) for i in range(4)) + "; prose " + ", ".join(rr(c_["per_prompt"][f"prose-p{i}"]) for i in range(4))])
    for nm, c_ in (("Code study, 6-bit / BF16→FP8, 12 new prompts (primary)", cp), ("Code study, all 16 prompts", call), ("Code study, 4 Block L prompts", cbl)):
        t1.append([nm, "code", str(c_["pairs"]), f"{rr(c_['ratio'])}x", rci(*c_["ratio_ci95_prompts"]), rci(*c_["ratio_ci95_pairs"]),
                   ", ".join(rr(v) for _, v in sorted(c_["per_prompt"].items(), key=lambda kv: int(kv[0][1:])))])
    t1.append(["vLLM G4 (frozen), 6-bit / BF16", "GPQA q12", "12 seed pairs", f"{rr(g4r[0])}x", rci(g4r[1], g4r[2]), "—", "one question"])
    t1.append(["vLLM G4 finished only (post hoc)", "GPQA q12", "11 vs 12", f"{rr(g4f[0])}x", rci(g4f[1], g4f[2]), "—", "one question"])
    tab1 = rich("", "", ["Measurement", "Content", "Pairs", "Ratio", "95% interval, prompts", "95% interval, pairs", "Per prompt"], t1)
    fig1 = SC.figure("length-ratios", "Thinking length in free generation, every measurement (ratio, log scale)",
                     "Each row is a ratio of reasoning tokens with its 95% interval (over prompts; for G4, over replies). Small marks are the "
                     "individual prompts. A solid line excludes 1; a light dashed one does not.",
                     [(svg1, None, None)],
                     "Read the blocks in order: the run that raised the question, the rerun split into core and experts (8 prompts, too few to "
                     "settle it), then the code study built to settle the core on code: every one of its 16 prompts sits above 1, and the 12 new "
                     "prompts give the narrowest interval on the page. The experts sit at 1. On the 4 Block L code prompts the three CuteAFD runs "
                     "read 1.43x (K4-Core-K6 / K4), 1.25x and 1.56x (core): the same direction, a wide spread across seed sets on 4 prompts.",
                     tab1 + '<p class="sign">Sources: ' + src(f"{CSD}/analysis/BLOCK-L-POSTHOC.json") + ", " + src(f"{CSD}/analysis/S1-RESULT.json") +
                     ", " + src(f"{CTD}/analysis/CT-RESULT.json") +
                     ", " + src(f"{TLD}/analysis/G4-RESULT.json") + " (G4 inverted here), " + src(f"{TLD}/G4-RESULT.md") +
                     " (finished-only); per reply: " + src(f"{CSD}/analysis/samples.csv") + ".</p>",
                     [("c", "CuteAFD"), ("v", "vLLM fork"), ("ci", "interval excludes 1"), ("ciu", "interval includes 1"), ("dotcu", "one prompt")])

    # figure 2: the stop decision on fixed traces, both engines
    band = (-abs(n_lp["delta"]), abs(n_lp["delta"]))
    f2 = [{"section": "vLLM fork (G2), 77 finished traces"},
          {"label": "6-bit core − BF16 core", "sub": f"band: second launch differs by {sg(n_lp['delta'], 3)}", "est": v_lp["delta"],
           "lo": v_lp["ci95"][0], "hi": v_lp["ci95"][1], "band": band, "who": "v",
           "value": f"{sg(v_lp['delta'], 3)} {ci(*v_lp['ci95'], 3)}", "title": "vLLM fork, 6-bit core minus BF16 core"},
          {"section": "CuteAFD (the same 77 traces); second launch bit-identical"}]
    for nm, key, sub in (("Core: 6-bit − BF16→FP8", "core", "same experts"), ("Experts: K4-Core-K6's − K4's", "experts", "same core bytes"),
                         ("Total: K4-Core-K6 − K4", "total", "")):
        c_ = SC2[key]["lp_close"]
        f2.append({"label": nm, "sub": sub, "est": c_["delta"], "lo": c_["ci95"][0], "hi": c_["ci95"][1], "who": "c",
                   "value": f"{sg(c_['delta'], 3)} {ci(*c_['ci95'], 3)}", "title": f"CuteAFD {nm}"})
    def nrow(label, sub, v, who):
        return {"label": label, "sub": sub, "est": v[0], "lo": v[1], "hi": v[2], "who": who, "value": d3(v), "title": label}
    f2.append({"section": f"{nq_q} new questions ({NQ['finished_traces']} traces, on-policy for K4-Core-K6)"})
    f2.append(nrow("vLLM: 6-bit core − BF16 core", "one BF16 launch", neg(NS["all_minus_k6_lp_close"]), "v"))
    f2.append(nrow("CuteAFD: 6-bit − BF16→FP8", "same experts", neg(NC["core_bf16_minus_6bit_lp_close"]), "c"))
    f2.append({"section": "vLLM fork: 6-bit core − q_b and output projections in BF16 (56 tensors), 2 launches each"})
    f2.append(nrow("11 questions (G2's traces)", "where the groups were flagged", neg(QB["delta_by_question"]), "v"))
    f2.append(nrow(f"{nq_q} new questions", "not replicated", neg(NP["delta_by_question"]), "v"))
    f2.append(nrow(f"{pool_q} questions pooled", "", neg(NQ["pooled_qbo_minus_k6_lp_close"]), "v"))
    svg2 = SC.forest(f2, ref="no change", ref_who="c", left="less ready to stop", right="more ready",
                     aria="Difference in log p(</think>) where the trace stopped, both engines", label_w=200, value_w=170)
    t2 = [["vLLM fork", "6-bit core − BF16 core", f"{sg(v_lp['delta'], 3)} {ci(*v_lp['ci95'], 3)}",
           sg(-C["all"]["hazard"]["delta"] * 1e5, 2), f"{A['k6']['kl64_vs_ref_all_rows']:.4f}", f"{sg(n_lp['delta'], 3)} (KL {PH['kl64_k6_vs_k6r2']['all_rows']:.4f})"]]
    for nm, key, kl in (("Core", "core", KL["core_C-K6_vs_C-K6x"]), ("Experts", "experts", KL["experts_C-K6x_vs_C-K4"]), ("Total", "total", KL["total_C-K6_vs_C-K4"])):
        c_ = SC2[key]
        t2.append(["CuteAFD", f"{nm}: {c_['a']} − {c_['b']}", f"{sg(c_['lp_close']['delta'], 3)} {ci(*c_['lp_close']['ci95'], 3)}",
                   sg(c_["hazard"]["delta"] * 1e5, 2) + " " + ci(c_["hazard"]["ci95"][0] * 1e5, c_["hazard"]["ci95"][1] * 1e5, 2), f"{kl:.4f}", "0 (bit-identical)"])
    TM = NQ["trace_metrics"]
    hz = lambda v: (lambda w: f"{sg(w[0] * 1e5, 2)} {ci(w[1] * 1e5, w[2] * 1e5, 2)}")(neg(v))
    t2.append(["vLLM fork", f"6-bit core − BF16 core, {nq_q} new questions", d3(neg(NS["all_minus_k6_lp_close"])), hz(NS["all_minus_k6_hazard"]),
               f"{TM['all']['kl_top64_vs_k6a_mean_per_trace']:.4f}", f"KL {TM['k6-b']['kl_top64_vs_k6a_mean_per_trace']:.4f}"])
    t2.append(["CuteAFD", f"Core: C-K6 − C-K6x, {nq_q} new questions", d3(neg(NC["core_bf16_minus_6bit_lp_close"])),
               hz(NC["core_bf16_minus_6bit_hazard"]), "—", "—"])
    for nm, v, h in ((f"6-bit − q_b + output projections BF16, 11 questions", QB["delta_by_question"], AP["qbo"]["hazard"]["delta_by_question"]),
                     (f"6-bit − q_b + output projections BF16, {nq_q} new questions", NP["delta_by_question"], NS["qbo_minus_k6_hazard"])):
        t2.append(["vLLM fork", nm, d3(neg(v)), hz(h), f"{TM['qbo-a']['kl_top64_vs_k6a_mean_per_trace']:.4f}" if "new" in nm else "—", "2 launches each"])
    tab2 = rich("", "", ["Engine", "Contrast", "log p(&lt;/think&gt;) at the stop", "Hazard, ×10⁻⁵", "Top-64 KL, all rows", "Second launch"], t2)
    fig2 = SC.figure("stop-decision-both", "The stop decision on fixed traces, both engines",
                     "Finished GPQA reasoning traces, fed token by token to each arm: the 77 of the first investigation (11 questions), then "
                     f"{NQ['finished_traces']} traces of {nq_q} questions not used before. Each row is the paired difference in log p(&lt;/think&gt;) at the "
                     "token where the trace stopped thinking, with its 95% interval (over traces in the first block, over questions below). The "
                     "shaded band is the vLLM fork's difference between two launches of the same model; CuteAFD's launches are identical.",
                     [(svg2, None, None)],
                     "The core rows include 0 on both engines and both question sets. One row excludes 0: q_b and the output projections on the "
                     f"11 questions where G2 flagged them. On {nq_q} new questions the same arm reads {d3(neg(NP['delta_by_question']))}, and the "
                     "11-question value lies outside that interval. One secondary measure moves on the new questions: the hazard (mean "
                     "p(&lt;/think&gt;) over the 512 tokens before the stop) is higher on the 6-bit side on both engines, "
                     f"{hz(NS['all_minus_k6_hazard'])} (vLLM fork) and {hz(NC['core_bf16_minus_6bit_hazard'])} (CuteAFD) ×10⁻⁵, where on the first 11 "
                     "questions both intervals include 0. Both shifts are under a tenth of the hazard itself, and the measure at the stop does not move. The traces are GPQA reasoning, the content "
                     "where free generation shows no length difference; code text was not scored this way.",
                     tab2 + '<p class="sign">Hazard: mean p(&lt;/think&gt;) over the 512 tokens before the stop. KL: top-64, nats per token, '
                     f"between the two arms of the row (experts: {KL['experts_C-K4_vs_C-K6x']:.4f} with the other arm as reference). Sources: "
                     + src(f"{TLD}/analysis/G2-SCORES-A1.json") + ", " + src(f"{CSD}/analysis/S2-SCORES-base-C-K6.json") + ", "
                     + src(f"{CSD}/analysis/S2-SCORES-base-C-K6x.json") + ", " + src(f"{CSD}/analysis/S2-IDENTITY.json") + "; per probe: "
                     + src(f"{CSD}/analysis/s2-probes.csv") + "; follow-ups " + src(f"{APD}/analysis/QBO.json") + ", " + src(f"{NQD}/analysis/NQ.json")
                     + ". New questions: KL is the mean per trace against the first K4-Core-K6 launch; hazard as above.</p>",
                     [("v", "vLLM fork"), ("c", "CuteAFD"), ("band", "vLLM launch-to-launch difference"), ("ci", "interval excludes 0"), ("ciu", "interval includes 0")])

    pos = AP["position"]
    fit = ("<ul><li><b>The 6-bit core makes code replies think longer on CuteAFD.</b> The first reading (code "
           f"{rr(BL['code']['ratio'])}x, read after the fact) shrank on 8 prompts with new seeds ({rr(core['ratio_by_content']['code'])}x on code, "
           f"interval over 8 prompts including 1). The code study then used 16 code prompts, 12 of them new, 4 seeds each: "
           f"{rr(cp['ratio'])}x {rci(*cp['ratio_ci95_prompts'])} on the new prompts, every prompt above 1, the 6-bit core longer in "
           f"{CT['pairs_6bit_longer'][0]} of {CT['pairs_6bit_longer'][1]} seed pairs. This revises the earlier “inconclusive”: that interval was "
           "wide because of the prompt count, not because the effect was absent.</li>"
           f"<li><b>The extra thinking does not change the outcome.</b> Hidden tests pass on {CA['C-K6']['all_tests_pass']} and "
           f"{CA['C-K6x']['all_tests_pass']} of {CA['C-K6']['requests']} replies; the two arms agree on all-pass in "
           f"{CT['pairs_agree_on_all_tests_pass'][0]} of {CT['pairs_agree_on_all_tests_pass'][1]} pairs. Median reasoning "
           f"{k(CA['C-K6']['median_reasoning_tokens'])} against {k(CA['C-K6x']['median_reasoning_tokens'])} tokens, at "
           f"{CA['C-K6']['median_decode_tok_s']:.0f} against {CA['C-K6x']['median_decode_tok_s']:.0f} tok/s: on these prompts the 6-bit core "
           "costs about a third more time per code reply for the same result.</li>"
           f"<li><b>The routed experts are ruled out at this resolution.</b> {rr(exp_['ratio'])}x {rci(*exp_['ratio_ci95_prompts'])}; the total "
           f"is the core times the experts ({rr(core['ratio'])} × {rr(exp_['ratio'])} ≈ {rr(tot['ratio'])}).</li>"
           f"<li><b>It is tied to code, not to reasoning in general.</b> On GPQA reasoning no length difference shows (Block L reasoning "
           f"{rr(BL['reasoning']['ratio'])}x {rci(*BL['reasoning']['ratio_ci95_prompts'])}; vLLM G4, finished replies, {rr(g4f[0])}x), and the "
           f"stop decision on fixed GPQA traces does not move for the core on either engine, now on {pool_q} questions. How the stop decision "
           "behaves on code text has not been scored.</li>"
           "<li><b>The difference does not build up along the reply</b> on the GPQA traces: on both engines the top-64 KL between the core "
           f"arms is highest in the first 1,024 tokens (CuteAFD {pos['cuteafd']['core']['m1_kl_by_bin']['0-1024'][0]:.4f}), flat from 1K to 64K "
           f"({pos['cuteafd']['core']['m1_kl_by_bin']['1024-4096'][0]:.4f}-{pos['cuteafd']['core']['m1_kl_by_bin']['16384-65536'][0]:.4f}) and lower "
           "beyond. Whether the same holds on code text is unmeasured.</li>"
           "<li><b>q_b and the output projections.</b> The two groups that met G2's rule, swapped to BF16 together with the KDA output "
           f"projection, shift the stop decision on the 11 questions they were found on (6-bit side {d3(neg(QB['delta_by_question']))}, launch "
           f"noise {AP['qbo']['reading_rule']['launch_band']:.4f}), not on {nq_q} new questions ({d3(neg(NP['delta_by_question']))}). The whole core in BF16 "
           "shows no such shift on either set. The flags are specific to those 11 questions.</li>"
           "<li><b>The two engines' “BF16 core” differ.</b> The vLLM loader serves it as BF16; CuteAFD converts it to FP8 at load, which is "
           "how it serves K4. The CuteAFD core contrast is 6-bit against FP8-from-BF16, on CuteAFD's kernels; the same 16 code prompts and "
           "seeds on the vLLM fork, where the 6-bit core is rebuilt to BF16 at load and runs on the same kernels as the BF16 core, are being "
           "run to separate the weights from the serving path.</li>"
           f"<li><b>The core is also what makes K4-Core-K6 slower</b> on CuteAFD: with its BF16 core converted to FP8, its experts decode at K4's "
           f"speed ({SP['C-K6x']['code']:.0f} against {SP['C-K4']['code']:.0f} tok/s on code); with the native 6-bit core, {SP['C-K6']['code']:.0f}.</li></ul>")

    # CuteAFD details
    def arow(lab, sub, ck, core_, exp__, arm):
        P = S1["per_arm"][arm]; mr = P["median_reasoning_tokens"]
        return [f"{lab}<small>{sub}</small>", ck, f"{core_}<br><span class=\"ci\">experts: {exp__}</span>", f"{k(mr['code'])} / {k(mr['prose'])}",
                f"{SP[arm]['code']:.0f} / {SP[arm]['prose']:.0f}"]
    arms_t = rich("", "Three arms on CuteAFD v4.0.0 (unmodified launcher; serving and scoring configs differ only in the checkpoint). 32 replies per arm in free generation, all finished, none capped; 93 fixed traces per arm",
                  ["Arm", "Checkpoint", "Core at runtime", "Reasoning tokens (median), code / prose", "Decode tok/s, code / prose"],
                  [arow("K4-Core-K6", "C-K6", hf(*revs["K4-Core-K6"]), "native 6-bit EXL3", "K4-Core-K6's", "C-K6"),
                   arow("K4-Core-K6, BF16 core", "C-K6x · local derived checkpoint, not a producer release",
                        "built by " + src(f"{CSD}/prep/build_derived.py") + " from the row above and the core of " + hf(*revs["BF16"]),
                        "BF16 → FP8 at load, as K4", "K4-Core-K6's", "C-K6x"),
                   arow("K4", "C-K4", hf(*revs["K4"]), "BF16 → FP8 at load", "K4's", "C-K4")],
                  foot=f"The BF16 core tensors are byte-identical to K4's ({CS['derived_checkpoint']['core_bytes_identical_to_k4']}; "
                       + src(f"{CSD}/prep/core-hash.json") + "), so core minus experts isolates each part. CuteAFD's planner gives the derived "
                       "checkpoint the same plan as K4 (FP8 core projections, FP8 head, same KV pool). Medians are of all 16 replies per content, "
                       "not paired; the ratios above are paired.")
    s1_note = (f"<p>Free generation: Block L stage L3 (130,048-token cap, 2 in flight, thinking on), the same 4 code and 4 prose prompts as "
               f"the run that raised the question, two new seed sets; each seed is shared by the three arms. All {3 * tot['pairs']} replies "
               "finished. Reasoning tokens are counted by re-tokenizing the saved reasoning text. Frozen rule: a difference is detected when the "
               "95% interval over the 8 prompts excludes 1; the interval over the 32 pairs is secondary. Read: " + src(f"{CSD}/S1-READ.md") + ".</p>")
    s2_note = (f"<p>Fixed traces: the 93 traces of the vLLM investigation (token ids unchanged), scored on CuteAFD's bench probe with a cold "
               f"cache and drafting off; {S2['traces']['rows_per_arm']:,} rows per arm; the longest trace ({S2['probe_timing']['longest_prompt_tokens']:,} "
               f"tokens) took {S2['probe_timing']['longest_seconds']:.0f} s. The thinking-length run's scorer is used unchanged. Read: "
               + src(f"{CSD}/S2-READ.md") + ".</p>")
    maxp = (f"<p><b>A note on one measure.</b> “Max p(&lt;/think&gt;) on unfinished traces” (the last column of the vLLM per-group table "
            f"below) falls on the first scored row, the opening of the reasoning span, in {MP['argmax_at_first_row'][0]} of "
            f"{MP['argmax_at_first_row'][1]} trace-arms on CuteAFD and {MP['vllm_g2_argmax_at_first_row'][0]} of {MP['vllm_g2_argmax_at_first_row'][1]} "
            "on the vLLM fork. That row is the same for every trace of a question, so the measure is mostly a per-question value counted once per "
            "trace. On CuteAFD it flagged the experts (one question carries it); with the opening row removed the order of the arms changes from "
            "question to question. On the vLLM fork no group met the rule on it. Post hoc: " + src(f"{CSD}/analysis/POST-HOC-S2.json") + ".</p>")

    def crow(lab, sub, arm):
        a_ = CA[arm]
        return [f"{lab}<small>{sub}</small>", f"{a_['finished']} / {a_['requests']}", k(a_["median_reasoning_tokens"]),
                f"{a_['all_tests_pass']} of {a_['requests']}", f"{a_['mean_share_tests_passed']:.3f}", f"{a_['median_decode_tok_s']:.0f}",
                str(a_["finished_with_terminal_repetition_onset"])]
    code_t = rich("", f"CuteAFD v4.0.0, the core-swap serving configs; 16 code prompts × 4 seeds per arm, the same seed on both arms; cap 130,048 tokens, 2 in flight, thinking on",
                  ["Arm", "Finished", "Reasoning tokens, median", "All tests pass", "Share of tests passed", "Decode tok/s, median", "Ends by restating earlier text"],
                  [crow("6-bit core", "C-K6 · " + hf(*revs["K4-Core-K6"]), "C-K6"),
                   crow("BF16 core → FP8 at load", "C-K6x · local derived checkpoint, not a producer release", "C-K6x")],
                  foot="Prompts: p0-p3 are the four Block L code projects, unchanged; p4-p15 are 12 Python projects (spec, reference implementation, "
                       "hidden pytest suite) written for this run before any request, each reference passing its tests. Reasoning tokens by "
                       "re-tokenizing the saved reasoning text; tests run in a no-network sandbox. Last column: replies whose end repeats earlier "
                       "text (the loop detector's onset; code answers restate code drafted in the reasoning); all finished, none are loops. "
                       "Frozen rule: detected when the 95% interval over the 12 new prompts excludes 1. Read: " + src(f"{CTD}/CT-RESULT.md")
                       + " (it also corrects one descriptive field of " + src(f"{CTD}/analysis/CT-RESULT.json") + "); per reply: "
                       + src(f"{CTD}/analysis/samples.csv") + "; prompts: " + gh(f"{CTD}/prompts", "<code>prompts/</code>") + ".")
    code_note = ("<p>Per prompt (6-bit / BF16→FP8): " + ", ".join(f"p{i} {rr(call['per_prompt'][f'p{i}'])}" for i in range(16))
                 + ". The vLLM fork run on the same prompts and seeds (6-bit core rebuilt to BF16 at load against the BF16 core, same kernels) "
                 "is in progress; it will show whether the ratio goes with the 6-bit weights or with CuteAFD's native 6-bit path.</p>")
    BN = ["0-1024", "1024-4096", "4096-16384", "16384-65536", "65536-1073741824"]
    BL_ = ["0-1K", "1K-4K", "4K-16K", "16K-64K", "64K+"]
    def prow(lab, d):
        return [lab] + [f"{d['m1_kl_by_bin'][b][0]:.4f}" for b in BN] + [d3(d["m1_slope_kl_per_log2pos"])]
    PV, PC = pos["vllm"], pos["cuteafd"]
    pos_t = rich("", "Top-64 KL between two arms, nats per token, by position in the trace; 93 GPQA traces, the same rows on both engines",
                 ["Arms"] + BL_ + ["Slope per doubling of position"],
                 [prow("vLLM: whole core BF16 vs 6-bit", PV["all"]), prow("vLLM: MLA q_b BF16 vs 6-bit", PV["mla_q_b"]),
                  prow("vLLM: MLA output BF16 vs 6-bit", PV["mla_o"]), prow("vLLM: second 6-bit launch", PV["k6r2"]),
                  prow("CuteAFD: core, BF16→FP8 vs 6-bit", PC["core"]), prow("CuteAFD: experts, K4's vs K4-Core-K6's", PC["experts"])],
                 foot="Rows of each bin: " + ", ".join(f"{b} {PC['core']['m1_kl_by_bin'][bn][1]:,}" for b, bn in zip(BL_, BN)) + ". Slope: per trace, "
                      "least squares of KL on log2(position), mean over traces, 95% bootstrap clustered by question. Criteria written before "
                      "computing: " + src(f"{APD}/NOTE.md") + "; numbers " + src(f"{APD}/analysis/POSITION.json") + ".")
    pos_note = ("<p>No swapped group's divergence grows with position, on either engine: every slope is negative. The vLLM fork's second "
                "launch is the exception in shape (identical over the first chunk of prefill, then 0.002-0.005): that is the prefill "
                "variation between launches described under G2, not a model difference. One measure "
                "differs between the engines: the mean log p(&lt;/think&gt;) over the 512 tokens before the close, where p is about 10⁻⁶. "
                f"BF16 side minus 6-bit, it reads {d3(PC['core']['m2_last512_logp_delta'])} on CuteAFD and {d3(PV['all']['m2_last512_logp_delta'])} "
                f"on the vLLM fork, and again on the {nq_q} new questions ({d3(NC['core_bf16_minus_6bit_last512_logp'])} and "
                f"{d3(NS['all_minus_k6_last512_logp'])}). It measures the far tail of the head's distribution, where FP8 and BF16 serving "
                "differ. In linear terms over the same tokens (hazard, figure above) the engines agree in sign on the new questions.</p>")

    rows = []
    for arm in TL_ORDER:
        c = C[arm]["lp_close"]; g = GR[arm]
        rows.append([f"{'All 316 core tensors' if arm == 'all' else E(g['what'])}<small>{g['tensors']} tensor{'s' if g['tensors'] != 1 else ''}"
                     f"{' · the reference gap' if arm == 'all' else ''}</small>",
                     diverge(c["delta"], 0.03, c["ci95"][0] > 0 or c["ci95"][1] < 0, label=sg(c["delta"], 3), sub=ci(*c["ci95"], 3)),
                     "—" if arm == "all" else f"{c['closure']:.1f}",
                     badge(C[arm]["lp_close"].get("moves_amendment_1", False), yes="meets the rule", no="—") if arm != "all" else "—",
                     sg(C[arm]["hazard"]["delta"] * 1e5, 2), sg(C[arm]["max_p_think"]["delta"] * 1e6, 1)])
    rows.append([f"Second launch, no swap<small>launch-to-launch variation</small>",
                 diverge(n_lp["delta"], 0.03, False, label=sg(n_lp["delta"], 3), sub=ci(*n_lp["ci95"], 3)), "—", "—",
                 sg(noise["hazard"]["delta"] * 1e5, 2), sg(noise["max_p_think"]["delta"] * 1e6, 1)])
    g2t = rich("", "Direction as published: BF16 − 6-bit. Each group loaded from BF16 alone, everything else 6-bit; change against the 6-bit core, paired over traces, "
               "95% bootstrap interval. A bar is solid when its interval excludes 0",
               ["Swapped to BF16", "log p(&lt;/think&gt;) at the close", "Share of the reference gap", "Frozen rule", "Hazard, ×10⁻⁵", "Max p on unfinished, ×10⁻⁶"],
               rows, hi=(0,),
               foot="Frozen rule (with Amendment 1): a group moves a measure when it closes at least half the gap to the all-BF16 core, its interval "
                    "excludes 0 and its change exceeds the second launch's. Hazard: mean p(&lt;/think&gt;) over the 512 tokens before the close. "
                    "Max p: largest p(&lt;/think&gt;) along the 16 traces that did not finish; mostly a per-question value (note above). Source: "
                    + src(f"{TLD}/analysis/G2-SCORES-A1.json") + ".")

    ph = PH["contrasts"]
    ctx = ("<ul><li><b>Two groups meet the frozen rule</b> on the close measure: the MLA output and MLA q_b projections "
           f"({sg(C['mla_o']['lp_close']['delta'], 3)} and {sg(C['mla_q_b']['lp_close']['delta'], 3)}). Read with them: the reference gap they are "
           f"measured against ({sg(C['all']['lp_close']['delta'], 3)}) is itself smaller than launch variation and its interval includes 0, so their "
           "shares of it (3.5 and 2.9) divide by a gap indistinguishable from zero; 9 groups × 3 measures make 27 tests, of which about 1.4 "
           "would pass at 95% with no effect; no group meets the rule on the other two measures.</li>"
           f"<li><b>Post hoc, against other bases:</b> against the second 6-bit launch both intervals include 0 (MLA output "
           f"{sg(ph['k6r2']['mla_o']['delta'], 3)} {ci(*ph['k6r2']['mla_o']['ci95'], 3)}, MLA q_b {sg(ph['k6r2']['mla_q_b']['delta'], 3)} "
           f"{ci(*ph['k6r2']['mla_q_b']['ci95'], 3)}); against the mean of the two launches both exclude 0 "
           f"({sg(ph['pooled']['mla_o']['delta'], 3)}, {sg(ph['pooled']['mla_q_b']['delta'], 3)}).</li>"
           "<li><b>Size:</b> +0.014 in log p is about a 1.4% relative change in p(&lt;/think&gt;) at the close (mean p ≈ 0.70, median 0.94).</li>"
           "<li><b>The two launches differ</b> because the vLLM fork's multi-chunk prefill is not run-to-run deterministic: more than half of the "
           f"BF16-core distance on long traces ({A['k6']['kl64_vs_ref_all_rows']:.4f}) is the size of the distance between launches "
           f"({PH['kl64_k6_vs_k6r2']['all_rows']:.4f}). On the short single-chunk teacher windows the two launches differ by "
           f"{sg(pa_r2[0], 7)} in KL {ci(*pa_r2[1], 7)}. CuteAFD's two launches agree bit for bit on the same long traces.</li>"
           "<li><b>Follow-up, the two groups together</b> (BF16 − 6-bit, as the table). MLA q_b, MLA output and KDA output (56 tensors) "
           f"loaded as BF16 together, two launches against two K4-Core-K6 launches: {d3(QB['delta_by_question'])} over the 11 questions, all four launch pairings positive "
           f"(frozen rule met). Not additive: the single groups summed to about +0.04. Post hoc, the whole core in BF16 reads "
           f"{d3(AP['qbo_post_hoc']['vs_mean_of_4_k6_launches']['g2-all'])} against the same four K4-Core-K6 launches. On {nq_q} questions not "
           f"used before, the same arm reads {d3(NP['delta_by_question'])} (frozen reading: not replicated; the 11-question value lies outside "
           f"it), {d3(NQ['pooled_qbo_minus_k6_lp_close'])} over all {pool_q}. Restricted after the fact to new traces where the stop was not "
           "already near-certain (log p above −0.01 excluded), it is −0.007 [−0.037, +0.016]. The G2 flags and the follow-up are specific "
           "to the 11 questions. Sources: " + src(f"{APD}/QBO-RESULT.md") + ", " + src(f"{NQD}/NQ-RESULT.md") + ".</li></ul>")

    def toks(arm):
        return " ".join(f"<b>{k(t)}</b>" if t >= 327680 else k(t) for t in G4["per_arm"][arm]["tokens_sorted"])
    g4t = rich("", "GPQA diamond question 12 (a steady long thinker: 25-39K tokens in 6 earlier samples), temperature 1.0, top-p 0.95, thinking on, "
               "cap 327,680 tokens, seeds 51201-51212 on both arms",
               ["Arm", "Finished / looped", "Completion tokens, sorted", "Median", "sd of log tokens", "Correct"],
               [["6-bit core", f"{k4['classes'].get('ok', 0)} / {k4['classes'].get('loop', 0)}", toks("k6"), k(k4["median_tokens"]), f"{k4['sd_log_tokens']:.2f}", f"{k4['correct']} of 12"],
                ["BF16 core", f"{a4['classes'].get('ok', 0)} / {a4['classes'].get('loop', 0)}", toks("all"), k(a4["median_tokens"]), f"{a4['sd_log_tokens']:.2f}", f"{a4['correct']} of 12"]],
               foot=f"Frozen reading (as published, BF16 / 6-bit): {pr['ratio']:.2f}, 95% interval [{pr['ratio_ci95'][0]:.2f}, {pr['ratio_ci95'][1]:.2f}]; "
                    f"stated 6-bit / BF16 on this page: {rr(g4r[0])} {rci(g4r[1], g4r[2])}. The interval includes 1 and is wider than [0.8, 1.25] "
                    f"(inconclusive); its width comes from the one loop. Post hoc, finished replies only: {G4_FINISHED[0]:.2f} {rci(*G4_FINISHED[1:])} "
                    f"(6-bit / BF16 {rr(g4f[0])}); sd of log tokens 0.28 and 0.31 against 0.19 earlier, so this design resolves about a 1.3x change. "
                    "The loop (seed 51203) repeated one sentence to the cap, 1.49M characters, no answer. Sources: "
                    + src(f"{TLD}/analysis/G4-RESULT.json") + ", " + src(f"{TLD}/G4-RESULT.md") + ".", cls="nb")

    K3, K4c, G1 = la["K3.25"], la["K4"], la["G1b"]
    lct = rich("", "Replies that reached the 327,680-token cap on the seven most length-variable GPQA questions (186, 12, 81, 120, 86, 74, 13)",
               ["Checkpoint", "Engine", "Requests", "At the cap", "Whole benchmark"],
               [["K3.25", "vLLM fork 0.7.0-0.9.1, several configurations", str(K3["knife_requests"]), f"{K3['knife_cap_hits']} ({pct(K3['knife_cap_hits'], K3['knife_requests'])})",
                 f"{K3['all_cap_hits']} of {K3['all_requests']:,} ({pct(K3['all_cap_hits'], K3['all_requests'])})"],
                ["K4", "vLLM fork 0.8.0-0.9.1", str(K4c["knife_requests"]), f"{K4c['knife_cap_hits']} ({pct(K4c['knife_cap_hits'], K4c['knife_requests'])})",
                 f"{K4c['all_cap_hits']} of {K4c['all_requests']:,} ({pct(K4c['all_cap_hits'], K4c['all_requests'])})"],
                ["K4-Core-K6, 6-bit core", "vLLM fork 0.9.2 + local loader", str(G1["knife_requests"]), f"{G1['knife_cap_hits']} ({pct(G1['knife_cap_hits'], G1['knife_requests'])})", "—"]],
               foot=f"K3.25 and K4: every GPQA record of <a href=\"https://github.com/UrbanAstroLA/local-inference-evals\">local-inference-evals</a> that logged "
                    f"token counts. Counting the older records too, with an empty answer standing in for a cap hit: {K3['knife_with_proxy'][0]} of "
                    f"{K3['knife_with_proxy'][1]} and {K4c['knife_with_proxy'][0]} of {K4c['knife_with_proxy'][1]}. K4 against K4-Core-K6: Fisher p = "
                    f"{la['fisher_k4_vs_k4core_k6_g1b']:.1f}. Engine versions, concurrency and loader differ between rows. Questions 81 and 13 carry "
                    f"most cap hits (K4-Core-K6: {G1['by_doc']['81'] + G1['by_doc']['13']} of 12). Source: " + src(f"{TLD}/analysis/LOOP-CHECKS.json") + ".")
    loops = [x for x in lb["not_finished"] if x["class"] == "loop"]
    det = ("<ul><li><b>How late the loops start.</b> The looping investigation's early-stop detector (the last 30,000 characters checked every "
           "10,000; three ratios below 0.10 in a row) stops no finished reply here "
           f"({lb['finished_replies']} replies, lowest check {lb['finished_lowest_check']:.3f}). On the {len(loops)} loops it would fire at "
           + ", ".join(f"{x['detector_fires_at_char'] / 1e3:,.0f}K of {x['reasoning_chars'] / 1e3:,.0f}K characters" if x["detector_fires_at_char"]
                       else f"never ({x['reasoning_chars'] / 1e3:,.0f}K)" for x in loops) +
           ": the three loops on questions 81 and 13 began late in their replies, the question-12 loop early.</li>"
           f"<li><b>On the 16 unfinished traces</b> (cut at 32K tokens, mostly before any loop), the BF16 core makes the recorded continuation "
           f"slightly less likely per token ({sg(c_all['delta'])} {ci(*c_all['ci95'])}), the same size as between two launches of the 6-bit core "
           f"({sg(c_r2['delta'])} {ci(*c_r2['ci95'])}).</li>"
           f"<li><b>CuteAFD rerun:</b> 0 of {3 * tot['pairs']} replies reached the 130,048-token cap on any arm (code and prose prompts, not the "
           "GPQA questions above).</li></ul>")

    design = ("<ul><li><b>CuteAFD (the engine where the question arose).</b> tpurtell's CuteAFD v4.0.0, unmodified. Three arms (table above) "
              "separate the core from the routed experts; the derived checkpoint is a local build, not a producer release. Step 2, the fixed "
              "traces, ran first (four scoring launches, including a second K4-Core-K6 launch); step 1, free generation, followed. Protocol "
              "frozen before the first request: " + src(f"{CSD}/protocol/PROTOCOL.md") + ". The Block L ratio that raised the question and the "
              "max-p check are post hoc.</li>"
              "<li><b>vLLM fork, arms.</b> One checkpoint, <code>wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6</code> (K4 routed experts, 6-bit EXL3 core "
              "and head). The 6-bit arm rebuilds its 316 core tensors to BF16 at load (exact arithmetic, one rounding). Each swap arm loads the "
              "named group's original tensors from <code>zai-org/GLM-5.3-Flash-BF16</code> @ <code>f9fed3bb</code>, the checkpoint's own source, "
              "instead; every launch logged the expected number of swapped tensors. Same engine, image, loader and kernels on every arm.</li>"
              "<li><b>vLLM fork, engine.</b> tpurtell's vLLM fork v0.9.2 release image with a <b>local loader modification</b> (not a tpurtell release; the "
              "release does not load this checkpoint): " + gh("repro/vllm-k6-loader", "<code>repro/vllm-k6-loader</code>") + ".</li>"
              f"<li><b>G2, fixed traces.</b> {tr['finished']} finished and {tr['not_finished']} unfinished reasoning traces, each teacher-forced "
              f"through every arm: {tr['by_set']['tr']['finished'] + tr['by_set']['tr']['not_finished']} from earlier hard-question probes "
              f"(questions {', '.join(map(str, tr['by_set']['tr']['docs']))}; K3.25 and K4 on earlier fork versions, so off-policy here) and "
              f"{tr['by_set']['on']['finished'] + tr['by_set']['on']['not_finished']} generated by the 6-bit arm itself on the seven "
              "length-variable questions. Top-64 log-probabilities at sampled rows and at the last 512 rows before each close, plus the "
              "exact log-probability of <code>&lt;/think&gt;</code> at every stored row. Plus the P-A teacher panel (25 × 2,048 tokens). "
              "CuteAFD scored the same traces at the same rows.</li>"
              "<li><b>vLLM protocols.</b> G2's reading rule was frozen before the first capture; a second launch of the 6-bit arm was added (Amendment 1) "
              "before any capture was read, because the fork's long-prompt prefill varies between launches. G4 was frozen after G2 was read and "
              "before its first sample. The loop checks were chosen after G4 was read and are exploratory.</li>"
              "<li><b>Code study (CuteAFD).</b> The core-swap arms C-K6 and C-K6x on 16 code prompts × 4 seeds, the same seed on both arms, "
              "the v4 Block L driver unchanged; 12 of the prompts written for it, before any request. Primary set and rule frozen before the "
              "first request: " + src(f"{CTD}/protocol/PROTOCOL.md") + ".</li>"
              "<li><b>Position (no new requests).</b> The existing dumps of both engines, by position along the trace; criteria written "
              "before computing: " + src(f"{APD}/NOTE.md") + ". CuteAFD v4.0.0 loads its native core only whole (every layer's attention and "
              "FFN groups native together), so the single-group swaps exist on the vLLM fork only; a CuteAFD attention-only arm was "
              "refused at load.</li>"
              "<li><b>q_b and output projections together (vLLM fork).</b> 56 tensors, launches interleaved K4-Core-K6, swap, K4-Core-K6, "
              "swap; frozen before the first launch: " + src(f"{APD}/protocol/FROZEN-QBO.json") + ".</li>"
              f"<li><b>New questions.</b> {len(NQ['questions_drawn'])} GPQA Diamond questions drawn at random (seed 20261106) from those not used "
              f"before; K4-Core-K6 on the vLLM fork wrote 3 replies each (all {NG['samples']} finished, {NG['finished_correct']} correct, median "
              f"{k(NG['completion_tokens_finished']['median'])} tokens: mostly easier than the first 11, which were chosen as loop-prone or "
              "length-variable); every vLLM arm and both CuteAFD core arms scored the finished replies. Frozen before the first launch: "
              + src(f"{NQD}/protocol/PROTOCOL.md") + ".</li></ul>")

    repro = ("<ol><li><b>Inputs.</b> Checkpoints " + hf(*revs["K4-Core-K6"]) + ", " + hf(*revs["K4"]) + " and the BF16 source " + hf(*revs["BF16"])
             + "; engines tpurtell's CuteAFD v4.0.0 (<a href=\"https://github.com/tpurtell/cuteafd\">tpurtell/cuteafd</a>) and vLLM fork v0.9.2 "
             "(<a href=\"https://github.com/tpurtell/glm-5.3-flash-ext3-2x-rtx\">tpurtell/glm-5.3-flash-ext3-2x-rtx</a>) with "
             + gh("repro/vllm-k6-loader", "the local loader modification") + ".</li>"
             "<li><b>Derived checkpoint.</b> " + src(f"{CSD}/prep/build_derived.py") + " (standard library; rewrites the shards that hold core "
             "tensors, hardlinks the rest); check with " + src(f"{CSD}/prep/hash_core.py") + " against " + src(f"{CSD}/prep/core-hash.json")
             + " and " + src(f"{CSD}/prep/derived-manifest.json") + ".</li>"
             "<li><b>CuteAFD runs.</b> Configs in " + gh(f"{CSD}/code/configs") + "; the chain " + src(f"{CSD}/code/chain-cs.sh")
             + "; drivers " + gh(f"{CSD}/code/drivers") + " (fixed-trace probes, identity check, Block L with new seeds) and the v4 Block L driver "
             + gh(f"{CSD}/code/v4-drivers") + ", which imports " + src("repro/stage0/drivers/block_l.py") + ".</li>"
             "<li><b>Scoring.</b> Reasoning tokens: " + src("repro/stage0/drivers/analyze_l.py") + "; free generation: "
             + src(f"{CSD}/analysis/analyze_s1.py") + " and " + src(f"{CSD}/analysis/block_l_posthoc.py") + " (both read " + src(f"{CSD}/analysis/samples.csv")
             + "'s fields); fixed traces: " + src(f"{TLD}/analysis/score_stop.py") + ", " + src(f"{CSD}/analysis/post_hoc_s2.py") + ".</li>"
             "<li><b>Follow-ups.</b> Code study: chain, driver and prompt builder in " + gh(f"{CTD}/code") + ", prompts in "
             + gh(f"{CTD}/prompts") + ", reading " + src(f"{CTD}/analysis/analyze_ct.py") + ". Position and q_b + output projections: "
             + src(f"{APD}/analysis/position.py") + ", " + src(f"{APD}/analysis/analyze_qbo.py") + ", chain " + src(f"{APD}/code/chain-qbo.sh")
             + ". New questions: " + src(f"{NQD}/code/select_questions.py") + ", " + src(f"{NQD}/code/chain-nq.sh") + ", "
             + src(f"{NQD}/analysis/analyze_nq.py") + ".</li>"
             "<li><b>Third-party analysis without the run.</b> " + src(f"{CSD}/analysis/samples.csv") + " (one row per reply: arm, seed, finish, "
             "reasoning tokens, decode speed), " + src(f"{CSD}/analysis/s2-probes.csv") + " (one row per probe, with a digest of the per-row logits "
             "hashes), " + src(f"{CTD}/analysis/samples.csv", "the code study's <code>samples.csv</code>") + " (one row per reply, with tests passed), "
             + src(f"{NQD}/analysis/NQ.json") + " (new questions: per-question deltas, per-reply length and correctness), the per-trace scores in "
             + gh(f"{CSD}/analysis") + " and " + gh(f"{TLD}/analysis") + "; the numbers on this page are in the "
             "<code>SUMMARY.json</code> of " + ", ".join(gh(d, f"<code>{d.split('/')[-1]}</code>") for d in (TLD, CSD, CTD, APD, NQD))
             + ", and the post hoc checks in each folder's result notes.</li>"
             "<li><b>Not published.</b> Reply and reasoning texts (model output), GPQA question text and the fixed traces' token ids (dataset "
             "terms), capture and probe dumps (top-64 log-probabilities of model output), and checkpoint weights (rebuild them from the public "
             "sources with the script above).</li></ol>")

    openq = ("<ul><li><b>Does the code effect go with the 6-bit weights or with CuteAFD's serving of them?</b> Measured on CuteAFD only, "
             "where the comparison arm is FP8-from-BF16 on different kernels. The vLLM fork run on the same prompts and seeds is in progress.</li>"
             "<li><b>Does the core change the stop decision on code text?</b> Unmeasured: every fixed trace scored so far is GPQA reasoning.</li>"
             "<li><b>Does it hold beyond these 16 Python projects?</b> One prompt family, one checkpoint; prose moved less (1.04x on 4 prompts).</li>"
             "<li><b>Does the 6-bit core change how often replies loop?</b> Measured: 1 loop in 18 samples of question 12 on the 6-bit core "
             "(6 earlier, 12 in G4), 0 in 12 on the BF16 core (Fisher p = 1.0), vLLM fork; on the seven questions, K4-Core-K6 reached the cap about as "
             f"often as K4 and K3.25 in earlier records (table above). No CuteAFD reply reached the cap ({3 * tot['pairs'] + 2 * CA['C-K6']['requests']} "
             "replies, code and prose).</li></ul>")
    caveat = ("<ul><li>Two engines, one machine. The vLLM loader rounds the 6-bit core once from exact arithmetic; CuteAFD runs it natively and the "
              "producer's own rebuild rounds at FP16 between stages (15.8% of elements differ, 2.4% by more than one BF16 unit). CuteAFD's “BF16 "
              "core” is BF16 converted to FP8 at load.</li>"
              "<li>The routed experts are compared as two whole quantizations (K4-Core-K6's and K4's), not tensor by tensor; the derived "
              "checkpoint is a local build, not a producer release.</li>"
              "<li>Free generation on CuteAFD covers 8 prompts (4 code, 4 prose), 4 replies per prompt per arm; the Block L ratio that raised "
              "the question is post hoc. G4 on the vLLM fork is one GPQA question; the knife-edge questions where replies tip between short and "
              "capped were dropped from G4 because their spread would need hundreds of samples per arm.</li>"
              "<li>The code study's 12 new prompts were written for it (specs, reference implementations and tests published); p0-p3 raised "
              "the question and are reported separately. One prompt family (Python packages), 4 seeds per prompt.</li>"
              "<li>The fixed traces are GPQA reasoning generated on the vLLM fork, teacher-forced on both engines. The new questions are a random "
              "draw and mostly easy for this model; on many of their traces p(&lt;/think&gt;) at the close is near 1 on every arm.</li>"
              "<li>KL here is a top-64 measure with the arm's 64th value as the floor for tokens outside its top 64 (a lower bound), not "
              "full vocabulary. GLM tokenizer throughout; not comparable with other model families.</li></ul>")
    data = (f'<p class="sign">Data: CuteAFD part {gh(CSD, f"<code>{CSD}</code>")} ({src(f"{CSD}/SUMMARY.json")}, '
            f'{src(f"{CSD}/S1-READ.md")}, {src(f"{CSD}/S2-READ.md")}, {gh(f"{CSD}/protocol", "<code>protocol/</code>")}); vLLM part '
            f'{gh(TLD, f"<code>{TLD}</code>")} ({src(f"{TLD}/SUMMARY.json")}, {src(f"{TLD}/G2-RESULT.md")}, {src(f"{TLD}/G4-RESULT.md")}, '
            f'{src(f"{TLD}/LOOP-CHECKS.md")}, {gh(f"{TLD}/protocol", "<code>protocol/</code>")}); follow-ups {gh(CTD, f"<code>{CTD}</code>")} '
            f'(code study), {gh(APD, f"<code>{APD}</code>")} (position, q_b + output projections) and {gh(NQD, f"<code>{NQD}</code>")} '
            "(new questions). Reasoning texts, question text and dumps are not published.</p>")
    body = (conv + h2("at-a-glance", "At a glance") + glance +
            h2("length", "Thinking length in free generation") + fig1 +
            h2("stop-both", "The stop decision on fixed traces") + fig2 +
            h2("fit", "How the results fit together") + fit +
            h2("code", "CuteAFD: the 6-bit core on 16 code prompts") + code_t + code_note +
            h2("cuteafd", "CuteAFD: core or experts?") + arms_t + s1_note + s2_note + maxp +
            h2("position", "Does the difference build up along the reply?") + pos_t + pos_note +
            h2("stop-decision", "vLLM fork: core groups on fixed traces (G2)") + g2t + ctx +
            h2("free-generation", "vLLM fork: free generation (G4)") + g4t +
            h2("loops", "Loops: what the records show") + lct + det +
            h2("design", "What was tested") + design +
            h2("reproduce", "Reproduce and re-analyse") + repro +
            h2("open", "Open questions") + openq +
            h2("caveats", "Caveats") + caveat + data)
    page("thinking.html", "Investigation: does the 6-bit core make K4-Core-K6 think longer?", lede, body)


def build(root, page, h2, gh, details):
    S = load(root)
    S["_root"] = root
    page_checkpoints(S, page, h2, gh, details)
    page_v4(S, page, h2, gh, details)
    if (Path(root) / TCD / "SUMMARY.json").exists():
        page_tools(root, page, h2, gh, details)
    if (Path(root) / TLD / "SUMMARY.json").exists():
        page_thinking(root, page, h2, gh, details)
