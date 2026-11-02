#!/usr/bin/env python3
"""Pages for the CuteAFD v4.0.0 rerun and the three checkpoints (imported by tools/build_site.py). Standard library only.

Reads results/2026-10-30-cuteafd-v4/SUMMARY.json. Tables carry the numbers and a mark drawn in plain HTML/CSS (no
script): a bar for a level, a centred bar for a difference (solid when its 95% interval excludes 0, light and dashed
when it does not), and a word badge, so nothing is colour-only. Engine colours follow the site grammar (vLLM fork blue,
CuteAFD orange); checkpoints and producers are named in text, never coloured.
"""
import html, json
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


def rich(caption, sub, head, rows, foot="", hi=()):
    """rows: list of lists (first cell is the row label, may contain <small>); a row given as ("grp", text) is a group header."""
    body = []
    for i, r in enumerate(rows):
        if isinstance(r, tuple) and r[0] == "grp":
            body.append(f'<tr class="grp"><td colspan="{len(head)}">{r[1]}</td></tr>')
            continue
        cls = ' class="hi"' if i in hi else ""
        body.append(f"<tr{cls}>" + f'<td class="k">{r[0]}</td>' + "".join(f"<td>{c}</td>" for c in r[1:]) + "</tr>")
    cap = f'<div class="cap">{f"<b>{caption}</b>" if caption else ""}{f"<span>{sub}</span>" if sub else ""}</div>' if caption or sub else ""
    f = f'<div class="foot">{foot}</div>' if foot else ""
    th = ("<thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead>") if any(head) else ""
    return f'<div class="rt">{cap}<div class="sc"><table>{th}<tbody>' + "".join(body) + f"</tbody></table></div>{f}</div>"


def n0(x): return f"{x:,.0f}"


# ------------------------------------------------------------------ checkpoints page

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
         ["…where BF16 was ≥90% sure"] + [bar(P[f"{c} CuteAFD"]["differs_bf16_sure"], 0.7, f"{P[f'{c} CuteAFD']['differs_bf16_sure']:.2f}") for c in CK]],
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
            "leaves 16% more room for context and runs 5-15% slower; its code replies think longer.</p>" + k6k4 +
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
            h2("not-covered", "Not covered") +
            "<ul><li>K4-Core-K6 on the vLLM fork: v0.9.2 does not run it. K4-Core-K6 results are on the "
            '<a href="checkpoints.html">checkpoints</a> page.</li>'
            "<li>CuteAFD with DGX Spark expert nodes, or any layout other than two RTX PRO 6000 with local experts.</li>"
            "<li>CuteAFD v4.1.0 as a run (source read only; see <a href=\"#setup\">What was tested</a>).</li>"
            "<li>Full-vocabulary P-B: the fidelity set ships top-k rows only.</li></ul>" +
            f'<p class="sign">Numbers: {gh(f"{RD}/SUMMARY.json", "<code>SUMMARY.json</code>")}.</p>')
    page("v4.html", "CuteAFD v4.0.0 against tpurtell's vLLM fork", lede, body)


def build(root, page, h2, gh, details):
    S = load(root)
    page_checkpoints(S, page, h2, gh, details)
    page_v4(S, page, h2, gh, details)
