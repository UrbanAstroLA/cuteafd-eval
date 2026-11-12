#!/usr/bin/env python3
"""Page for the CuteAFD v5.0.0 context probe (imported by tools/build_site.py). Standard library only.

Reads results/2026-11-10-context-probe/SUMMARY.json. Same grammar as tools/site_v4.py, whose cell builders it reuses:
plain HTML/CSS, a bar for a level, a centred bar for a difference (solid when its 95% interval excludes 0, dashed
when it does not) and a word badge. Arms are named in text, never coloured.
"""
import importlib.util, json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

_v4 = importlib.util.spec_from_file_location("site_v4", Path(__file__).resolve().parent / "site_v4.py")
V4 = importlib.util.module_from_spec(_v4); _v4.loader.exec_module(V4)
E, MINUS, sg, bar, diverge, badge, rich, n0 = V4.E, V4.MINUS, V4.sg, V4.bar, V4.diverge, V4.badge, V4.rich, V4.n0

RUN = "2026-11-10-context-probe"
RD = f"results/{RUN}"
ARMS = ("anchor", "hqa", "compact")
PAIRS = ("hqa - anchor", "compact - anchor", "hqa - compact")
LENS = (("4k", "4K"), ("16k", "16K"), ("64k", "64K"), ("128k", "127K"))
ARM_SUB = {"anchor": "BF16 core, reference", "hqa": "BF16 q_b_proj + o_proj, rest K6", "compact": "K6 core",
           "exlr8-k4": "EXLR8 K4 checkpoint, added later"}
REF = "exlr8-k4"                       # reference checkpoint added after the results were read; never part of ARMS or PAIRS
ARMS4 = ARMS + (REF,)


def load(root):
    return json.loads((Path(root) / RD / "SUMMARY.json").read_text())


def f3(x): return f"{x:.3f}"
def h3(x): return str(Decimal(str(x)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
def s3(x): return "0.000" if round(x, 3) == 0 else f"{x:+.3f}".replace("-", MINUS)
def ci3(lo, hi): return f'<span class="ci">[{s3(lo)}, {s3(hi)}]</span>'
def arm(a): return f"<code>{a}</code><small>{ARM_SUB[a]}</small>"
def pair(p): return " ".join(f"<code>{x}</code>" if x in ARMS else MINUS for x in p.split())
def excl(v): return v[1] > 0 or v[2] < 0
def dcell(v, span): return diverge(v[0], span, excl(v), label=s3(v[0])) + " " + ci3(v[1], v[2])
def unfinished(fin):
    c, r = fin.get("cap", 0), fin.get("repetition", 0)
    return "0" if not c + r else f"{c} cap / {r} loop"


def pair4(p): return " ".join(f"<code>{x}</code>" if x in ARMS4 else MINUS for x in p.split())
def iv3(v): return f"{s3(v[0])} [{s3(v[1])}, {s3(v[2])}]"
def span(vals, fmt):
    lo, hi = fmt(min(vals)), fmt(max(vals))
    return lo if lo == hi else f"{lo} to {hi}"


def reference_sections(S, h2, gh):
    """The reference checkpoint, the scoring capture on it and amendment 1: added after the results were read. Returns the
    paragraph for the lede, the bullet for the reading and the three sections. Sentences that state a reading check the
    numbers they rest on, so the text cannot outlive a change in the data."""
    RF, CA, AM, LA = S["reference"], S["capture"], S["amendment_1"], S["launch"]
    BL, PD, IV = RF["by_length"], RF["paired"], RF["intervals"]
    rp = [f"{REF} - {a}" for a in ARMS]
    ra, rh, rc = (PD[p]["score"]["all"] for p in rp)
    rc_long, rc_short, rc_strict = PD[rp[2]]["score"]["64k+128k"], PD[rp[2]]["score"]["4k+16k"], PD[rp[2]]["every_field_right"]["all"]
    if excl(ra) or excl(rh) or not excl(rc) or not excl(rc_long) or excl(rc_short) or excl(rc_strict):
        raise SystemExit("v5 page: the reference checkpoint's intervals no longer match the reading written for them")
    if any(excl(PD[p]["every_field_right"][k]) for p in rp for k in PD[p]["every_field_right"]):
        raise SystemExit("v5 page: an every-field-right interval of the reference checkpoint excludes 0")
    code = f"<code>{REF}</code>"
    req, same = RF["requests"][REF], RF["prompt_tokens_equal_to_anchor"][REF]

    intro = (f"<p>{code} is a reference checkpoint added after the results above were read: <code>{E(RF['checkpoint'])}</code>, a "
             f"{E(RF['what'])}. Same engine release and image, same drafter, the same 60 items at the same four lengths, the same "
             f"seeds, reply cap, concurrency and sampling settings; the two single-message passes only ({E(RF['ran'])}). "
             f"{n0(req)} requests, {RF['errors'][REF]} errors; prompt tokens equal to <code>anchor</code>'s on {same} of {req}. "
             f"{E(RF['loading'])} {E(RF['upstream_status'])}</p>"
             f"<p><b>{E(RF['whole_checkpoint'])}</b> It is outside the frozen comparison, and every interval in this section is post "
             "hoc. <code>anchor</code> stays the reference of the probe, not a recommendation.</p>")

    def sc(a, k): return BL[a][k]["score"]
    rows = [[arm(a)] + [bar(sc(a, k)[0], 1.0, f3(sc(a, k)[0]), sub=f'all 8 right {BL[a][k]["right"]} of {BL[a][k]["n"]}') for k, _ in LENS] +
            [f'{f3(sc(a, "all")[0])} <span class="ci">[{f3(sc(a, "all")[1])}, {f3(sc(a, "all")[2])}]</span>',
             f'{BL[a]["all"]["right"]} of {BL[a]["all"]["n"]}'] for a in ARMS4]
    by_pass = "; ".join(f'<code>{a}</code> {f3(BL[a]["128k"]["score_by_pass"][0])} and {f3(BL[a]["128k"]["score_by_pass"][1])}' for a in ARMS4)
    fin = " / ".join(f3(BL[a]["128k"]["score_finished_only"]) for a in ARMS4)
    t_score = rich("Share of answer fields right, with the reference checkpoint", "Single message, two passes pooled (120 requests per "
                   "cell). Unfinished replies score 0. Second figure: replies with every field right. Interval: 95% over items",
                   ["Arm"] + [n for _, n in LENS] + ["All lengths", "Every field right, all lengths"], rows,
                   foot=f"The two passes at 127K, pass 1 and pass 2: {by_pass}. Among finished replies at 127K: {fin} (same arm order).")

    CL = ("right", "1 wrong", "2 wrong", "3+ wrong", "cap", "repetition")
    rows = [[arm(a)] + [str(BL[a]["all"]["classes"].get(c, 0)) for c in CL] for a in ARMS4]
    t_cls = rich("What each reply came to", "Of 480 replies per arm: four lengths, two passes",
                 ["Arm", "Every field right", "1 field wrong", "2 wrong", "3 or more wrong", "Hit the reply cap", "Loop abort"], rows,
                 foot="Loop abort: the engine's repetition abort, finish class <code>repetition</code> in the per-request tables. Hit "
                      "the reply cap: finish class <code>cap</code>. Both score 0.")

    rows = [[pair4(p), dcell(PD[p]["score"]["all"], 0.08), dcell(PD[p]["score"]["4k+16k"], 0.08), dcell(PD[p]["score"]["64k+128k"], 0.08),
             badge(excl(PD[p]["score"]["all"]), "excludes 0", "includes 0"), dcell(PD[p]["every_field_right"]["all"], 0.08)] for p in rp]
    LAB = {"all": "all lengths", "4k": "4K", "16k": "16K", "64k": "64K", "128k": "127K", "4k+16k": "4K and 16K pooled", "64k+128k": "64K and 127K pooled"}
    ex = "; ".join(f'{LAB[x["lengths"]]} {iv3(x["value"])}' for x in IV["excluding_zero"])
    t_pair = rich("Reference checkpoint against each probe arm: paired difference", "Post hoc. Right of the line: the reference checkpoint "
                  "scored higher. Paired by item, 95% interval over the 60 items; bar edge = 0.08",
                  ["Difference", "Field score, all lengths", "4K and 16K", "64K and 127K", "Pooled interval", "Every field right, all lengths"], rows,
                  foot=f"{IV['computed']} intervals were computed for this section (six pairs, the three probe pairs included; field score "
                       f"and every field right, by length and pooled) with no correction for their number. {len(IV['excluding_zero'])} exclude 0, all "
                       f"{code} {MINUS} <code>compact</code> on field score: {ex}. On every field right no pair separates at any length. "
                       "An interval that excludes 0 in a post hoc reading is a lead, not a finding.")

    DC, FF, AG = RF["discordant"], RF["flip_floor"], RF["agreement"]
    rows = [("grp", "Reference checkpoint against a probe arm, same pass and seed: right only in the reference / right only in the probe arm")]
    rows += [[f"{code} vs <code>{a}</code>"] + [f"{DC[f'{REF} vs {a}'][ps][0]} / {DC[f'{REF} vs {a}'][ps][1]}" for ps in RF["passes"]] for a in ARMS]
    rows += [("grp", "Floor: one arm against its own second pass, pairs with a different outcome")]
    rows += [[f"<code>{a}</code>", str(FF[a]), ""] for a in ARMS4]
    tot = [sum(DC[f"{REF} vs {a}"][ps]) for a in ARMS for ps in RF["passes"]]
    t_agree = rich("How often \"every field right\" differs", "Counts of the 240 (item, length) pairs", ["Pair", "Pass 1", "Pass 2"], rows,
                   foot=f"Per pass the reference checkpoint and a probe arm differ on {min(tot)} to {max(tot)} of 240 pairs; one arm against its "
                        f"own second pass differs on {min(FF.values())} to {max(FF.values())}. Every field right in all four arms on "
                        f"{AG['all_four_right']} of {AG['of']} requests, in none on {AG['none_right']}.")

    def res(a): return sum(RF["launch"]["resident_weights_mib_rtx0_rtx1"] if a == REF else LA["resident_weights_mib_rtx0_rtx1"][a])
    def kvp(a): return RF["launch"]["kv_pool_tokens_serving"] if a == REF else LA["kv_pool_tokens_serving"][a]
    rows = [[arm(a), n0(res(a)), n0(kvp(a)), " / ".join(n0(x) for x in RF["pass_wall_s"][a]),
             " / ".join(f'{BL[a][k]["decode_tok_s_median"]:.1f}' for k, _ in LENS), f'{BL[a]["128k"]["ttft_s_median"]:.1f}'] for a in ARMS4]
    t_cost = rich("Memory, duration and speed", "Resident weights: both GPUs together, from the launch logs. Duration: wall time of each "
                  "single-message pass (240 requests, eight at once). Speed: median per stream at 4K / 16K / 64K / 127K",
                  ["Arm", "Resident weights, MiB", "KV pool, tokens", "Pass 1 / pass 2, s", "Tokens/s per stream", "First token at 127K, s"], rows,
                  foot="Speeds and durations are under a mixed load of eight requests and depend on what else was in the batch and on how long "
                       "the replies ran: they are not an arm comparison. The two launches of the reference checkpoint report the same figures.")

    ref_reading = ("<ul>"
                   f"<li><b>{code} against <code>anchor</code> and against <code>hqa</code>: no difference measured</b>, {iv3(ra)} and "
                   f"{iv3(rh)} pooled. Basis: two passes, 60 items, 480 requests per arm.</li>"
                   f"<li><b>{code} against <code>compact</code>: higher field score, post hoc</b>, {iv3(rc)} pooled and {iv3(rc_long)} at "
                   f"64K and 127K; at 4K and 16K {iv3(rc_short)}. The arm was added after the results were read and this is one of "
                   f"{IV['computed']} intervals, so it is a lead and not a finding. It is on the partial-credit score only: on every field "
                   f"right the pair does not separate ({iv3(rc_strict)}). Being a whole-checkpoint difference, it does not say which "
                   "component carries it.</li>"
                   f"<li><b>Accuracy falls with length in the reference checkpoint as in the probe arms</b> ({f3(sc(REF, '4k')[0])} at 4K to "
                   f"{f3(sc(REF, '128k')[0])} at 127K; finished replies only at 127K {f3(BL[REF]['128k']['score_finished_only'])}, "
                   f"<code>anchor</code> {f3(BL['anchor']['128k']['score_finished_only'])}).</li></ul>")

    # ---- scoring capture
    BA, AT = CA["between_arms"], CA["against_text"]
    def pct(x, nd=2): return f"{100 * x:.{nd}f}%"
    def k4(x): return f"{x:.4f}" if round(x, 4) >= 0.0001 else f"{x:.6f}"
    def s4(x): return "0.0000" if round(x, 4) == 0 else f"{x:+.4f}".replace("-", MINUS)
    def nat(x): return f"{x:+.2f}".replace("-", MINUS)
    def iv4(v): return f'{s4(v[0])} <span class="ci">[{s4(v[1])}, {s4(v[2])}]</span>'
    PATHS = (("prefill", "Prefill path"), ("decode", "Decode path"))
    rows = []
    for path, lab in PATHS:
        rows.append(("grp", f"{lab}, {n0(AT[path]['rows'])} positions"))
        for a in ARMS4:
            d = AT[path]["arms"][a]
            rows.append([arm(a), f'{d["nll"]:.4f}', iv4(d["nll_minus_ref"]) if a != "anchor" else "", f'{d["top1_given"]:.4f}',
                         iv4(d["top1_minus_ref"]) if a != "anchor" else ""])
    bands = list(AT["prefill"]["arms"][REF]["nll_by_band"])
    bd = [AT["prefill"]["arms"][REF]["nll_by_band"][b] - AT["prefill"]["arms"]["anchor"]["nll_by_band"][b] for b in bands]
    t_abs = rich("Against the given text", "NLL of the given token in nats (lower = predicted better) and the share of positions whose most "
                 f"likely token is the given one. Differences are arm minus <code>anchor</code>; interval: {E(AT['interval'])}",
                 ["Arm", "NLL", "NLL minus anchor", "Top token is the given one", "Minus anchor"], rows,
                 foot="One capture per arm; intervals are not corrected for their number.")
    rows = [[arm(a)] + [f'{AT["prefill"]["arms"][a]["nll_by_band"][b]:.3f}<small>top token given {AT["prefill"]["arms"][a]["top1_given_by_band"][b][0]:.3f}</small>'
                        for b in bands] for a in ARMS4]
    t_band = rich("Against the given text, by depth", "Prefill path. NLL of the given token in nats; second figure: the share of positions "
                  "whose most likely token is the given one. Values per band are shown without intervals",
                  ["Arm"] + [f"{b} tokens" for b in bands], rows,
                  foot=f"{code} minus <code>anchor</code> in NLL by depth: " + "; ".join(f"{b} {s4(x)}" for b, x in zip(bands, bd)) + ".")
    rows = []
    for a in ("compact", REF):
        d = AT["prefill"]["arms"][a]["nll_difference_rows"]; c = d["by_text"]["code"]
        rows.append([arm(a), nat(d["sum"]), s4(d["median"]),
                     f'{d["rows_over_1_nat"]} ({pct(d["rows_over_1_nat"] / AT["prefill"]["rows"], 1)})', nat(d["sum_of_those"]),
                     f'{c["rows_over_1_nat"]} positions, {nat(c["sum_of_those"])}', nat(c["sum"]),
                     s4(d["mean_trimmed_1pct_each_side"]), pct(d["share_rows_arm_better"], 1)])
    def col(path): return ", ".join(f'<code>{a}</code> {AT[path]["arms"][a]["collapse_rows"]["n"]}' for a in ARMS4)
    ctexts = sorted({x for a in ARMS4 for x in AT["prefill"]["arms"][a]["collapse_rows"]["by_text"]})
    if any(AT["decode"]["arms"][a]["collapse_rows"]["n"] for a in ARMS4) or ctexts != ["code"]:
        raise SystemExit("v5 page: collapse rows are no longer prefill-only and in the text `code`")
    t_heavy = rich("Where the NLL difference from <code>anchor</code> sits", "Prefill path, per-position NLL of the arm minus "
                   "<code>anchor</code>'s, nats; below 0 = the arm predicts the given token better there",
                   ["Arm", "Sum over all positions", "Median per position", "Positions more than 1 nat apart", "Their sum",
                    "Of those, in the text <code>code</code>", "Sum in <code>code</code>", "Mean, 1% trimmed each side", "Positions where the arm is ahead"], rows,
                   foot=f"Positions where one arm gives the given token under 0.05 while every other arm gives it at least 0.9 "
                        f"(prefill path): {col('prefill')}, all in the text <code>code</code>; decode path: none in any arm.")
    kr = [v["kl_median"] for k, v in BA["prefill"]["all"]["pairs"].items() if REF in k]; kp = [v["kl_median"] for k, v in BA["prefill"]["all"]["pairs"].items() if REF not in k]
    tr = [v["top1_differs"] for k, v in BA["prefill"]["all"]["pairs"].items() if REF in k]; tp = [v["top1_differs"] for k, v in BA["prefill"]["all"]["pairs"].items() if REF not in k]
    hr, hc = (AT["prefill"]["arms"][a]["nll_difference_rows"] for a in (REF, "compact"))
    t1 = [AT[path]["arms"][a]["top1_minus_ref"] for path, _ in PATHS for a in ARMS4 if a != "anchor"]
    share = hr["rows_over_1_nat"] / AT["prefill"]["rows"]
    if (min(kr) <= max(kp) or min(tr) <= max(tp) or any(excl(v) for v in t1) or max(bd) >= 0.003 or hr["median"] != 0
            or hr["share_rows_arm_better"] >= 0.5 or not 0.005 < share < 0.015
            or 2 * hr["by_text"]["code"]["rows_over_1_nat"] <= hr["rows_over_1_nat"]):
        raise SystemExit("v5 page: the scoring capture's numbers no longer match the reading written for them")
    cap_intro = (f"<p>One capture of {code} in which the engine scores given texts instead of generating: five long texts (not the task "
                 "items), assistant frame, on the prefill path and on the decode path, read beside the same capture of the three probe arms. "
                 "Exploratory: one capture per arm, no correction for the number of comparisons. The whole-checkpoint statement above "
                 "applies.</p>"
                 "<p><b>Distance from the unquantized BF16 model is not measured for these four configurations in this run.</b> All four "
                 "are quantized: <code>anchor</code> has a BF16 core and K4 experts, so a difference from <code>anchor</code> is a "
                 'difference from another quantization. The <a href="precision.html">BF16-referenced panels</a> of this repository (texts '
                 "to 14.4K tokens) cover other checkpoints. What this capture references to something fixed is the given text.</p>"
                 "<p>The dumps and per-position files are not published; the numbers are in "
                 f'{gh(f"{RD}/exploratory/capture_abs.json", "<code>capture_abs.json</code>")} and '
                 f'{gh(f"{RD}/exploratory/capture_pairs.json", "<code>capture_pairs.json</code>")}.</p>')
    cap_reading = ("<ul>"
                   f"<li><b>{code} is not measurably worse at predicting the text than <code>anchor</code></b>: over the whole capture its "
                   "most likely token is the given one as often as for <code>anchor</code> (the difference's interval spans zero on "
                   "both paths, as it does for <code>hqa</code> and <code>compact</code>). By depth band its NLL is below "
                   "<code>anchor</code>'s or within 0.003 of it; the per-band values carry no interval.</li>"
                   "<li><b>The lower mean NLL (prefill path) is carried by about 1% of positions, most of them in one text, and is not read as an "
                   f"improvement</b>: {hr['rows_over_1_nat']} of {n0(AT['prefill']['rows'])} positions carry {nat(hr['sum_of_those'])} of "
                   f"the {nat(hr['sum'])} nat, {100 * hr['sum_of_those'] / hr['sum']:.0f}% of the sum "
                   f"({hr['by_text']['code']['rows_over_1_nat']} of them in <code>code</code>); the median per-position difference is "
                   "zero and the arm is ahead on fewer than half of the positions. <code>compact</code>'s smaller sum also sits "
                   f"mostly in <code>code</code> ({nat(hc['sum'])} nat in all, {nat(hc['by_text']['code']['sum'])} of it in <code>code</code>) "
                   f"but is less concentrated in single positions ({hc['rows_over_1_nat']} positions over 1 nat carry "
                   f"{nat(hc['sum_of_those'])} of it).</li></ul>")
    cap_between = ("<p><b>Between arms (not a distance from the BF16 model).</b> The three probe arms share their experts, so the "
                   f"distance between two of them reflects the settings outside the experts alone (the core and, for <code>anchor</code>, the output head): median KL {span(kp, k4)}, most likely token different "
                   f"on {span(tp, pct)} of positions (prefill path). {code} has its own experts, so its distance to any probe arm "
                   f"({span(kr, k4)}; {span(tr, pct)}) includes both expert quantizations and does not rank it against the probe arms by "
                   f'closeness to the BF16 model. Full tables: {gh(f"{RD}/RESULTS.md", "<code>RESULTS.md</code>")}, section 10, and '
                   f'{gh(f"{RD}/exploratory/capture_pairs.json", "<code>capture_pairs.json</code>")}.</p>')

    # ---- amendment 1
    am_link = gh(f"{RD}/{AM['file']}", "Amendment 1")
    amend = (f"<p>{am_link} (written {E(AM['written'])}; sha256 <code>{AM['sha256']}</code>) was written after {E(AM['written_after'])} "
             f"and before {E(AM['written_before'])}. It adds {E(AM['adds'])}. Reading rule: {E(AM['rule'])}. No eight-turn pass and no "
             "items are added. The protocol file is unchanged and its hash still holds.</p>")
    rows = [[arm(a), badge(False, "done", "pending"), badge(False, "done", "pending")] for a in ARMS4]
    t_am = rich("Passes added by amendment 1", "In progress. No number from these passes is on this page",
                ["Arm", "Single message, pass 3", "Single message, pass 4"], rows)

    lede = (f"<p>Added after these results were read: a reference checkpoint in another quantisation format, {code}, on the same items "
            f"(two single-message passes). No difference from <code>anchor</code> ({iv3(ra)}) or from <code>hqa</code> ({iv3(rh)}) is "
            "measured; it differs from the arms as a whole checkpoint, so no difference from an arm is attributable to one component "
            '(<a href="#reference">reference checkpoint</a>). Two further single-message passes per arm are in progress under '
            '<a href="#amendment">amendment 1</a>; none of their numbers is on this page.</p>')
    bullet = (f"<li><b>Reference checkpoint {code}, added after the results were read: no difference from <code>anchor</code> or "
              f"<code>hqa</code> measured</b> ({iv3(ra)} and {iv3(rh)} pooled). Against <code>compact</code> its field score is higher post "
              f"hoc ({iv3(rc)}), on the partial-credit score only: a lead, not a finding. Each is a whole-checkpoint difference "
              '(<a href="#reference">details</a>).</li>')
    body = (h2("reference", "Reference checkpoint: EXLR8 K4") + intro + ref_reading + t_score + t_cls + t_pair + t_agree + t_cost +
            h2("capture", "Scoring capture on the reference checkpoint") + cap_intro + cap_reading + t_abs + t_band + t_heavy + cap_between +
            h2("amendment", "Amendment 1: passes 3 and 4, in progress") + amend + t_am)
    data = (f'<p class="sign">Reference checkpoint: {gh(f"{RD}/analysis/samples-reference.csv", "<code>samples-reference.csv</code>")} '
            f'(one row per request, no text) and {gh(f"{RD}/analysis/reference.py", "<code>reference.py</code>")}, which recomputes its '
            f'tables from the two CSVs into {gh(f"{RD}/analysis/REFERENCE.json", "<code>REFERENCE.json</code>")} (standard library only).</p>')
    return lede, bullet, body, data


def page_v5(S, page, h2, gh, details):
    F = S["frozen_rule"]["differences"]
    SL, BF, T, LG, PH, LA = S["score_by_length"], S["by_family"], S["turns"], S["ledger_exploratory"], S["post_hoc_long_context"], S["launch"]
    ha, ca, hc = (F[p]["single"]["all"] for p in PAIRS)
    lo4 = min(SL[a]["single"]["4k"]["score"] for a in ARMS); hi4 = max(SL[a]["single"]["4k"]["score"] for a in ARMS)
    lo127 = min(SL[a]["single"]["128k"]["score"] for a in ARMS); hi127 = max(SL[a]["single"]["128k"]["score"] for a in ARMS)
    lc = PH["64k+128k"]["compact - anchor"]["ledger"]
    kv = LA["kv_pool_tokens_serving"]

    lede = ("<p>CuteAFD v5.0.0 adds <code>ATTENTION_MODE</code>, which runs the HQA checkpoint of GLM 5.3 Flash at two core precisions; "
            "a locally derived all-BF16 core is the reference here. On graded tasks from 4K to "
            "127K tokens, neither setting is measurably behind the reference: "
            f"<code>hqa</code> {MINUS} <code>anchor</code> {s3(ha[0])} [{s3(ha[1])}, {s3(ha[2])}] and "
            f"<code>compact</code> {MINUS} <code>anchor</code> {s3(ca[0])} [{s3(ca[1])}, {s3(ca[2])}] in field score, pooled over lengths. "
            f"Accuracy falls with length in every probe arm, <code>anchor</code> included ({lo4:.2f} at 4K, {lo127:.2f} to {hi127:.2f} at 127K), so "
            "that loss is not produced by core precision; a third to a half of it is replies that did not finish. One slice leans "
            "against the K6 core, running totals at 64K and 127K, and twenty items do not decide it. The eight-turn pass did not test history written by the model; its design is to be revised.</p>")

    # ---- what was tested
    setup = rich(
        "", "One engine (CuteAFD v5.0.0, unmodified launcher), two RTX PRO 6000 Max-Q, experts local. K4 experts and the same drafter in every arm",
        ["Arm", "What runs", "Checkpoint", "Launch setting"],
        [[f"<code>{a}</code>", E(S["arms"][a]["what"]), E(S["arms"][a]["checkpoint"]), f'<code>{E(S["arms"][a]["settings"])}</code>'] for a in ARMS],
        foot="The arms differ in the precision of the tensors outside the experts: the core and, for <code>anchor</code>, the output head, which it keeps at BF16 with the engine's FP8 conversions off. Nothing on this page measures expert quantisation. "
             "<code>anchor</code> is the reference the others are read against, not a recommended setting.")
    st = S["settings"]
    setup += (f'<p><b>Checkpoint availability.</b> <code>hqa</code> and <code>compact</code> load the K4-Core-K6-HQA checkpoint: '
              f'{E(S["hqa_checkpoint"]["what"])}. {E(S["hqa_checkpoint"]["availability"])}</p>'
              f'<p><b>Tasks.</b> {E(st["items"])}. Each item hides a small set of records among distractors and asks for eight exact values: '
              "<code>join</code> looks records up across two tables, <code>ledger</code> keeps running totals over events spread through "
              "the context, <code>trace</code> follows a chain of references. The same item is rendered at every length; only the amount "
              "of distractor text changes. Per arm: two single-message passes and one pass that delivers the same records over eight "
              f'turns. {E(st["sampling"]).capitalize()}; reply cap {n0(st["reply_cap_tokens"])} tokens; {st["concurrency"]} requests at '
              f'once. Protocol frozen {E(st["frozen"])}. Graded runs: 2026-11-10 19:55 to 2026-11-11 08:28.</p>'
              "<p><b>Terms.</b> The <i>experts</i> are the per-layer expert matrices; the <i>core</i> is the other matrices of the "
              "layers (attention among them), and the <i>head</i> is the output projection. K4 and K6 are the checkpoint producer's "
              "EXL3 quantisation levels, K6 the finer; BF16 is the original precision. The <i>drafter</i> is the small "
              "model that proposes tokens the main model verifies. <i>Prefill</i> is processing the prompt, <i>decode</i> is generating "
              "the reply. \"Cap\" is the reply limit in tokens (32,768 for answers, 4,096 for the delivery turns of the eight-turn "
              "pass); \"loop\" is the engine's repetition abort (finish class <code>repetition</code>).</p>"
              "<p><b>Score.</b> Fields right / fields, read from the reply's last answer line; a reply that hit the cap or was ended by "
              "the loop abort scores 0. Differences are paired by item, with a 95% interval from resampling the 60 items.</p>")

    # ---- score by length
    rows = []
    for cell, lab in (("single", "Single message, two passes pooled (120 requests per cell)"), ("turns-p8", "Eight turns, one pass (60 requests per cell)")):
        rows.append(("grp", lab))
        for a in ARMS:
            rows.append([arm(a)] + [bar(SL[a][cell][k]["score"], 1.0, f3(SL[a][cell][k]["score"]),
                                        sub=f'all 8 right {h3(SL[a][cell][k]["every_field_right"])}') for k, _ in LENS] +
                        [unfinished(SL[a][cell]["128k"]["finish"])])
    def unf(cell, k): return " / ".join(str(SL[a][cell][k]["unfinished"]) for a in ARMS)
    fin127 = " / ".join(f3(SL[a]["single"]["128k"]["score_finished_only"]) for a in ARMS)
    bylen = rich("Share of answer fields right", "Unfinished replies score 0. Second figure: share of replies with every field right",
                 ["Arm"] + [n for _, n in LENS] + ["Unfinished at 127K"], rows,
                 foot="Every arm loses 0.07 to 0.09 between 4K and 127K, the reference 0.08. A third to a half of that is replies "
                      f"that did not finish: among finished replies the single-message score at 127K is {fin127} "
                      "(<code>anchor</code> / <code>hqa</code> / <code>compact</code>). The arms share the model, the K4 experts, the "
                      "engine, the drafter, the sampling settings and the reply cap, so the loss sits somewhere among those. "
                      f"Unfinished replies at the other lengths, same arm order: none at 4K; 16K single 0 / 0 / 0, eight turns {unf('turns-p8', '16k')}; "
                      f"64K single {unf('single', '64k')}, eight turns {unf('turns-p8', '64k')}.")

    # ---- differences
    rows = []
    for cell, lab in (("single", "Single message, two passes"), ("turns-p8", "Eight turns, one pass")):
        rows.append(("grp", lab))
        for p in PAIRS:
            d = F[p][cell]
            rows.append([pair(p)] + [dcell(d[k], 0.08) for k, _ in LENS] + [dcell(d["all"], 0.08), badge(excl(d["all"]), "excludes 0", "includes 0")])
    diffs = rich("Paired difference in field score (frozen rule)", "Right of the line: the first-named arm scored higher. 95% interval over items; bar edge = 0.08",
                 ["Difference"] + [n for _, n in LENS] + ["All lengths", "Pooled interval"], rows,
                 foot=f"No interval in this table excludes 0. Pooled over lengths, a loss larger than about {abs(ha[1]):.3f} for <code>hqa</code> and "
                      f"{abs(ca[1]):.3f} for <code>compact</code> against the reference is outside the interval. Single cells at 64K and "
                      "127K are wider: they leave room for a loss of up to about 0.05 to 0.07.")
    FL = S["frozen_rule"]["flips_single"]
    def fl(d, first="b_only", second="a_only"):
        return f'{h3(d["discordant"])} <span class="ci">({d[first]} / {d[second]}; p {d["p_exact"]:.2f})</span>'
    fa = FL["hqa - anchor"]["floor"]["a rep0|rep1"]; fh = FL["hqa - anchor"]["floor"]["b rep0|rep1"]; fc = FL["compact - anchor"]["floor"]["b rep0|rep1"]
    rows = [("grp", "Between two arms, same pass and seed")]
    rows += [[pair(p), fl(FL[p]["between"]["rep0"]), fl(FL[p]["between"]["rep1"])] for p in PAIRS]
    rows += [("grp", "Floor: one arm against itself, pass 1 against pass 2"),
             ["<code>anchor</code>", fl(fa, "a_only", "b_only"), ""], ["<code>hqa</code>", fl(fh, "a_only", "b_only"), ""],
             ["<code>compact</code>", fl(fc, "a_only", "b_only"), ""]]
    flips = rich("How often \"every field right\" differs", "Share of the 240 (item, length) pairs with different outcomes "
                 "(right only in the first-named arm / only in the second; floor rows: only in pass 1 / only in pass 2; exact McNemar p)", ["Pair", "Pass 1", "Pass 2"], rows,
                 foot="Two arms disagree about as often as one arm disagrees with its own second pass (distinct seeds), and no "
                      "one-sided imbalance is detected: the smallest p is 0.05 (<code>compact</code> against <code>anchor</code>, pass 2), "
                      "and the same pair splits evenly in pass 1.")

    # ---- families
    rows = []
    for fam in ("join", "ledger", "trace"):
        rows.append(("grp", fam))
        for a in ARMS:
            rows.append([arm(a)] + [bar(BF[a][fam][k]["score"], 1.0, f3(BF[a][fam][k]["score"]),
                                        sub=f'{BF[a][fam][k]["every_field_right"][0]} of {BF[a][fam][k]["every_field_right"][1]}') for k, _ in LENS])
    fams = rich("By task family", "Single message, two passes: field score, then replies with every field right of 40",
                ["Arm"] + [n for _, n in LENS], rows,
                foot="<code>trace</code> is level to 127K in every arm. <code>join</code> stays near ceiling to 64K, and its drop at "
                     "127K is replies that did not finish (" + " / ".join(str(BF[a]["join"]["128k"]["unfinished"]) for a in ARMS) +
                     " of 40): finished <code>join</code> replies score " + " / ".join(f3(BF[a]["join"]["128k"]["score_finished_only"]) for a in ARMS) +
                     " there. Among finished replies the length effect is <code>ledger</code>: running totals over events spread through the context.")

    # ---- ledger, exploratory and post hoc
    LD = LG["differences"]["single"]
    rows = [[pair(p)] + [dcell(LD[p][k], 0.2) for k, _ in LENS] for p in PAIRS]
    led = rich("<code>ledger</code> alone: paired difference in field score", "By family, as the protocol asks of every table; outside the frozen comparison rule. 20 items, single message, two passes; bar edge = 0.2",
               ["Difference"] + [n for _, n in LENS], rows)
    L2 = PH["64k+128k"]
    rows = [[pair(p), dcell(L2[p]["all families"]["score"]["single"], 0.2), dcell(L2[p]["ledger"]["score"]["single"], 0.2),
             dcell(L2[p]["ledger"]["every_field_right"]["single"], 0.3)] for p in PAIRS]
    v3 = L2["compact - anchor"]["ledger"]["every_field_right"]["single+turns"]
    post = rich("64K and 127K pooled", f"Post hoc, added after the results were read. 48 such intervals were computed; two exclude 0, both <code>compact</code> {MINUS} <code>anchor</code> on <code>ledger</code> every-field-right. Single message, two passes",
                ["Difference", "All families, field score", "<code>ledger</code>, field score", "<code>ledger</code>, every field right"], rows,
                foot=f"With the eight-turn pass included, <code>compact</code> {MINUS} <code>anchor</code> on <code>ledger</code> every-field-right is "
                     f"{s3(v3[0])} [{s3(v3[1])}, {s3(v3[2])}]. An interval that excludes 0 in a post hoc slice is a lead, not a finding.")
    lf, wf = LG["left_out_event_fields_64k_128k"], LG["wrong_fields_single_64k_128k"]
    rows = [[f"<code>{a}</code>", lf[a]["single-rep0"], lf[a]["single-rep1"], lf[a]["turns-p8-rep0"],
             f'{wf[a]["wrong"]} of {wf[a]["finished_fields"]}'] for a in ARMS]
    left = rich("Wrong <code>ledger</code> fields at 64K and 127K", "Finished replies. \"Left out\": the wrong value equals the right total with one or two of its events missing (a heuristic; a value can match by coincidence)",
                ["Arm", "Left out, pass 1", "Left out, pass 2", "Left out, eight turns", "All wrong fields, two single passes"], rows,
                foot="<code>compact</code>'s count differs between its own two passes by as much as it differs from the other arms.")
    lh = PH["64k+128k"]["hqa - anchor"]["ledger"]["score"]["single"]
    ledger_txt = ("<p>In the single-message passes, <code>ledger</code> field score at 64K and at 127K orders <code>anchor</code>, "
                  f"<code>hqa</code>, <code>compact</code>. <code>hqa</code> is nominally lower than the reference by {abs(lh[0]):.3f} pooled "
                  f"over the two lengths, [{s3(lh[1])}, {s3(lh[2])}], and every one of its intervals includes 0. <code>compact</code> is nominally "
                  f"{abs(LD['compact - anchor']['64k'][0]):.2f} lower at 64K and {abs(LD['compact - anchor']['128k'][0]):.2f} at 127K with intervals "
                  f"that include 0; pooled over the two lengths the field-score gap is {s3(lc['score']['single'][0])} "
                  f"[{s3(lc['score']['single'][1])}, {s3(lc['score']['single'][2])}], and only the strict measure excludes 0. Twenty items "
                  f"cannot tell \"the K6 core costs nothing on running totals at long context\" from \"it costs about {abs(lc['score']['single'][1]):.2f} in field score\". An "
                  f'extension with more <code>ledger</code> items was written down before the data and is held, not run '
                  f'({gh(f"{RD}/notes/ledger-extension-hold.md", "note")}).</p>')

    # ---- turns
    TM, MW, IC = T["turns_minus_single"], T["model_written_share"], T["intermediate_caps"]
    rows = [[arm(a)] + [dcell(TM[a][k], 0.12) for k, _ in LENS] for a in ARMS]
    turns_t = rich("Eight turns minus single message, same items", "Paired by item; bar edge = 0.12", ["Arm"] + [n for _, n in LENS], rows)
    rows = [[f"<code>{a}</code>"] + [f'{100 * MW[a][k]["median"]:.1f}% <span class="ci">(max {100 * MW[a][k]["max"]:.1f}%)</span>' for k, _ in LENS] +
            [f'{IC[a]["turns_not_stop"]} in {IC[a]["sessions_with_one"]} sessions'] for a in ARMS]
    share_t = rich("How much of the final prompt the model wrote", "Median over 60 sessions per cell: tokens generated in the eight delivery turns "
                   "(thinking included, which stays in context) / prompt tokens of the final turn",
                   ["Arm"] + [n for _, n in LENS] + ["Delivery turns that ran to the 4,096 cap"], rows,
                   foot=f'Of {n0(IC["anchor"]["delivery_turns"])} delivery turns in {IC["anchor"]["sessions"]} sessions per arm. Delivery turns whose reply was '
                        "not the bare acknowledgement: " + " / ".join(str(IC[a]["turns_not_the_acknowledgement"]) for a in ARMS) +
                        " (<code>anchor</code> / <code>hqa</code> / <code>compact</code>); " + " / ".join(str(IC[a]["of_which_finished_with_stop"]) for a in ARMS) +
                        " of those finished on their own and the rest ran to the cap. The session's final answer was scored as usual. "
                        f'{IC["compact"]["most_in_one_session"]} of <code>compact</code>\'s {IC["compact"]["turns_not_stop"]} capped turns were in one session. Descriptive.')
    turns_txt = (f"<p><b>Scope of this pass.</b> {E(T['scope'])}</p>"
                 "<p>What the pass does show: delivering the same input as eight messages, each resumed from the prefix cache, shows no "
                 "accuracy cost. From 16K to 127K every interval includes 0, and a cost of up to about 0.07 is not excluded; at 4K eight "
                 "turns score slightly higher in <code>anchor</code> and <code>hqa</code> (those two intervals exclude 0).</p>")

    # ---- memory
    rows = []
    for a in ARMS:
        L = LA["serving"][a][0]; g0, g1 = L["gpus"]["rtx0"], L["gpus"]["rtx1"]
        free = [g["cap_mib"] - g["weights_mib"] - g["workspaces_mib"] - g["reserve_mib"] - g["kv_pool_mib"] for g in (g0, g1)]
        rows.append([arm(a), bar(L["coordinator_weights_gib"], 7, f'{L["coordinator_weights_gib"]:.2f} GiB'), E(L["head"]),
                     f'{n0(g0["weights_mib"])} / {n0(g1["weights_mib"])}', f'{n0(g0["workspaces_mib"])} / {n0(g1["workspaces_mib"])}',
                     n0(L["kv_pool_tokens"]), f"{n0(free[0])} / {n0(free[1])}"])
    sc = LA["kv_pool_tokens_scoring_launches"]
    mem = rich("What each arm loads and is admitted", "From each serving launch's log; the three launches of an arm report the same figures. MiB per GPU: first / second",
               ["Arm", "Coordinator weights", "Head", "Resident weights, MiB", "Workspaces, MiB", "KV pool, tokens", "Left under the cap, MiB"], rows,
               foot=f"Every arm was admitted the configured maximum KV pool ({n0(kv['anchor'])} tokens) in all nine serving launches, so on "
                    "this hardware the cheaper settings buy memory headroom, not context room. A smaller pool for <code>anchor</code> "
                    f"({n0(sc['anchor'][0])} tokens) was seen only in the scoring launches of the exploratory depth profile (16 requests at once). "
                    "Corrected 2026-11-11: the results text first carried that scoring-launch figure into the graded-run table.")

    # ---- descriptive
    def four(a, key, fmt): return " / ".join(fmt(SL[a]["single"][k][key]) for k, _ in LENS)
    rows = [[arm(a), four(a, "reasoning_chars_median", n0), four(a, "completion_tokens_median", n0),
             four(a, "decode_tok_s_median", lambda x: f"{x:.1f}"), four(a, "ttft_s_median", lambda x: f"{x:.1f}")] for a in ARMS]
    desc = rich("Thinking length and speed", "Medians over all replies, finished or not, at 4K / 16K / 64K / 127K; single message, two passes",
                ["Arm", "Thinking, characters", "Output tokens", "Tokens/s per stream", "First token, s"], rows,
                foot="Speeds are per stream under a mixed load of eight requests and depend on what else was in the batch: they are not an "
                     "arm comparison. Thinking grows with context length in every arm.")

    checks = ("<p>Before the graded runs the protocol records five exploratory checks (sections 10 to 13 of "
              f'{gh(f"{RD}/protocol/PROTOCOL.md", "the protocol")}; one capture each, not measurements):</p><ul>'
              "<li><b>Depth profile.</b> Five arms scored the same long texts (to 128K tokens; not the task items) position by position: the "
              "three above, <code>fp8c</code> (<code>ATTENTION_MODE=fp8-compact</code>) and <code>core-fp8</code> (the BF16-core checkpoint "
              "with the engine's default FP8 conversions on). No arm was measurably "
              "worse than the reference at predicting the text at any depth; the arms differ from each other by about the same small "
              "amount, with no ordering by precision.</li>"
              "<li><b>FP8 prefill switch.</b> On the HQA checkpoint, <code>GLM5_FLASH_FP8_PREFILL=off</code> changed the load line and "
              "left every recorded distribution bit-identical (11,648 rows), so it was dropped as an arm.</li>"
              "<li><b>Launch to launch.</b> Two launches of <code>anchor</code> and two of <code>hqa</code> gave bit-identical rows "
              "(11,648 of 11,648 each): scored rows carry no launch-to-launch noise. Sampled generation still varies between passes.</li>"
              "<li><b>Cache path</b> (<code>hqa</code>, <code>compact</code>, <code>fp8c</code> and <code>hqa</code> with FP8 prefill off; "
              "<code>anchor</code> not in this step). A conversation resumed from the prefix cache matched a decode replay bit for bit "
              "in 45 of 46 conversations, counted over the four arms together; the "
              "exception is a harness artifact (a reply that ended inside the thinking block is rendered with a closing tag the model "
              "did not generate). A context prefilled in one piece and the same context built turn by turn are close but never "
              "bit-equal, in every arm.</li>"
              "<li><b>Batching</b> (same four arms). Greedy output was one text in all 260 requests per arm, alone or eight at once.</li></ul>")

    reading = ("<ul>"
               f"<li><b><code>hqa</code> against the reference: no difference measured</b>, {s3(ha[0])} [{s3(ha[1])}, {s3(ha[2])}] pooled; "
               "request-level disagreement at the level of one arm against its own second pass; nominally lower on long-context running "
               f"totals ({s3(lh[0])} [{s3(lh[1])}, {s3(lh[2])}]), interval including 0. Basis: 60 items at four lengths, two passes; "
               "strength: moderate (one model family, synthetic tasks).</li>"
               f"<li><b><code>compact</code> against the reference: no difference measured</b>, {s3(ca[0])} [{s3(ca[1])}, {s3(ca[2])}] pooled. "
               f"Its largest nominal gap is <code>ledger</code> at 64K and 127K ({s3(lc['score']['single'][0])} "
               f"[{s3(lc['score']['single'][1])}, {s3(lc['score']['single'][2])}]); that is open, not shown.</li>"
               f"<li><b><code>hqa</code> against <code>compact</code>: no difference measured</b>, {s3(hc[0])} [{s3(hc[1])}, {s3(hc[2])}] pooled.</li>"
               "<li><b>The long-context loss is shared.</b> The reference loses about as much as the other arms, so core precision does not "
               "produce it; a third to a half of it is replies that did not finish.</li>"
               "<li><b>Split delivery shows no accuracy cost</b> within intervals of about 0.07; whether model-written history does is untested here.</li></ul>")
    ref_lede, ref_bullet, ref_body, ref_data = reference_sections(S, h2, gh) if "reference" in S else ("", "", "", "")
    lede += ref_lede
    reading = reading[:-len("</ul>")] + ref_bullet + "</ul>"
    openq = "<ul>" + "".join(f"<li>{E(q)}</li>" for q in S["open_questions"]) + "</ul>"
    limits = "<p>" + (lambda t: t[:1].upper() + t[1:])("; ".join(E(x) for x in S["limits"])) + ".</p>"
    data = (f'<p class="sign">Numbers: {gh(f"{RD}/SUMMARY.json", "<code>SUMMARY.json</code>")}. Result as read, with dated corrections: '
            f'{gh(f"{RD}/RESULTS.md", "<code>RESULTS.md</code>")}. One row per request, no text: '
            f'{gh(f"{RD}/analysis/samples.csv", "<code>samples.csv</code>")}; {gh(f"{RD}/analysis/posthoc.py", "<code>posthoc.py</code>")} '
            f'recomputes the scores, differences and intervals from it (launch figures and the left-out counts come from logs and '
            f'replies, which are not in the table). Folder: {gh(RD, "<code>" + RD + "</code>")}. Reply texts are not published.</p>')

    repro = ("<ul>"
             f'<li><b>Recompute.</b> In {gh(RD, "the results folder")}, <code>python3 analysis/posthoc.py</code> (standard library only) '
             "rebuilds the scores, differences and intervals on this page from <code>samples.csv</code> and writes <code>POSTHOC.json</code>; "
             "<code>python3 tools/verify.py</code> at the repository root checks <code>docs/findings.json</code> against the same table. "
             "Run from a clean copy of the published folder on 2026-11-11: same output.</li>"
             "<li><b>Rebuild the inputs.</b> <code>drivers/gen_tasks.py --items 20 --first 100</code> regenerates the 240 rendered items "
             "from their seeds; it needs the <code>tokenizers</code> package and the model's <code>tokenizer.json</code> (set the path at "
             "the top of the script; its SHA-256 is checked). <code>items/measured/index.json</code> lists the SHA-256 of every rendered item. Regenerated from the published script on "
             "2026-11-11: 240 of 240 hashes match.</li>"
             "<li><b>Re-measure.</b> <code>chain.sh</code>, <code>drivers/run_tasks.py</code> and <code>configs/</code> are what ran, with the "
             "image digest and checkpoint revisions in <code>RUN.json</code>. The HQA checkpoint is no longer on the hub, so "
             "<code>hqa</code> and <code>compact</code> cannot be re-measured without a copy of it; <code>anchor</code>'s checkpoint is "
             "assembled locally, with every core matrix taken from the original BF16 weights, and was never a release. The items and "
             "the scoring do not depend on the engine.</li></ul>")
    body = (h2("reading", "What the results show") + reading +
            h2("arms", "What was tested") + setup +
            h2("by-length", "Score by length") + bylen +
            h2("differences", "Differences between arms") + diffs + flips +
            h2("families", "By task family") + fams +
            h2("ledger", "Running totals at long context") + ledger_txt + led + post + left +
            h2("turns", "Eight turns: what this pass tested") + turns_txt + turns_t + share_t +
            h2("memory", "What the cheaper settings buy") + mem +
            h2("descriptive", "Thinking length and speed") + desc +
            h2("checks", "Checks before the graded runs") + checks + ref_body +
            h2("open", "Open questions") + openq +
            h2("limits", "Limits") + limits +
            h2("reproduce", "Reproducing this") + repro + data + ref_data)
    page("v5.html", "CuteAFD v5.0.0: core precision at long context", lede, body)


def build(root, page, h2, gh, details):
    if (Path(root) / RD / "SUMMARY.json").exists():
        page_v5(load(root), page, h2, gh, details)
