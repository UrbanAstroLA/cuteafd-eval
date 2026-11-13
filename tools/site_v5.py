#!/usr/bin/env python3
"""Page for the CuteAFD v5.0.0 context probe (imported by tools/build_site.py). Standard library only.

Reads results/2026-11-10-context-probe/SUMMARY.json. Same grammar as tools/site_v4.py, whose cell builders it reuses:
plain HTML/CSS, a bar for a level, a centred bar for a difference (solid when its 95% interval excludes 0, dashed
when it does not) and a word badge. Arms are named in text, never coloured. Page order: bits per weight with a short
primer, what each configuration trades, distance from the BF16 model, four passes, how the replies ended, a fifth configuration added by amendment 2
(all added 2026-11-12), then the frozen two-pass result as published on 2026-11-11 with dated pointers.
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
           "exlr8-k4": "EXLR8 K4 checkpoint, added later", "k325-fp8": "K3.25 experts, FP8 core, added later"}
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


SC = V4.SC


def f4(x): return f"{x:.4f}"
def s4(x): return "0.0000" if round(x, 4) == 0 else f"{x:+.4f}".replace("-", MINUS)
def iv4(v): return f"{s4(v[0])} [{s4(v[1])}, {s4(v[2])}]"
def lvl(v, f=f3): return f'{f(v[0])} <span class="ci">[{f(v[1])}, {f(v[2])}]</span>'
def dcell4(v, span): return diverge(v[0], span, excl(v), label=s4(v[0])) + f' <span class="ci">[{s4(v[1])}, {s4(v[2])}]</span>'
def stale(what): raise SystemExit(f"v5 page: {what} no longer match the reading written for them")


K325 = "k325-fp8"                      # fifth configuration (amendment 2); its measured figures are in SUMMARY.json amendment_2
ARMS5 = ARMS4 + (K325,)


def pair5(p): return " ".join(f"<code>{x}</code>" if x in ARMS5 else MINUS for x in p.split())


def amend2_sections(S, h2, gh):
    """Added later on 2026-11-12: the fifth configuration, k325-fp8 (amendment 2; RESULTS.md section 16). Its four single-message
    passes read by the frozen rule beside the four earlier configurations, how its replies ended, and its distance from the BF16
    model on this engine release. Returns the section, the sentences other sections quote and the data line. The figures of the
    four earlier configurations are those of the sections above; the function checks that they are."""
    A, FP, EN, BD, BW = S["amendment_2"], S["four_pass"], S["endings"], S["bf16_distance"], S["bits_per_weight"]
    code = lambda a: f"<code>{a}</code>"
    f1, f2 = (lambda x: f"{x:.1f}"), (lambda x: f"{x:.2f}")
    def seq(xs): return ", ".join(str(x) for x in xs[:-1]) + f" and {xs[-1]}"
    BLn, PD, AM, B, FC = A["by_length"], A["paired"], A["amendment"], A["bf16_distance"], A["five_columns"]["columns"]
    H, U, J, SCR, G, PU, FT, UR = (A[k_] for k_ in ("how_each_request_ended", "unfinished", "join_127k", "score_127k", "gap_127k_by_family",
                                                     "paired_unfinished_share", "finished_reply_tokens", "unfinished_replies"))
    PAIRS5 = tuple(f"{K325} - {a}" for a in ARMS4)
    three = ("anchor", "hqa", REF)                      # the configurations k325-fp8 is lower than at 127K
    FAMS = ("join", "ledger", "trace")
    LK = tuple(k_ for k_, _ in LENS)
    n = A["requests"]
    if (A["arm"] != K325 or tuple(BLn) != ARMS5 or tuple(PD) != PAIRS5 or n != FP["requests_per_arm"] or A["errors"]
            or set(A["checks"].values()) - {0} != {n} or A["checks"]["cached_tokens_nonzero"]
            or A["checkpoint"] != BW[K325]["checkpoint"] or BW[K325]["status"] != "measured (amendment_2)"
            or any(BLn[a][k_]["score"] != FP["by_length"][a]["p1234"][k_]["score"] for a in ARMS4 for k_ in ("all",) + LK)
            or any(H[a][k_] != EN["how_each_request_ended"][a]["p1234"][k_] for a in ARMS4 for k_ in ("all", "128k"))
            or any(J[a] != EN["join_127k"][a]["p1234"] or SCR[a] != EN["score_127k"][a]["p1234"] for a in ARMS4)):
        stale("the amendment-2 block and the sections it sits beside")

    # ---------------------------------------------------------------- what was added
    repo, rev = A["checkpoint"].split(" @ ")
    AM2 = gh(f"{RD}/{AM['file']}", "Amendment 2")
    if not AM["written"].startswith("2026-11-12 11:57") or not A["ran"].startswith("2026-11-12 11:58 to 16:54") or len(A["passes"]) != 4:
        stale("when amendment 2 was written and run")
    intro = (f"<p>{AM2} adds a fifth configuration, {code(K325)}: the checkpoint <code>{E(repo)}</code> (revision "
             f"<code>{E(rev[:8])}</code>), with routed experts at K3.25 and, as the engine runs it by default, FP8 attention, dense and shared-expert blocks (as stored, its files hold part of the attention, the output head and the embedding at BF16, and <a href='#bits'>bits per weight</a> counts the files). It is the "
             "checkpoint of the engine's own starting config for two RTX cards. The amendment was written on 2026-11-12 at 11:57, after "
             "the four-pass results and the ending breakdown above had been read and before the first request of the passes it adds "
             f"(sha256 <code>{AM['sha256_as_written']}</code>). It fixed four single-message passes in advance and predicted no "
             "direction for task score: a level result and a lower one were both called plausible. The passes ran from 11:58 to 16:54 the "
             f"same day, one launch per pass: {n} requests, {A['errors']} errors, and in all {n} the same item, seed and prompt-token count "
             "as <code>anchor</code>'s request. No eight-turn pass was run. Added later on 2026-11-12.</p>"
             f"<p><b>Two things qualify every comparison in this section.</b> {code(K325)} differs from each other configuration in the "
             "whole checkpoint: K3.25 routed experts where theirs are 4-bit, and its own tensors outside them. No difference below can be "
             "assigned to one component. And its four passes ran after the other configurations', not interleaved with them, so an "
             "effect of the session cannot be excluded by design. The items, generator and driver hashes are the same in all twenty "
             "passes of the five configurations, and the launch config pins the engine image by the same digest.</p>")

    # ---------------------------------------------------------------- side by side
    reach = f"{BD['sets']['fidelity_set']['last_generated_position'] / 1000:.1f}K"
    kl = {a: BD["arms"][a]["fidelity_set"]["kl"] for a in ARMS4}; kl[K325] = B["arms"][K325]["fidelity_set"]["kl"]
    kt = {a: BD["arms"][a]["teacher_panel"]["kl"] for a in ARMS4}; kt[K325] = B["arms"][K325]["teacher_panel"]["kl"]
    bpw = {a: FC[a]["bits_per_weight"] for a in ARMS5}
    if (tuple(FC) != ARMS5 or any(abs(bpw[a] - BW["arms"][a]["bits_per_weight"]) > 1e-4 for a in ARMS5)
            or any(FC[a]["kl_from_bf16_fidelity_set"] != kl[a][0] or FC[a]["kl_from_bf16_teacher_panel"] != kt[a][0] for a in ARMS5)
            or any(FC[a]["score_four_passes_127k"] != BLn[a]["128k"]["score"][0] or FC[a]["score_four_passes_all_lengths"] != BLn[a]["all"]["score"][0]
                   or FC[a]["unfinished_of_960"] != BLn[a]["all"]["unfinished"] or FC[a]["every_field_right_of_960"] != BLn[a]["all"]["right"]
                   or FC[a]["unfinished_join_127k_of_80"] != J[a]["unfinished"] for a in ARMS5)):
        stale("the five-column table")
    def col(key, f): return [f(FC[a][key]) for a in ARMS5]
    rows = [("grp", "Size"),
            ["Bits per weight, whole language model"] + [bar(bpw[a], 16, f2(bpw[a])) for a in ARMS5],
            ["Bits per weight, routed experts"] + col("bits_per_weight_routed_experts", f2),
            ["Resident weights, both GPUs, MiB"] + col("resident_weights_mib_both_gpus", n0),
            ("grp", f"Distance from the BF16 model: KL in nats, lower is closer; contexts to {reach} only"),
            [f"Fidelity set, to {reach}"] + col("kl_from_bf16_fidelity_set", f4),
            ["Teacher panel, 2K"] + col("kl_from_bf16_teacher_panel", f4),
            ("grp", f"Graded tasks, four passes: {n} requests per configuration"),
            ["Field score at 4K"] + col("score_four_passes_4k", f3),
            ["Field score at 16K"] + col("score_four_passes_16k", f3),
            ["Field score at 127K"] + col("score_four_passes_127k", f3),
            ["Field score, all lengths"] + col("score_four_passes_all_lengths", f3),
            [f"Every field right, of {n}"] + col("every_field_right_of_960", str),
            [f"Unfinished replies, of {n}"] + col("unfinished_of_960", str),
            [f"Unfinished <code>join</code> replies at 127K, of {J[K325]['requests']}"] + col("unfinished_join_127k_of_80", str),
            ("grp", "Speed as run: median per stream under a mixed load of eight requests; descriptive, not a comparison of configurations"),
            ["Decode tokens/s at 127K"] + col("decode_tok_s_127k_median", f1),
            ["First token at 127K, s"] + col("first_token_s_127k_median", f1)]
    t_five = rich("Five configurations, side by side", "One column per configuration. The first four columns repeat the sections above; "
                  "intervals are in the tables below. Bars: full width = 16 bits per weight, the BF16 model",
                  [""] + [code(a) for a in ARMS5], rows,
                  foot=f"{code(K325)} and {code(REF)} are other checkpoints, not settings of the HQA checkpoint. The two distance rows use "
                       "different measures and are not comparable with each other. Every configuration was admitted the same KV pool "
                       f"({n0(A['launch']['kv_pool_tokens_serving'])} tokens), so smaller resident weights stayed as memory not in use in "
                       "these launches; pool and batch size were not varied.")

    # ---------------------------------------------------------------- graded tasks
    def sc(a, k_): return BLn[a][k_]["score"]
    def cell(a, k_):
        c_ = BLn[a][k_]
        return bar(c_["score"][0], 1.0, f3(c_["score"][0]), sub=f'all 8 right {c_["right"]} of {c_["n"]}')
    rows = [[arm(a)] + [cell(a, k_) for k_ in LK] +
            [lvl(sc(a, "all")), f'{BLn[a]["all"]["right"]} of {BLn[a]["all"]["n"]}',
             f'{BLn[a]["all"]["unfinished"]} <span class="ci">({BLn[a]["128k"]["unfinished"]} at 127K)</span>',
             f3(BLn[a]["128k"]["score_finished_only"])] for a in ARMS5]
    kp = A["score_by_pass"]
    op = [x for a in three for x in FP["by_length"][a]["score_by_pass"]["128k"]]
    cp = FP["by_length"]["compact"]["score_by_pass"]["128k"]
    SP = FP["single_pass_spread"]
    t_score = rich("Share of answer fields right, four passes, five configurations", f"Single message, four passes pooled: {n} requests per "
                   "configuration, 240 per length. Unfinished replies score 0. Second figure: replies with every field right. Interval: "
                   "95% over items",
                   ["Configuration"] + [x for _, x in LENS] + ["All lengths", "Every field right", "Unfinished replies", "Finished replies only, 127K"],
                   rows, hi=(len(rows) - 1,),
                   foot=f"{code(K325)} per pass (passes 1, 2, 3, 4): all lengths {', '.join(f3(x) for x in kp['all'])}; at 127K "
                        f"{', '.join(f3(x) for x in kp['128k'])}. At 127K the single passes of <code>anchor</code>, <code>hqa</code> and "
                        f"{code(REF)} range from {f3(min(op))} to {f3(max(op))} and <code>compact</code>'s from {f3(min(cp))} to {f3(max(cp))}. "
                        f"A single pass of one of the four earlier configurations moves by up to {SP['at_127k']:.2f} at 127K.")
    rows = [[pair5(p)] + [dcell(PD[p]["score"][k_], 0.08) for k_ in LK + ("all",)] for p in PAIRS5]
    def pooled(k_): return "; ".join(f"against {code(p.split(' - ')[1])} {iv3(PD[p]['score'][k_])}" for p in PAIRS5)
    t_pairs = rich(f"Paired difference in field score: {K325} against each of the four", f"Left of the line: {code(K325)} scored lower. Paired "
                   "by item, repeats averaged within the item; 95% interval over the 60 items (10,000 resamples of the items, seed 5); "
                   "solid bar: the interval excludes 0; bar edge = 0.08",
                   ["Difference"] + [x for _, x in LENS] + ["All lengths"], rows,
                   foot=f"Pooled over 4K and 16K: {pooled('4k+16k')}. Pooled over 64K and 127K: {pooled('64k+128k')}.")
    IV = A["intervals"]
    EX = IV["excluding_zero"]
    up = [x for x in EX if x["value"][0] > 0]
    if (IV["listed"] != 76 or len(EX) != IV["lower"] + IV["higher"] or len(up) != IV["higher"] or IV["selected"] != "none"
            or {(x["measure"], x["scope"]) for x in up} != {("every_field_right", "16k")}
            or sorted(x["pair"].split(" - ")[1] for x in up) != ["anchor", "compact"]):
        stale("the interval counts of the fifth configuration")
    counts = (f"<p><b>How many intervals exclude 0.</b> The task comparison of {code(K325)} lists {IV['listed']} intervals: four pairs × 19 "
              "(field score at four lengths, all lengths and two length groups; every field right at four lengths, all lengths and 64K + "
              "127K; field score in each of three task families over all lengths and at 127K), with no correction for their number and "
              f"none selected by a rule. {len(EX)} exclude 0: {IV['lower']} with {code(K325)} lower and {IV['higher']} with it higher "
              "(every field right at 16K, against <code>anchor</code> "
              f"{iv3(next(x['value'] for x in up if x['pair'].endswith('anchor')))} and against <code>compact</code> "
              f"{iv3(next(x['value'] for x in up if x['pair'].endswith('compact')))}). The full list is in "
              f"{gh(f'{RD}/SUMMARY.json', '<code>SUMMARY.json</code>')} under <code>amendment_2.intervals</code>. The endings and "
              f"distance tables below add {PU['intervals']} and {B['intervals']['listed']} more.</p>")

    # ---------------------------------------------------------------- how its replies ended
    CL = ("every field right", "1 wrong", "2 wrong", "3 or more wrong", "reply cap", "loop abort")
    def ended(k_): return [[arm(a)] + [str(H[a][k_][x]) for x in CL] for a in ARMS5]
    n_127 = sum(H[K325]["128k"].values())
    BFL = {a: EN["unfinished"]["by_arm_family_length"][a] for a in ARMS4}; BFL[K325] = U["by_family_length"][K325]
    unf = {a: BLn[a]["all"]["unfinished"] for a in ARMS5}
    cells = [(f, k_) for f in FAMS for k_ in LK if any(BFL[a][f][k_] for a in ARMS5)]
    LN = dict(LENS)
    if (cells != [("join", "64k"), ("join", "128k"), ("ledger", "64k"), ("ledger", "128k"), ("trace", "16k")] or U["with_answer_text"]
            or U["total"] != unf[K325] or len(UR) != U["total"] or sum(unf.values()) != U["all_five_arms_total"]
            or any(sum(BFL[a][f][k_] for f in FAMS for k_ in LK) != unf[a] for a in ARMS5) or BFL[K325]["join"]["128k"] != J[K325]["unfinished"]):
        stale("the unfinished replies of the fifth configuration by cell")
    t_end = rich("What each reply came to, five configurations", f"Single message, four passes: {n} replies per configuration, {n_127} of them at 127K",
                 ["Configuration", "Every field right", "1 field wrong", "2 wrong", "3 or more wrong", "Hit the reply cap", "Loop abort"],
                 [("grp", f"All four lengths, of {n}")] + ended("all") + [("grp", f"At 127K, of {n_127}")] + ended("128k"),
                 foot='Classes as in <a href="#endings">How the replies ended</a>, whose definitions were written on the first four '
                      "configurations before these passes ran and are applied here unchanged.")
    rows = [[arm(a)] + [str(BFL[a][f][k_]) for f, k_ in cells] + [str(unf[a])] for a in ARMS5]
    t_cells = rich("Where the unfinished replies are, five configurations", "Four passes, 80 requests per configuration in each family and "
                   "length. The other seven cells have none",
                   ["Configuration"] + [f"<code>{f}</code> {LN[k_]}" for f, k_ in cells] + ["All"], rows, hi=(len(rows) - 1,))
    BK_, jk = U["by_kind"], J[K325]
    jr = [r for r in UR if r["item"].startswith("join") and r["length"] == "128k"]
    jcopy = sum(r["kind"].startswith("copying") for r in jr)
    late = [r for r in jr if not r["kind"].startswith("copying")]
    if (BK_["copying, cap"] + BK_["other, cap"] + BK_["other, loop abort"] != U["total"] or BK_["copying, loop abort"] or len(jr) != jk["unfinished"]
            or jk["copy_run_unfinished"] != jk["unfinished"] or jk["unfinished_without_copy_run"] or len(late) != 1 or late[0]["run_start_chars"] is None
            or jk["copy_run_unfinished_all_8_docks_before"] + jk["copy_run_unfinished_7_docks_before"] != jk["unfinished"]
            or U["by_family_kind"]["trace"] != {k_: 0 for k_ in BK_}):
        stale("the make-up of the fifth configuration's unfinished replies")
    end_kind = (f"<p><b>All {U['total']} unfinished replies of {code(K325)} ended inside the reasoning; none had written any answer "
                f"text.</b> {BK_['copying, cap']} are copying replies that ran to the reply cap, {BK_['other, cap']} reached the cap on other "
                f"reasoning and {BK_['other, loop abort']} was stopped by the loop abort. They are spread over the passes "
                f"({' / '.join(str(x) for x in U['by_pass'])}) and over {U['distinct_items']} items, "
                f"{len(U['items_also_unfinished_in_an_earlier_arm'])} of which also have an unfinished reply in one of the four earlier "
                f"configurations. In <code>join</code> at 127K all {jk['unfinished']} have a copy run: {jcopy} are copying by the "
                "half-of-the-reasoning threshold and one started its run late "
                f"(after {late[0]['run_start_chars'] / 1000:.0f} thousand characters). In {jk['copy_run_unfinished_all_8_docks_before']} of "
                f"the {jk['unfinished']} all eight correct docks had been written in the reasoning before the run started; in the other "
                f"{['', 'one', 'two', 'three'][jk['copy_run_unfinished_7_docks_before']]}, seven had.</p>")
    BP = A["join_127k_unfinished_by_pass"]
    jn = jk["requests"]
    rows = [[arm(a), str(J[a]["unfinished"]), " / ".join(str(x) for x in BP[a]), str(J[a]["with_copy_run"]), str(J[a]["copy_run_finished"]),
             str(J[a]["copy_run_unfinished"]), str(J[a]["copy_run_unfinished_all_8_docks_before"]), str(J[a]["items_with_unfinished"])] for a in ARMS5]
    t_join = rich("<code>join</code> at 127K, every reply, five configurations", f"{jn} requests per configuration over four passes, whether the reply finished or not",
                  ["Configuration", "Unfinished", "By pass", "Copy run", "Finished", "Unfinished", "All 8 before", "Items"], rows, hi=(len(rows) - 1,), cls="nb",
                  foot=f"Columns as in the table of that name above. Across the five configurations, {A['join_127k_items_with_unfinished_any_arm']} "
                       "of the 20 <code>join</code> items have at least one unfinished reply at 127K.")
    def scell(v, fo): return f'{f3(v)}<small class="t">finished only {f3(fo)}</small>'
    rows = [[arm(a)] + [scell(SCR[a]["by_family"][f]["score"], SCR[a]["by_family"][f]["finished_only"]) for f in FAMS] +
            [scell(SCR[a]["score"], SCR[a]["finished_only"])] for a in ARMS5]
    t_fam = rich("Score at 127K by task family, and of the finished replies alone, five configurations", "Four passes, 80 requests per family "
                 "and configuration. Unfinished replies score 0 in the first figure and are left out of the second",
                 ["Configuration"] + [f"<code>{f}</code>" for f in FAMS] + ["All families"], rows, hi=(len(rows) - 1,))
    if list(G) != list(PAIRS5) or any(abs(G[p]["all"] - PD[p]["score"]["128k"][0]) > 0.0006 for p in PAIRS5): stale("the split of the fifth configuration's 127K gap")
    rows = [[pair5(p)] + [s3(G[p][k_]) for k_ in ("all",) + FAMS] for p in PAIRS5]
    t_gap = rich(f"The 127K difference in score of {K325}, split by task family", "Each family is a third of the requests at 127K, so a "
                 "difference in score there is the sum of three parts up to rounding. No intervals: this is arithmetic on the table above",
                 ["Difference in score at 127K", "All", "From <code>join</code>", "From <code>ledger</code>", "From <code>trace</code>"], rows)
    SCOPE = (("unfinished_all", "All lengths, all families"), ("unfinished_127k", "127K, all families"), ("unfinished_127k_join", "127K, <code>join</code>"),
             ("unfinished_127k_ledger", "127K, <code>ledger</code>"), ("unfinished_64k_ledger", "64K, <code>ledger</code>"))
    if (PU["intervals"] != len(PAIRS5) * len(SCOPE) or any(set(PU[p]) != {k_ for k_, _ in SCOPE} for p in PAIRS5)
            or sum(excl(PU[p][k_]) for p in PAIRS5 for k_, _ in SCOPE) != PU["excluding_zero"]):
        stale("the count of the fifth configuration's share intervals")
    rows = [[pair5(p)] + [dcell(PU[p][k_], 0.35) for k_, _ in SCOPE] for p in PAIRS5]
    t_share = rich(f"Paired difference in the share of unfinished replies: {K325} against each of the four", f"Right of the line: {code(K325)} "
                   "had more unfinished replies. Paired by item, repeats averaged within the item; 95% interval from 10,000 resamples of "
                   "the items (seed 5); 60 items in the all-families columns, 20 in the <code>join</code> and <code>ledger</code> "
                   "columns; solid bar: the interval excludes 0; bar edge = 0.35",
                   ["Difference"] + [x for _, x in SCOPE], rows,
                   foot=f"All {PU['intervals']} intervals of this kind are shown; {PU['excluding_zero']} exclude 0. No correction is applied.")
    ft = FT[K325]["128k"]
    ft4 = [EN["finished_reply_tokens"][a]["128k"] for a in ARMS4]
    end_len = (f"<p>Its finished replies at 127K are about as long as the others': median {ft['median'] / 1000:.1f} thousand tokens "
               f"against {min(x['median'] for x in ft4) / 1000:.1f} to {max(x['median'] for x in ft4) / 1000:.1f}, 99th percentile "
               f"{ft['p99'] / 1000:.0f} thousand against {min(x['p99'] for x in ft4) / 1000:.0f} to {max(x['p99'] for x in ft4) / 1000:.0f}, "
               f"and {ft['over_half_cap']} of {ft['n']} longer than half the cap.</p>")

    # ---------------------------------------------------------------- distance from BF16
    YS, KA, DF, BI = BD["yardsticks"], B["arms"][K325], B["differences"], B["intervals"]
    fp8, ER = YS["official_fp8_release"], B["earlier_release"]
    BK = list(KA["fidelity_set"]["by_bucket"])
    order = sorted(ARMS4, key=lambda a: kl[a][0])
    RP, PC = B["repeat"], B["port_against_cli"]
    if (list(DF) != list(PAIRS5) or BI["listed"] != 20 or BI["excluding_zero"] != 20 or BI["selected"] != "none"
            or any(not excl(v) or v[0] <= 0 for p in PAIRS5 for v in list(DF[p]["fidelity_set"].values()) + [DF[p]["teacher_panel"]])
            or BK != list(BD["arms"]["anchor"]["fidelity_set"]["by_bucket"]) or not KA["fidelity_set"]["fidelity_gate"]["pass"]
            or RP["kl_difference"] or len(set(RP["same_argmax_generated_positions"])) != 1
            or any(x["largest_kl_difference"] or len(set(x["records_agreeing"])) != 1 for x in (PC["r0"], PC["r1"]))
            or ER["teacher_panel_kl"] != kt[K325][0] or abs(ER["fidelity_set_kl"] - kl[K325][0]) > 0.0001
            or ER["fidelity_set_kl"] != YS["k3.25_on_cuteafd"]["fidelity_set_kl"]):
        stale("the distance of the fifth configuration from BF16")
    def lv(v): return bar(v[0], 0.05, f4(v[0])) + f' <span class="ci">[{f4(v[1])}, {f4(v[2])}]</span>'
    def pt(x): return bar(x, 0.05, f4(x))
    def bk(a): return (KA if a == K325 else BD["arms"][a])["fidelity_set"]["by_bucket"]
    rows = [["Official FP8 model<small>baseline recorded in the fidelity set's manifest; quoted, not recomputed here</small>", pt(fp8["fidelity_set_kl"]), "", "", "", ""]]
    rows += [[arm(a), lv(kl[a])] + [f4(bk(a)[b]["kl"][0]) for b in BK] + [lv(kt[a])] for a in order + [K325]]
    g = KA["fidelity_set"]["fidelity_gate"]
    t_kl = rich("KL from the BF16 model, five configurations", f"Nats; 0 is identical, lower is closer. Fidelity set: generated positions, "
                f"contexts to {reach}. Teacher panel: 2K contexts. 95% interval over windows. Bar edge = 0.05",
                ["Configuration", "Fidelity set, generated positions"] + BK + ["Teacher panel"], rows, hi=(len(rows) - 1,),
                foot=f"{code(K325)} was captured on 2026-11-12 from 16:54 to 17:09 on CuteAFD v5.0.0, with the sets, measures and scorer of "
                     '<a href="#bf16">Distance from the BF16 model</a>, whose rows the first five are. The same checkpoint measured '
                     f"{f4(ER['fidelity_set_kl'])} and {f4(ER['teacher_panel_kl'])} on CuteAFD v3.0.1 on 2026-10-26 (the K3.25 row of that "
                     "section): the teacher-panel figure is the same to the last digit recorded, the fidelity-set figure differs in the "
                     f"fourth decimal. It passes the engine CLI's own fidelity gate on the fidelity set, which compares point estimates with four "
                     f"thresholds: KL {f4(kl[K325][0])} against at most {g['kl_max']}, same most likely token {f4(KA['fidelity_set']['top1'])} against "
                     f"at least {g['top1_min']}, the same where BF16 is confident {f4(KA['fidelity_set']['confident_top1'])} against at least "
                     f"{g['confident_top1_min']}, and top-3 containment {f4(g['top3'])} against at least {g['top3_min']}. The upper end of the "
                     f"KL interval, {f4(kl[K325][2])}, is above that threshold.")
    NAME = {"anchor": "anchor: BF16 core (reference)", "hqa": "hqa: BF16 q_b_proj + o_proj, rest K6", "compact": "compact: K6 core",
            REF: f"{REF}: EXLR8 K4 checkpoint", K325: f"{K325}: K3.25 experts, FP8 core"}
    panel = [("Official FP8 model (recorded baseline)", fp8["fidelity_set_kl"], "r")] + [(NAME[a], kl[a][0], "c") for a in order + [K325]]
    svg = V4.SC.bars([("KL from the BF16 model · fidelity set, generated positions", panel)], label_w=270,
                     aria="KL from the BF16 model on the fidelity set: the official FP8 model, the four configurations and k325-fp8, the farthest")
    trows = [[E(lab), f4(v), "baseline recorded in the set's manifest; quoted, not recomputed here" if k_ == "r" else
              f"[{f4(kl[lab.split(':')[0]][1])}, {f4(kl[lab.split(':')[0]][2])}]"] for lab, v, k_ in panel]
    fig = V4.SC.figure("k325-scale", "Distance from the BF16 model, five configurations on this release",
                       f"KL from the BF16 model on the fidelity set (generated positions, contexts to {reach}), one bar per configuration, all "
                       f"measured on CuteAFD v5.0.0, with the baseline recorded for the official FP8 model in the set's manifest. The bars "
                       "carry no interval; the table above and the table view give them.",
                       [(svg, None, None)],
                       f"The last bar is {K325}. Its interval lies above those of <code>anchor</code>, <code>hqa</code> and "
                       f"<code>compact</code> and overlaps the upper end of {REF}'s; the paired differences below, computed on the same "
                       f"rows, are what separates it from each of the four. Nothing here reaches past {reach}.",
                       rich("", "", ["Row", "KL, nats", "95% interval or source"], trows),
                       legend_items=[("bc", "CuteAFD v5.0.0: the five configurations"),
                                     ("br", "official FP8 model: baseline recorded in the set's manifest, not recomputed here")])
    if not max(kl[a][2] for a in ARMS) < kl[K325][1] < kl[REF][2]: stale("the overlap of the fidelity-set intervals")
    rows = [[pair5(p), dcell4(DF[p]["fidelity_set"]["overall"], 0.03)] + [dcell4(DF[p]["fidelity_set"][b], 0.03) for b in BK] +
            [dcell4(DF[p]["teacher_panel"], 0.03)] for p in PAIRS5]
    t_diff = rich(f"Paired difference in KL from BF16: {K325} against each of the four", f"Right of the line: {code(K325)} is farther from BF16. "
                  "Paired on the same rows, 95% interval over windows; solid bar: the interval excludes 0; bar edge = 0.03",
                  ["Difference", "Fidelity set, generated positions"] + BK + ["Teacher panel"], rows,
                  foot=f"All {BI['listed']} intervals computed are shown ({BI['fidelity_set']} on the fidelity set, {BI['teacher_panel']} on "
                       f"the teacher panel) and all {BI['excluding_zero']} exclude 0; no correction for their number.")
    def two(d, key, f): return f"{f(d['fidelity_set'][key])} / {f(d['teacher_panel'][key])}"
    def rng(key, f): return " / ".join(span([BD["arms"][a][s_][key] for a in ARMS4], f) for s_ in ("fidelity_set", "teacher_panel"))
    r_ = PC["r0"]["records_agreeing"][0]
    bf_other = (f"<p><b>Other measures against BF16</b> (fidelity set / teacher panel; the four earlier configurations in brackets). Most likely "
                f"token the same as BF16's: {two(KA, 'top1', f4)} ({rng('top1', f4)}). NLL above BF16, nats: {two(KA, 'nll_above_bf16', s4)} "
                f"({rng('nll_above_bf16', s4)}). Same token where BF16 is confident: {two(KA, 'confident_top1', f4)} "
                f"({rng('confident_top1', f4)}).</p>"
                f"<p><b>Repeat.</b> A second launch reproduced the fidelity-set result exactly: KL difference 0.0 and the same most likely "
                f"token on {n0(RP['same_argmax_generated_positions'][0])} of {n0(RP['same_argmax_generated_positions'][1])} generated positions. "
                f"The float64 port used for the intervals and the engine CLI agree on {n0(r_)} of {n0(r_)} records in both launches.</p>")

    # ---------------------------------------------------------------- reading
    d16 = [PD[p]["score"]["4k+16k"] for p in PAIRS5]
    d64 = [PD[p]["score"]["64k"] for p in PAIRS5]
    d127 = {a: PD[f"{K325} - {a}"]["score"]["128k"] for a in ARMS4}
    if (any(excl(v) for v in d16 + d64) or min(v[0] for v in d16) <= 0 or max(v[0] for v in d64) >= 0
            or any(excl(PD[p]["score"][k_]) for p in PAIRS5 for k_ in ("4k", "16k"))
            or any(not excl(d127[a]) or d127[a][0] >= 0 for a in three) or excl(d127["compact"]) or d127["compact"][0] >= 0
            or sum(x > max(kp["128k"]) for x in op) < 10 or min(kp["128k"]) >= min(cp)):
        stale("the task reading of the fifth configuration")
    fo = {f: {a: SCR[a]["by_family"][f]["finished_only"] for a in ARMS5} for f in FAMS}
    lu = [SCR[a]["by_family"]["ledger"]["unfinished"] for a in ARMS4]
    f127 = {f: [PD[p]["by_family_127k"][f] for p in PAIRS5] for f in FAMS}
    if (any(not G[f"{K325} - {a}"]["join"] < G[f"{K325} - {a}"]["ledger"] < -0.01 or abs(G[f"{K325} - {a}"]["trace"]) > 0.01 for a in three)
            or any(excl(v) for v in f127["ledger"] + f127["trace"]) or max(v[0] for v in f127["ledger"]) >= 0
            or [excl(v) for v in f127["join"]] != [a in three for a in ARMS4]
            or fo["join"][K325] < 0.98 or fo["join"][K325] >= min(fo["join"][a] for a in ARMS4)
            or fo["ledger"][K325] >= min(fo["ledger"][a] for a in ARMS4) - 0.02 or SCR[K325]["by_family"]["ledger"]["unfinished"] <= max(lu)
            or not min(fo["trace"][a] for a in ARMS4) < fo["trace"][K325] < max(fo["trace"][a] for a in ARMS4)):
        stale("where the fifth configuration's 127K gap sits")
    ju = {a: J[a]["unfinished"] for a in ARMS5}
    pj = {a: PU[f"{K325} - {a}"]["unfinished_127k_join"] for a in ARMS4}
    OQ = "attention: o_proj and q_b_proj"
    oq = {a: BW["arms"][a]["by_component"][OQ]["bits_per_weight"] for a in ARMS5}
    if (min(ju[K325], ju["compact"]) < 2 * max(ju[a] for a in three) or any(not excl(pj[a]) for a in three) or excl(pj["compact"])
            or not oq[REF] < oq["compact"] < oq[K325] < oq["hqa"] or ju[REF] != min(ju.values())
            or kl["compact"][0] >= kl["anchor"][0] or kl[REF][0] <= max(kl[a][0] for a in ARMS)
            or any(x["kda_fp8"] != "Row128" for x in A["launch"]["serving"])):
        stale("the two groups of unfinished join replies")
    dd = [DF[p]["fidelity_set"]["overall"][0] for p in PAIRS5] + [DF[p]["teacher_panel"][0] for p in PAIRS5]
    t4 = BD["reading"]["times_the_fp8_figure"]
    RW = {a: FC[a]["resident_weights_mib_both_gpus"] for a in ARMS5}
    less = A["five_columns"]["resident_weights_mib_less_than_the_four"]
    b4 = [bpw[a] for a in ARMS4]
    big4 = BD["reading"]["largest_difference_between_the_four"]
    if (less != [min(RW[a] for a in ARMS4) - RW[K325], max(RW[a] for a in ARMS4) - RW[K325]] or bpw[K325] >= min(b4)
            or round(B["times_the_fp8_figure"], 1) <= t4[1] or min(dd) <= 2 * big4
            or abs(FC[K325]["decode_tok_s_127k_median"] - FC["anchor"]["decode_tok_s_127k_median"]) > 1.5
            or abs(FC[K325]["first_token_s_127k_median"] - FC["anchor"]["first_token_s_127k_median"]) > 1.5):
        stale("what the smaller size buys")
    d3 = [abs(d127[a][0]) for a in three]
    def gl(a): return G[f"{K325} - {a}"]
    reading = ("<ul>"
               f"<li><b>To 16K {code(K325)} scores level with the other four.</b> Pooled over 4K and 16K the four differences are "
               f"{s3(min(v[0] for v in d16))} to {s3(max(v[0] for v in d16))} and every interval includes 0; no field-score interval at 4K or "
               f"16K excludes 0. At 64K it is lower in count against all four ({s3(min(v[0] for v in d64))} to "
               f"{s3(max(v[0] for v in d64))}) and every interval includes 0. Basis: 480 requests per configuration at the two short "
               "lengths, 240 at 64K.</li>"
               f"<li><b>At 127K it is lower than <code>anchor</code>, <code>hqa</code> and {code(REF)} by {f3(min(d3))} to {f3(max(d3))}, "
               f"and not separated from <code>compact</code>.</b> Paired differences: {'; '.join(f'against {code(a)} {iv3(d127[a])}' for a in ARMS4)}. "
               f"Strength: the largest four-pass score difference between two configurations at one length on this page, with the same sign "
               f"against all three; its four passes at 127K are "
               f"{f3(min(kp['128k']))} to {f3(max(kp['128k']))}, and {sum(x > max(kp['128k']) for x in op)} of the {len(op)} single "
               f"passes of those three are above its highest (their lowest is {f3(min(op))}). Against that: three "
               f"intervals among {IV['listed']} with no correction, 60 items, a direction that was not predicted, passes that were not "
               "interleaved with the others', and a difference that is the whole checkpoint's.</li>"
               "<li><b>Most of that gap is replies that did not finish; part of it is answers.</b> Of the "
               f"{f3(abs(gl('anchor')['all']))} below <code>anchor</code> at 127K, {f3(abs(gl('anchor')['join']))} is <code>join</code> and "
               f"{f3(abs(gl('anchor')['ledger']))} <code>ledger</code>; <code>trace</code> is level. The <code>join</code> part is the "
               f'ending described in <a href="#endings">How the replies ended</a>: {ju[K325]} of {jn} replies ran to the reply cap with a '
               f"copy run, and its finished <code>join</code> replies score {f3(fo['join'][K325])} against "
               f"{span([fo['join'][a] for a in ARMS4], f3)}. The <code>ledger</code> part is both kinds: "
               f"{SCR[K325]['by_family']['ledger']['unfinished']} unfinished of {jn} against {span(lu, str)}, and finished replies at "
               f"{f3(fo['ledger'][K325])} against {span([fo['ledger'][a] for a in ARMS4], f3)}; no <code>ledger</code> interval at 127K "
               "excludes 0. This differs from <code>compact</code>, whose finished replies score level with the others in every family.</li>"
               f"<li><b>Unfinished <code>join</code> replies at 127K put the five in two groups: {ju[K325]} and {ju['compact']} of {jn} for "
               f"{code(K325)} and <code>compact</code>; {seq([ju[a] for a in three])} for <code>anchor</code>, <code>hqa</code> and "
               f"{code(REF)}.</b> {code(K325)} against each of the three: {', '.join(iv3(pj[a]) for a in three)}; against "
               f"<code>compact</code> {iv3(pj['compact'])}. The grouping was read after the counts were seen, and the intervals are not "
               "corrected for their number. Two orderings a reader might expect do not hold. The stored width of "
               f"<code>q_b_proj</code> and <code>o_proj</code> does not order them: {code(REF)} stores both in its 4-bit trellis and has the "
               f"fewest such replies, and {code(K325)} stores them at {f1(oq[K325])} bits on average and has the most (as run, its load line "
               "reports the projections of the attention layers the engine calls KDA held as FP8, converted at load, without "
               f"itemizing matrices, so the as-run width of these two is between 8 and {f1(oq[K325])} bits, and neither end of that range makes "
               "width order the counts). "
               f"Distance from BF16 does not either: <code>compact</code> is no farther than <code>anchor</code> on the fidelity set, and "
               f"{code(REF)} is the farthest of the four. What {code(K325)} and <code>compact</code> share that the other three do not is "
               "not identified by these runs. Within the one checkpoint where those two projections are the only difference "
               "(<code>hqa</code> and <code>compact</code>), the earlier reading stands as written: indicated, not established.</li>"
               f"<li><b>It is farther from the BF16 model than each of the four, on both sets.</b> By {f3(min(dd))} to {f3(max(dd))} nats "
               f"of KL, and all {BI['listed']} intervals exclude 0. That is {B['times_the_fp8_figure']:.1f} times the recorded figure "
               f"for the official FP8 model, where the four are {t4[0]:.1f} to {t4[1]:.1f}. Strength: the best-supported difference in this "
               "section (a deterministic capture, reproduced exactly by a second launch and matching the same checkpoint's figure on the "
               f"earlier release). It is a whole-checkpoint difference, measured to {reach}.</li>"
               f"<li><b>The two kinds of measurement separate it from the four at different lengths.</b> Distance from BF16 is measured "
               f"to {reach}, where its task score is level with theirs; the task difference is at 127K, where there is no BF16 reference. "
               "Neither result predicts the other from these data.</li>"
               f"<li><b>What the smaller size buys.</b> {f2(bpw[K325])} bits per weight against {f2(min(b4))} to {f2(max(b4))}, and "
               f"{n0(RW[K325])} MiB of resident weights over the two GPUs against {n0(min(RW[a] for a in ARMS4))} to "
               f"{n0(max(RW[a] for a in ARMS4))}: {n0(less[0])} to {n0(less[1])} MiB less. In these launches that memory was not put to "
               "use, because every configuration was admitted the same KV pool; what a larger pool or batch would return was not "
               f"measured. Speed as run at 127K is close to <code>anchor</code>'s ({f1(FC[K325]['decode_tok_s_127k_median'])} tokens/s and "
               f"{f1(FC[K325]['first_token_s_127k_median'])} s to first token against {f1(FC['anchor']['decode_tok_s_127k_median'])} and "
               f"{f1(FC['anchor']['first_token_s_127k_median'])}; descriptive).</li>"
               '<li><b>Beside <a href="#trades">What each configuration trades</a>.</b> BF16 core to <code>hqa</code> had no measured '
               "cost. <code>hqa</code> to <code>compact</code> showed in unfinished <code>join</code> replies at 127K and nowhere else. "
               f"The step to {code(K325)} is the first on this page where distance from BF16 moves by more than the {f4(big4)} that "
               "separates the four from each other, and where a long-context task difference of about "
               f"{f2(sum(d3) / len(d3))} appears against three configurations. That step changes the experts and everything outside them "
               "together, and the page has no configuration that changes one without the other.</li></ul>")
    limits = ("<p>Limits: " + "; ".join(E(x) for x in A["limits"]) + ". Distance from BF16: " + "; ".join(E(x) for x in B["limits"]) + ".</p>")
    body = (h2("k325", "A fifth configuration: K3.25 experts with an FP8 core") + intro + t_five + reading +
            "<p><b>Graded tasks.</b></p>" + t_score + t_pairs + counts +
            "<p><b>How its replies ended.</b></p>" + t_end + t_cells + end_kind + t_join + t_fam + t_gap + t_share + end_len +
            "<p><b>Distance from the BF16 model.</b></p>" + t_kl + fig + bf_other + t_diff + limits)

    sec = f'<a href="#k325">A fifth configuration</a>'
    quote = {
        "size_cells": {"kl": f4(kl[K325][0]), "all": f3(sc(K325, "all")[0]), "127k": f3(sc(K325, "128k")[0]), "unf127": str(BLn[K325]["128k"]["unfinished"])},
        "size_foot": (f"It was measured later on 2026-11-12 under {AM2.replace('Amendment 2', 'amendment 2')}, written before its first "
                      f"request: four task passes and its distance from BF16 on this release ({sec}). Its passes ran after the other "
                      "configurations' and were not interleaved with them."),
        "bits": (f"{code(K325)}, {f2(min(b4) - bpw[K325])} to {f2(max(b4) - bpw[K325])} bits below them, is farther from BF16 on both sets "
                 f"and scores lower at 127K ({sec}); that step changes the experts and the core together, so it does not show what "
                 "either costs alone."),
        "lede_size": (f"a fifth, the K3.25-Core-FP8 checkpoint ({code(K325)}), is at {f2(bpw[K325])}"),
        "lede": (f"<p><b>A fifth configuration</b>, added later on 2026-11-12 under a dated amendment: {code(K325)}, K3.25 experts with an "
                 f"FP8 core, at {f2(bpw[K325])} bits per weight. To 16K its task score is level with the other four. At 127K it is lower "
                 f"than <code>anchor</code>, <code>hqa</code> and {code(REF)} by {f3(min(d3))} to {f3(max(d3))} (intervals exclude 0) and "
                 f"not separated from <code>compact</code>; most of that gap is <code>join</code> replies that did not finish "
                 f"({ju[K325]} of {jn}). It is farther from BF16 than each of the four on both sets (KL {f4(kl[K325][0])} on the fidelity "
                 f"set). The difference is a whole checkpoint's and its passes were not interleaved with the others' ({sec}).</p>"),
        "k325_term": f" Since this was written the checkpoint has become a fifth configuration, {code(K325)}, measured on v5.0.0 ({sec}).",
        "am2": (f'<p><b>Amendment 2</b> ({gh(f"{RD}/{AM["file"]}", "text")}), written on 2026-11-12 before its first request, adds a fifth '
                f"configuration, {code(K325)}: the same four single-message passes and the same capture for distance from BF16. Both are "
                f"complete ({E(A['ran'].split(',')[0])} for the passes); their numbers are under {sec}, and the tables of this part of the "
                "page do not include them.</p>")}
    data = (f'<p class="sign">Added later on 2026-11-12. Fifth configuration: {gh(f"{RD}/analysis/samples-amend2.csv", "<code>samples-amend2.csv</code>")} '
            f'(one row per request, no text), {gh(f"{RD}/analysis/endings-amend2.csv", "<code>endings-amend2.csv</code>")} (counts over each '
            f'reply\'s reasoning, no text) and {gh(f"{RD}/analysis/amend2.py", "<code>amend2.py</code>")}, which recomputes that section '
            f'from the per-request CSVs into {gh(f"{RD}/analysis/AMEND2.json", "<code>AMEND2.json</code>")} (standard library only). Its '
            f'distance from BF16: {gh(f"{RD}/bf16ref/BF16REF-AMEND2.json", "<code>BF16REF-AMEND2.json</code>")}, with the per-window figures '
            "its intervals follow from. Saved replies, score files and dumps are not published.</p>")
    return body, quote, data


def sized_sections(S, h2, gh, k5):
    """Added later on 2026-11-12: bits per weight for the five checkpoints with a short primer (RESULTS.md section 15) and how
    the replies of the four passes ended (section 14). Returns the two sections, the sentences other sections quote and the data
    line. As elsewhere, a sentence that states a reading checks the numbers it rests on."""
    BW, EN, FP, BD = S["bits_per_weight"], S["endings"], S["four_pass"], S["bf16_distance"]
    code = lambda a: f"<code>{a}</code>"
    f1, f2, f4 = (lambda x: f"{x:.1f}"), (lambda x: f"{x:.2f}"), (lambda x: f"{x:.4f}")
    pc0, pc1, pc2 = (lambda x: f"{100 * x:.0f}%"), (lambda x: f"{100 * x:.1f}%"), (lambda x: f"{100 * x:.2f}%")
    def seq(xs): return ", ".join(str(x) for x in xs[:-1]) + f" and {xs[-1]}"
    others = [a for a in ARMS4 if a != "compact"]

    # ================================================================ bits per weight
    AR, SH, CM, RUNL = BW["arms"], BW["share_of_weights"], BW["components"], BW["as_run"]["launches"]
    OUT, RE, MTP, OQ, OA = "outside the routed experts, main layers", "routed experts", "multi-token-prediction block", "attention: o_proj and q_b_proj", "attention: other projections"
    if tuple(AR) != ARMS5 or BW["k325-fp8"]["status"] != "measured (amendment_2)" or BW["bf16_bits_per_weight"] != 16: stale("the configurations of the bits-per-weight table")
    bpw = {a: AR[a]["bits_per_weight"] for a in ARMS5}
    rel = {a: AR[a]["relative_to_bf16"] for a in ARMS5}
    gib = {a: AR[a]["stored_gib"] for a in ARMS5}
    outb = {a: AR[a]["outside_routed_experts_bits_per_weight"] for a in ARMS5}
    def c(a, comp): return AR[a]["by_component"][comp]["bits_per_weight"]
    def fm(a, comp): return AR[a]["by_component"][comp]["formats"]
    NAME = {"EXL3 trellis, 3 bits": "K3", "EXL3 trellis, 4 bits": "K4", "EXL3 trellis, 6 bits": "K6", "EXLR8 trellis, 4 bits": "EXLR8 4-bit trellis"}
    def mix(a, comp): return " and ".join(f"{pc0(v)} {NAME.get(k, k)}" for k, v in sorted(fm(a, comp).items(), key=lambda kv: -kv[1]) if v >= 0.01)
    W = BW["language_model_weights"]
    w3, w4 = AR[K325]["routed_expert_widths"]["3"], AR[K325]["routed_expert_widths"]["4"]
    fp8 = [c(a, comp) for a in ARMS5 for comp in CM if fm(a, comp).get("FP8", 0) >= 0.99]
    moved = sum(SH[comp] * (1 - fm("compact", comp).get("BF16", 0)) for comp in CM if comp not in (RE, MTP, "other"))
    d_mtp = (c("hqa", MTP) - c("compact", MTP)) * SH[MTP] * W / 8 / 2 ** 30      # GiB: hqa's BF16 projections in the multi-token-prediction block
    if not 0.05 < d_mtp < 0.2 or c("anchor", MTP) != c("compact", MTP): stale("the multi-token-prediction block of hqa")
    if (sorted(ARMS5, key=bpw.get, reverse=True) != list(ARMS5) or w3 != 3 * w4 or w3 + w4 != 288 * 42 * 3 or len(fp8) < 4
            or f2(c("anchor", RE)) != "4.01" or f2(c("hqa", "shared experts")) != "6.01" or f2(c(REF, RE)) != "4.00"
            or any(f2(c(a, RE)) != "4.01" for a in ARMS) or fm("hqa", OQ) != {"BF16": 1.0} or fm("compact", OQ) != {"EXL3 trellis, 6 bits": 1.0}
            or any(AR[a]["by_component"][comp] != AR["hqa"]["by_component"][comp] for a in ("compact",) for comp in CM if comp not in (OQ, MTP))
            or any(abs(c("anchor", comp) - 16) > 0.01 for comp in CM if comp not in (RE, MTP))
            or any(f2(c(a, "embedding")) != "16.00" for a in ARMS) or pc1(moved) != "2.4%" or pc1(SH[RE]) != "94.9%"
            or not c("hqa", OA) < outb["compact"] < outb["hqa"] < outb[K325] < 16.01 or outb[REF] >= outb["compact"]):
        stale("the bits-per-weight figures behind the primer")
    bits_intro = ("<p>The configurations on this page mix several storage formats inside one model, and their names (K4, K3.25, "
                  "Core-K6, FP8) each describe one part. This section puts them on one unit, <b>bits per weight</b>, counted from the "
                  "checkpoint files, with a short primer for readers who do not work with quantized models. Added later on "
                  "2026-11-12.</p>")
    primer = [
        ("Weights and bits", "a language model is a set of matrices of numbers, its weights. This model's language part has "
            f"{W / 1e9:.1f} billion of them. Bits per weight is the storage a part of the model takes divided by the number of weights "
            "in it: how many bits each weight gets on average. It sets the size of the files and, closely, of the model in memory, "
            "and a lower value is a coarser copy of the original."),
        ("BF16", "16 bits per weight, the format the model was released in. It is full precision here, and the 100% mark. At 16 bits "
            f"the language model would be {n0(BW['language_model_gib_at_bf16'])} GiB."),
        ("FP8", "an 8-bit floating-point number per weight plus a small table of scales: "
            f"{f1(min(fp8))} to {f1(max(fp8))} bits per weight as stored in these files."),
        ("EXL3 and the K numbers", "EXL3 is a trellis-coded format: a matrix is stored as a code of K bits per weight plus two short "
            f"scale vectors. K4 is 4 bits per weight ({f2(c('anchor', RE))} as stored) and K6 is 6 ({f2(c('hqa', 'shared experts'))})."),
        ("Mixed widths", "a fractional K is an average over matrices, not a width. In the K3.25 checkpoint three quarters of the "
            f"expert matrices are stored at 3 bits and one quarter at 4 ({n0(w3)} and {n0(w4)} matrices), which comes to "
            f"{f2(c(K325, RE))} bits per weight. Which matrix gets which width is the checkpoint author's allocation and is not "
            "examined here."),
        ("EXLR8", f"another trellis-coded format, by another author. Its K4 experts are {f2(c(REF, RE))} bits per weight. The same "
            f"nominal width in a different design is not the same code, so {code(REF)} is read as a whole checkpoint."),
        ("Where the weights are", f"{pc1(SH[RE])} of the weights are the routed experts: 288 small feed-forward blocks in each of 42 "
            "layers, of which a token passes through 8 per layer. Everything else in the main layers (attention, shared experts, the "
            f"dense feed-forward of the first three layers, the output head, the embedding) is {pc1(SH[OUT])}, and every token passes "
            f"through all of it. A further {pc1(SH[MTP])} is a multi-token-prediction block stored after the main layers. So the name "
            "on a checkpoint describes its experts and nearly fixes its size, while <code>anchor</code>, <code>hqa</code> and "
            f"<code>compact</code> differ inside the {pc1(SH[OUT])} (and, for <code>hqa</code>, in a {d_mtp:.1f} GiB part of the "
            "multi-token-prediction block)."),
        ("Names of the parts", "the <i>core</i> is everything in the main layers outside the routed experts. The <i>shared experts</i> "
            "are a feed-forward block beside the routed ones that every token passes through. <code>o_proj</code> and "
            "<code>q_b_proj</code> are two of the attention projection matrices of a layer, the two that <code>ATTENTION_MODE</code> "
            "selects the precision of. The <i>output head</i> turns the last hidden state into token scores. KDA is the engine's name "
            "for one of the model's two kinds of attention layer (MLA is the other); its load line (the line it logs when a checkpoint is "
            "loaded) reports whether the KDA projections are held as FP8. In the engine's source (v5.0.0, "
            "<code>rust/crates/cuteafd-loader/src/families/glm5_flash/core.rs</code>) <code>o_proj</code> is a projection of both kinds and "
            "<code>q_b_proj</code> of MLA layers only."),
        ("Stored and run", "the tables count what the files hold. The engine can hold a matrix in another form in memory; where it "
            'does, that is said under the component table. Memory in use is under <a href="#trades">What each configuration '
            "trades</a>.")]
    t_primer = '<dl class="gl">' + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in primer) + "</dl>"

    # ---- the layout figure: the parts of the model in the order data passes through them, and the format each configuration
    #      stores them in. Colour is the stored width (one hue, five steps); the number beside each strip is the measured figure.
    QB = {"EXL3 trellis, 3 bits": 3, "EXL3 trellis, 4 bits": 4, "EXLR8 trellis, 4 bits": 4, "EXL3 trellis, 6 bits": 6, "FP8": 8, "BF16": 16}
    HEAD, EMB, SHX, DMLP = "output head", "embedding", "shared experts", "dense MLP (layers 0-2)"
    LAY = [("Input", [(EMB, "token embedding")]),
           ("Attention", [(OQ, "o_proj and q_b_proj"), (OA, "other projections")]),
           ("Feed-forward", [(DMLP, "dense feed-forward, layers 0 to 2"), (SHX, "shared experts"), (RE, "routed experts")]),
           ("Output", [(HEAD, "output head")]),
           ("Stored after the main layers", [(MTP, "multi-token-prediction block")])]
    drawn = [comp for _, rs in LAY for comp, _ in rs]
    def segs(a, comp):
        m = {}
        for k_, v in fm(a, comp).items():
            if v < 0.03: continue                                   # a sliver under 3% of the part is folded into the rest
            if k_ not in QB: stale(f"a storage format the layout figure has no colour for ({k_})")
            m[QB[k_]] = m.get(QB[k_], 0) + v
        t = sum(m.values())
        if t < 0.97: stale(f"the format mix of {a}, {comp}")
        return [(q, v / t) for q, v in sorted(m.items())]
    def mixf(a, comp):                                               # every format of the part, to a tenth of a percent
        return ", ".join(f"{'100%' if v > 0.9995 else pc1(v)} {NAME.get(k_, k_)}" for k_, v in sorted(fm(a, comp).items(), key=lambda kv: -kv[1]) if v >= 0.0005)
    d_re = (c("compact", RE) - c(REF, RE)) * SH[RE] * W / 8 / 2 ** 30   # GiB: the routed experts of compact over exlr8-k4's
    fp8r = [c(a, comp) for a in ARMS5 for comp in drawn if fm(a, comp).get("FP8", 0) >= 0.99]
    worked = SH[RE] * c("compact", RE) + SH[OUT] * outb["compact"] + SH[MTP] * c("compact", MTP)
    if (sorted(drawn + ["other"]) != sorted(CM) or abs(SH[RE] + SH[OUT] + SH[MTP] - 1) > 5e-4 or pc2(SH["other"]) != "0.03%"
            or any(abs(c(a, "other") - 16) > 0.01 for a in ARMS5) or f2(worked) != f2(bpw["compact"])
            or f2(c("compact", RE)) != "4.01" or pc1(bpw["compact"] / 16) != pc1(rel["compact"])
            or any(q != 4 for a in ARMS5 if a != K325 for q, _ in segs(a, RE)) or [q for q, _ in segs(K325, RE)] != [3, 4]
            or any(q != 16 for comp in drawn if comp not in (RE, MTP) for q, _ in segs("anchor", comp))
            or not c(REF, OA) > c("compact", OA) or not c(REF, HEAD) > c("compact", HEAD)
            or any(not c(REF, comp) < c("compact", comp) for comp in (OQ, SHX, DMLP, EMB))
            or c("compact", EMB) != c("hqa", EMB) or outb[REF] != min(outb.values()) or f1(gib["compact"] - gib[REF]) != "1.0"
            or f1(d_re) != "0.3" or (f2(min(fp8r)), f2(max(fp8r))) != ("8.00", "8.26") or pc1(fm("compact", MTP).get("BF16", 0)) != "0.3%"
            or fm("compact", MTP) != fm("anchor", MTP) or f2(c("compact", MTP)) != "4.05" or not c("hqa", MTP) > c("compact", MTP)):
        stale("the layout figure of the bits-per-weight section")
    lgroups = [(hd, [(lb, pc2(SH[comp]), [(f2(c(a, comp)), segs(a, comp), f"{a} · {lb}: {f2(c(a, comp))} bits per weight, {mixf(a, comp)}")
                                           for a in ARMS5], comp == RE) for comp, lb in rs]) for hd, rs in LAY]
    ltotals = [("main layers outside routed experts", pc2(SH[OUT]), [f2(outb[a]) for a in ARMS5], False),
               ("whole language model", "100%", [f2(bpw[a]) for a in ARMS5], True),
               ("relative to BF16 (÷ 16)", "", [pc1(rel[a]) for a in ARMS5], False)]
    lsvg = V4.SC.layout(list(ARMS5), lgroups, ltotals,
                        [("routed experts", SH[RE], "w1"), ("rest of the main layers", SH[OUT], "w2"), ("multi-token-prediction block", SH[MTP], "w3")],
                        aria="For each of the five configurations, the storage format and bits per weight of each part of the model, "
                             "with the share of the weights each part holds", bracket=(1, 2, "one checkpoint, two settings"),
                        label_w=270, strip=44)
    ltab = ('<div class="tbl"><table><thead><tr><th>Part</th><th>Share of weights</th>' + "".join(f"<th>{code(a)}</th>" for a in ARMS5)
            + "</tr></thead><tbody>"
            + "".join(f"<tr><td>{E(hd)}: {E(lb)}</td><td>{pc2(SH[comp])}</td>"
                      + "".join(f"<td>{f2(c(a, comp))} · {E(mixf(a, comp))}</td>" for a in ARMS5) + "</tr>" for hd, rs in LAY for comp, lb in rs)
            + "".join(f"<tr><td>{E(lb)}</td><td>{sh}</td>" + "".join(f"<td>{E(t)}</td>" for t in ts) + "</tr>" for lb, sh, ts, _ in ltotals)
            + "</tbody></table></div>")
    fig_layout = V4.SC.figure(
        "layout", "How each configuration is built: storage format and bits per weight, part by part",
        "Rows are the parts of the model, from the input embedding to the output head, then the multi-token-prediction block the "
        "files store after them; columns are the five configurations. The strip in a cell is split by how much of that part the files "
        "store in each format (the colours in the key), and the number beside it is the part's bits per weight. The bar at the top "
        "is the whole model to scale: how its weights divide between the routed experts and everything else. <code>hqa</code> and "
        "<code>compact</code> are one checkpoint that stores <code>o_proj</code> and <code>q_b_proj</code> twice, once at BF16 and "
        "once at K6; each column counts the copy its setting loads.",
        [(lsvg, None, None)],
        f"Read down a column for how one configuration is built, across a row for where the configurations differ. The routed "
        f"experts row holds {pc1(SH[RE])} of the weights and so nearly fixes the whole-model figure: it is 4-bit in four columns, and "
        f"{code(K325)} is the one column where it is a mix of 3-bit and 4-bit. <code>anchor</code>, <code>hqa</code> and "
        f"<code>compact</code> have the same experts and differ in the other rows down to the output head, which together are "
        f"{pc1(SH[OUT])} of the weights. In <code>anchor</code> those rows are all BF16. In <code>hqa</code> and <code>compact</code> "
        "they are K6 except the embedding (BF16) and a tenth of the other attention projections (BF16), and the two differ in one "
        "row: <code>o_proj</code> and <code>q_b_proj</code>, BF16 in <code>hqa</code> and K6 in <code>compact</code> (the same two "
        f"projections inside the multi-token-prediction block are why that row reads {f2(c('hqa', MTP))} in <code>hqa</code>). "
        f"{code(REF)} spends its bits differently outside the experts: FP8 on the "
        "embedding, the head and most attention projections, its 4-bit trellis on <code>o_proj</code>, <code>q_b_proj</code>, the "
        f"shared experts and the dense feed-forward. That comes to {f2(outb[REF])} bits outside the routed experts, the lowest of the "
        f"five, although its head and other attention projections are stored at more bits than <code>compact</code>'s.",
        ltab,
        [("q3", "3-bit trellis (K3)"), ("q4", "4-bit trellis (K4; EXL3 or EXLR8)"), ("q6", "6-bit trellis (K6)"), ("q8", "FP8, 8 bits"),
         ("q16", "BF16, 16 bits")],
        calc="The bits per weight of a part is the bits its files store (the coded values plus the scale and sign vectors kept "
             "with them) divided by the number of weights the part stands for (rows × columns of each matrix). The vectors are why a "
             f"4-bit EXL3 trellis reads {f2(c('compact', RE))} and not 4.00, and why FP8 reads {f2(min(fp8r))} to {f2(max(fp8r))} depending on "
             "how many scale values are kept with it. A part with a little of a second format lands between the two widths: the "
             f"multi-token-prediction block of <code>compact</code> is K4 with {pc1(fm('compact', MTP)['BF16'])} BF16, which gives "
             f"{f2(c('compact', MTP))}. The whole-model figure pools every part, so each part counts by "
             f"its share of the weights. For <code>compact</code>: {pc2(SH[RE])} × {f2(c('compact', RE))} (routed experts) + "
             f"{pc2(SH[OUT])} × {f2(outb['compact'])} (rest of the main layers) + {pc2(SH[MTP])} × {f2(c('compact', MTP))} "
             f"(multi-token-prediction block) = {f2(bpw['compact'])}. Relative to BF16 is that figure over 16: {f2(bpw['compact'])} ÷ 16 "
             f"= {pc1(rel['compact'])}. Everything is read from the headers of the checkpoint files by "
             f"{gh(f'{RD}/analysis/bpw.py', '<code>bpw.py</code>')}; no weight is loaded. A sliver under 3% of a part is not drawn (the "
             f"table view lists every format to a tenth of a percent), and the remaining {pc2(SH['other'])} of the weights (normalization vectors and small tables, "
             "16 bits in every configuration) has no row but is in the totals. The figure is the files as stored, for <code>hqa</code> "
             "and <code>compact</code> the copy each setting loads; what the engine "
             'held in another form in memory is under "As run" below.')

    FSK = {a: BD["arms"][a]["fidelity_set"]["kl"][0] for a in ARMS4}
    reach = f"{BD['sets']['fidelity_set']['last_generated_position'] / 1000:.1f}K"
    BL = FP["by_length"]
    def meas(label, f, key): return [label] + [f(a) for a in ARMS4] + [k5["size_cells"][key]]
    rows = [("grp", "Size, counted from the checkpoint files"),
            ["Bits per weight, whole language model"] + [bar(bpw[a], 16, f2(bpw[a])) for a in ARMS5],
            ["Share of BF16 (bits per weight / 16)"] + [pc1(rel[a]) for a in ARMS5],
            ["Bits per weight outside the routed experts, as stored"] + [bar(outb[a], 16, f2(outb[a])) for a in ARMS5],
            ["Stored, GiB"] + [f1(gib[a]) for a in ARMS5],
            ("grp", "Measured, from the sections below"),
            meas(f"KL from BF16, fidelity set, to {reach} (lower is closer)", lambda a: f4(FSK[a]), "kl"),
            meas("Task score, four passes, all lengths", lambda a: f3(BL[a]["p1234"]["all"]["score"][0]), "all"),
            meas("Task score at 127K", lambda a: f3(BL[a]["p1234"]["128k"]["score"][0]), "127k"),
            meas("Replies at 127K that did not finish, of 240", lambda a: str(BL[a]["p1234"]["128k"]["unfinished"]), "unf127")]
    t_size = rich("Size beside what was measured", "One column per configuration. Bars: full width = 16 bits per weight, the BF16 model",
                  [""] + [code(a) for a in ARMS5], rows,
                  foot=f"{code(K325)} is a fifth configuration: the K3.25-Core-FP8 checkpoint ({E(BW['k325-fp8']['checkpoint'].split(' @ ')[0])}, "
                       f"revision {E(BW['k325-fp8']['checkpoint'].split(' @ ')[1][:8])}), the checkpoint of the engine's own starting "
                       "config for two RTX cards. " + k5["size_foot"] + " The K3.25 row of the first distance tables below is this "
                       "checkpoint measured on an earlier engine release (CuteAFD v3.0.1). Like "
                       f"{code(REF)} it is another checkpoint, so a difference from another column is a whole-checkpoint difference.")
    def lab(comp): return {OQ: "attention: <code>o_proj</code> and <code>q_b_proj</code>"}.get(comp, E(comp))
    rows = [[lab(comp), pc2(SH[comp])] + [bar(c(a, comp), 16, f2(c(a, comp))) for a in ARMS5] for comp in CM]
    rows += [[E(OUT), pc2(SH[OUT])] + [bar(outb[a], 16, f2(outb[a])) for a in ARMS5],
             ["<b>whole language model</b>", "100%"] + [bar(bpw[a], 16, f"<b>{f2(bpw[a])}</b>") for a in ARMS5]]
    t_comp = rich("Bits per weight by component, as stored", "Stored bits of each matrix's payload and of its scale and sign vectors, "
                  "over rows × columns of the matrix they stand for. Bars: full width = 16 bits",
                  ["Component", "Share of weights"] + [code(a) for a in ARMS5], rows, hi=(len(rows) - 1,), cls="nb",
                  foot=f"From {gh(f'{RD}/analysis/bpw.py', '<code>bpw.py</code>')}, which reads the header of every checkpoint file "
                       "(tensor names, types and sizes; no weight is loaded). Alignment padding, checksums and index records are left "
                       "out, and so is the vision tower (every configuration ran with vision off). <code>hqa</code> and "
                       "<code>compact</code> are two readings of one checkpoint, which stores <code>o_proj</code> and "
                       "<code>q_b_proj</code> twice: <code>hqa</code> counts the BF16 copy, <code>compact</code> the K6 copy.")
    k = RUNL[K325]
    if (mix("hqa", OA) != "90% K6 and 10% BF16" or mix(K325, OQ) != "53% BF16 and 47% FP8" or pc0(fm(K325, OA)["BF16"]) != "97%"
            or fm(K325, "shared experts") != {"FP8": 1.0} or fm(K325, "dense MLP (layers 0-2)") != {"FP8": 1.0}
            or (k["kda_fp8"], k["head"], k["kda_bf16_mib"]) != ("Row128", "FP8", 0.0) or RUNL["anchor"]["kda_fp8"] != "Off"
            or (RUNL["anchor"]["head"], RUNL["hqa"]["head"], RUNL["compact"]["head"], RUNL[REF]["head"]) != ("BF16", "K6", "K6", "row-FP8")):
        stale("what the component rows mix or the load lines")
    bits_mix = ("<p><b>What the rows mix.</b> <code>hqa</code> and <code>compact</code>, other attention projections at "
                f"{f2(c('hqa', OA))}: {mix('hqa', OA)}. {code(K325)}: shared experts and dense feed-forward FP8; <code>o_proj</code> and "
                f"<code>q_b_proj</code> {mix(K325, OQ)}; other attention projections {pc0(fm(K325, OA)['BF16'])} BF16; head and "
                f"embedding BF16. {code(REF)}: <code>o_proj</code>, <code>q_b_proj</code>, shared experts and dense feed-forward in its "
                f"4-bit trellis; other attention projections FP8 with block scales ({f2(c(REF, OA))}); head and embedding FP8 with one "
                f"scale per row ({f2(c(REF, 'output head'))}). The multi-token-prediction block is stored almost wholly at the experts' width in "
                f"every checkpoint, <code>anchor</code>'s included; its BF16 part is largest in <code>hqa</code> "
                f"({pc1(fm('hqa', MTP)['BF16'])} of the block), whose reading counts that block's <code>o_proj</code> and "
                "<code>q_b_proj</code> at BF16 too. Whether the engine uses that block when serving was not checked.</p>"
                "<p><b>As run</b>, from each launch's load line. <code>anchor</code>: no FP8 conversion, head BF16. <code>hqa</code> and "
                f"<code>compact</code>: head K6, as stored. {code(REF)}: head FP8 with row scales, as stored. <b>{code(K325)}: under the "
                "engine's defaults the load line reports the projections of the attention layers it calls KDA held as FP8, converted at load "
                f"(<code>kda_fp8={E(k['kda_fp8'])}</code>: {n0(k['kda_fp8_mib'])} MiB as FP8, {n0(k['kda_bf16_mib'])} MiB as BF16), and an "
                f"FP8 output head ({n0(k['head_mib'])} MiB, against {n0(RUNL['anchor']['head_mib'])} MiB for the BF16 head in "
                f"<code>anchor</code>).</b> So part of what this file stores at BF16 is run at FP8, and its {f2(outb[K325])} bits outside "
                "the routed experts is a property of the file, not of the launch. An as-run figure is not computed, because the logs do "
                "not itemize the conversion by matrix.</p>")
    b4 = [bpw[a] for a in ARMS4]
    d_hc, d_ac, d_kc = gib["hqa"] - gib["compact"], gib["anchor"] - gib["compact"], gib["compact"] - gib[K325]
    DHA = BD["differences"]["hqa - anchor"]
    if (c("compact", RE) - c(K325, RE)) * SH[RE] * W / 8 / 2 ** 30 <= d_kc or outb[K325] <= outb["hqa"]: stale("where k325-fp8 is smaller than compact")
    if (pc0(min(rel.values())), pc0(max(rel.values()))) != ("22%", "27%") or DHA["fidelity_set"]["overall"][0] > 0 or DHA["teacher_panel"][0] > 0:
        stale("the bits-per-weight reading")
    sref = FP["paired"][f"{REF} - anchor"]["p1234"]["score"]["all"]
    if excl(sref) or abs(sref[0]) > 0.005: stale(f"{REF} against anchor on score")
    bits_reading = ("<ul>"
                    f"<li><b>Every configuration here is a {pc0(min(rel.values()))} to {pc0(max(rel.values()))} copy of the BF16 model "
                    f"by bits.</b> The four with 4-bit experts span {f2(min(b4))} to {f2(max(b4))} bits per weight, "
                    f"{f2(round(max(b4), 2) - round(min(b4), 2))} bits end to end, because their experts are all at 4 bits and the "
                    f"experts are {pc0(SH[RE])} of the weights.</li>"
                    f"<li><b><code>hqa</code> to <code>compact</code> moves {pc2(SH[OQ])} of the weights from 16 bits to 6</b> in the main "
                    f"layers: {f2(bpw['hqa'])} to {f2(bpw['compact'])} bits per weight, {f1(d_hc)} GiB of files, {d_mtp:.1f} GiB of "
                    "it the same two projections in the multi-token-prediction block. <code>anchor</code> to "
                    f"<code>compact</code> moves {pc1(moved)} of the weights from 16 bits to about 6 or 7: {f2(bpw['anchor'])} to "
                    f"{f2(bpw['compact'])}, {f1(d_ac)} GiB. The embedding stays at BF16 in all three.</li>"
                    f"<li><b>{code(K325)} is the one that changes the experts</b>: {f2(c(K325, RE))} bits against "
                    f"{f2(c('compact', RE))} there. Its files are {f1(d_kc)} GiB smaller than <code>compact</code>'s in all: the experts "
                    "are smaller by more than that, and its core is stored at more bits than <code>hqa</code>'s or "
                    "<code>compact</code>'s (as stored; see \"As run\" above).</li>"
                    f"<li><b>{code(REF)} is the smallest of those four, though its head and most of its attention projections "
                    f"are FP8</b>, more bits than <code>compact</code>'s K6 there. It stores <code>o_proj</code>, <code>q_b_proj</code>, "
                    "the shared experts and the dense feed-forward in its 4-bit trellis where <code>compact</code> has K6, and its "
                    f"embedding at FP8 where <code>compact</code>'s is BF16: {f2(outb[REF])} bits outside the routed experts against "
                    f"{f2(outb['compact'])} (<a href=\"#layout\">the layout figure</a>). Its files are "
                    f"{f1(gib['compact'] - gib[REF])} GiB smaller in all, {f1(d_re)} GiB of that in the experts "
                    f"({f2(c(REF, RE))} bits against {f2(c('compact', RE))}).</li>"
                    "<li><b>Bits per weight is a size, not a quality score.</b> Among the four configurations with 4-bit experts neither distance "
                    f"from BF16 nor task score follows it: <code>hqa</code> at {f2(bpw['hqa'])} is no farther from BF16 than "
                    f'<code>anchor</code> at {f2(bpw["anchor"])} on either set (<a href="#bf16">distance from the BF16 model</a>), and '
                    f"{code(REF)} at {f2(bpw[REF])} scores level with <code>anchor</code>. " + k5["bits"] + " The unit says what was spent; the sections "
                    "below say what it bought.</li></ul>")
    bits_limits = ("<p>Limits: " + "; ".join(E(x) for x in BW["limits"]) + "; the HQA checkpoint is no longer on the hub and "
                   "<code>anchor</code>'s is derived locally, so a reader can rerun the script on " + f"{code(REF)} and {code(K325)} only.</p>")
    bits = (h2("bits", "Bits per weight: one unit for the checkpoints") + bits_intro + t_primer + fig_layout + t_size + t_comp + bits_mix +
            bits_reading + bits_limits)

    # ================================================================ how the replies ended
    H, U, J, SC, G, P, FT, UR = (EN[k_] for k_ in ("how_each_request_ended", "unfinished", "join_127k", "score_127k", "gap_127k_by_family",
                                                    "paired_unfinished_share", "finished_reply_tokens", "unfinished_replies"))
    CL = ("every field right", "1 wrong", "2 wrong", "3 or more wrong", "reply cap", "loop abort")
    FAMS = ("join", "ledger", "trace")
    def ended(k_): return [[arm(a)] + [str(H[a]["p1234"][k_][x]) for x in CL] for a in ARMS4]
    n_all, n_127 = (sum(H["anchor"]["p1234"][k_].values()) for k_ in ("all", "128k"))
    unf = {a: H[a]["p1234"]["all"]["reply cap"] + H[a]["p1234"]["all"]["loop abort"] for a in ARMS4}
    BAFL = U["by_arm_family_length"]
    cells = [(f, k_) for f in FAMS for k_, _ in LENS if any(BAFL[a][f][k_] for a in ARMS4)]
    if (cells != [("join", "128k"), ("ledger", "64k"), ("ledger", "128k"), ("trace", "16k")] or U["with_answer_text"] or U["total"] != sum(unf.values())
            or len(UR) != U["total"] or n_all != FP["requests_per_arm"] or any(unf[a] != BL[a]["p1234"]["all"]["unfinished"] for a in ARMS4)):
        stale("the unfinished replies by cell")
    end_intro = ('<p>The <a href="#four-pass">four-pass tables</a> count the replies that did not finish. This section says how each of '
                 f"the {n0(len(ARMS4) * n_all)} replies ended and, for the {U['total']} that did not finish, what their reasoning was made "
                 "of. It is descriptive and post hoc: the classification was written on 2026-11-12, after the four-pass results were "
                 f"read, and its intervals come on top of the {FP['intervals']['per_pass_set']} per pass set above. The counts are made "
                 "over the saved replies; no reply text is published. Added later on 2026-11-12.</p>")
    t_end = rich("What each reply came to, four passes", f"Single message, four passes: {n_all} replies per configuration, {n_127} of them at 127K",
                 ["Configuration", "Every field right", "1 field wrong", "2 wrong", "3 or more wrong", "Hit the reply cap", "Loop abort"],
                 [("grp", f"All four lengths, of {n_all}")] + ended("all") + [("grp", f"At 127K, of {n_127}")] + ended("128k"),
                 foot="Hit the reply cap: the reply reached the 32,768-token cap (finish class <code>cap</code>). Loop abort: the engine "
                      "stopped it for repetition (finish class <code>repetition</code>). Both score 0 under the frozen rule; "
                      "\"unfinished\" means one of the two.")
    LN = dict(LENS)
    rows = [[arm(a)] + [str(BAFL[a][f][k_]) for f, k_ in cells] + [str(unf[a])] for a in ARMS4]
    t_cells = rich("Where the unfinished replies are", "Four passes, 80 requests per configuration in each family and length. The other "
                   "eight cells have none",
                   ["Configuration"] + [f"<code>{f}</code> {LN[k_]}" for f, k_ in cells] + ["All"], rows)
    led = [BAFL[a]["ledger"]["64k"] + BAFL[a]["ledger"]["128k"] for a in ARMS4]
    j = {a: J[a]["p1234"] for a in ARMS4}
    jn = j["compact"]["requests"]
    if max(led) - min(led) > 2 or j["compact"]["unfinished"] < 2 * max(j[a]["unfinished"] for a in others) or any(j[a]["requests"] != jn for a in ARMS4):
        stale("the level ledger counts or compact's join count")
    end_where = (f"<p><b>All {U['total']} unfinished replies ended inside the reasoning; none had written any answer text.</b> "
                 f"<code>ledger</code> has {seq(led)} over its two lengths, level across the configurations. <code>compact</code>'s "
                 f"excess is <code>join</code> at 127K: {j['compact']['unfinished']} of {jn} against "
                 f"{seq([j[a]['unfinished'] for a in others])} ({', '.join(code(a) for a in others)}).</p>")
    KIND = U["by_arm_family_kind"]
    def kind(a, f, w): return sum(v for k_, v in KIND[a][f].items() if k_.startswith(w))
    jr = [r for r in UR if r["item"].startswith("join")]
    jc = [r for r in jr if r["kind"].startswith("copying")]
    jo = [r for r in jr if not r["kind"].startswith("copying")]
    recs = sorted(r["records"] for r in jr)
    if (len(jr) != sum(j[a]["unfinished"] for a in ARMS4) or len(jo) != 2 or {r["length"] for r in jr} != {"128k"}
            or [(r["arm"], f2(r["copy_share"]), r["run_start_chars"] is None) for r in sorted(jo, key=lambda r: r["arm"], reverse=True)]
               != [("hqa", "0.49", False), ("compact", "0.01", True)]
            or any(kind(a, "trace", "copying") for a in ARMS4) or min(kind(a, "join", "copying") for a in ARMS4) < 1
            or recs[0] < 8600 or recs[-1] > 8700):
        stale("the make-up of the unfinished join replies")
    o_c = next(r for r in jo if r["arm"] == "compact")
    end_terms = ("<p><b>What the unfinished reasoning was made of.</b> A <code>join</code> item is a list of records of three kinds in no "
                 "order (courier carries parcel, parcel routes via hub, hub ships from dock); the question names eight couriers and "
                 f"asks for each one's dock, three lookups per answer. At 127K the prompt holds about {n0(round(recs[len(recs) // 2], -1))} "
                 "records. A <i>step line</i> is a line of the reasoning that carries the record following, in the prompt, the record of "
                 "the previous such line: the reply is writing the prompt's records out in the prompt's order. A reply counts as "
                 "<i>copying</i> when step lines make up at least half of its reasoning by characters, and a <i>copy run</i> is 20 or "
                 f"more step lines in a row. The {U['total']} replies are listed with their shares in "
                 f"{gh(f'{RD}/analysis/ENDINGS.json', '<code>ENDINGS.json</code>')}, so another threshold can be applied.</p>")
    rows = [[arm(a), str(kind(a, "join", "copying")), str(kind(a, "join", "other")), str(kind(a, "ledger", "copying")),
             str(kind(a, "ledger", "other")), str(kind(a, "trace", "other"))] for a in ARMS4]
    t_kind = rich("Unfinished replies by what the reasoning was doing", f"The {U['total']} unfinished replies of four passes",
                  ["Configuration", "<code>join</code>: copying", "<code>join</code>: other", "<code>ledger</code>: copying",
                   "<code>ledger</code>: other", "<code>trace</code>: other"], rows,
                  foot=f"Of the {len(jr)} unfinished <code>join</code> replies, {len(jc)} are copying. One more (<code>hqa</code>) has a "
                       f"copy run and a share just under the threshold ({f2(next(r for r in jo if r['arm'] == 'hqa')['copy_share'])}); the "
                       f"last (<code>compact</code>) has no copy run and is {o_c['reasoning_chars'] / 1000:.0f} thousand characters of "
                       "other reasoning. In <code>ledger</code> the make-up differs by configuration on counts of "
                       f"{min(kind(a, 'ledger', '') for a in ARMS4)} to {max(kind(a, 'ledger', '') for a in ARMS4)}; no reading is taken "
                       "from that.")
    BP = EN["join_127k_unfinished_by_pass"]
    rows = [[arm(a), str(j[a]["unfinished"]), " / ".join(str(x) for x in BP[a]), str(j[a]["with_copy_run"]), str(j[a]["copy_run_finished"]),
             str(j[a]["copy_run_unfinished"]), str(j[a]["copy_run_unfinished_all_8_docks_before"]), str(j[a]["items_with_unfinished"])] for a in ARMS4]
    t_join = rich("<code>join</code> at 127K, every reply", f"{jn} requests per configuration over four passes, whether the reply finished or not",
                  ["Configuration", "Unfinished", "By pass", "Copy run", "Finished", "Unfinished", "All 8 before", "Items"], rows, cls="nb",
                  foot=f"Unfinished: of {jn}. By pass: the same count in passes 1 / 2 / 3 / 4. Copy run: replies with one, then how many "
                       "of those finished and how many did not. All 8 before: unfinished replies with a copy run in which all eight "
                       "correct docks were written before the run started. Items: of the 20 <code>join</code> items, those with at "
                       "least one unfinished reply.")
    starts = [r["run_start_chars"] for r in jc]
    before = {n: sum(r["answers_before"] == n for r in jc) for n in {r["answers_before"] for r in jc}}
    loop = [r for r in jc if r["finish"] == "repetition"]
    cr = {k_: [j[a][k_] for a in ARMS4] for k_ in ("with_copy_run", "copy_run_finished", "copy_run_finished_score")}
    iC, iO = ARMS4.index("compact"), [ARMS4.index(a) for a in others]
    if (set(before) != {7, 8} or len(loop) != 1 or loop[0]["arm"] != "anchor" or min(cr["copy_run_finished"]) < 1 or min(cr["copy_run_finished_score"]) < 0.95
            or cr["with_copy_run"][iC] <= max(cr["with_copy_run"][i] for i in iO) or cr["copy_run_finished"][iC] >= min(cr["copy_run_finished"][i] for i in iO)
            or any(r["finish"] != "cap" for r in jc if r is not loop[0])):
        stale("the shape of the copying replies")
    end_shape = (f"<p>The {len(jc)} copying replies have the same shape in every configuration, <code>anchor</code> included. The reasoning "
                 f"runs for {min(starts) / 1000:.1f} to {max(starts) / 1000:.1f} thousand characters, then starts writing the prompt's "
                 "records out in order and goes on until the reply cap (one <code>anchor</code> reply was stopped by the loop abort at "
                 f"{n0(loop[0]['tokens'])} tokens). In {before[8]} of the {len(jc)}, all eight correct docks had already been written in "
                 f"the reasoning before the copy run started; in the other {['', 'one', 'two', 'three'][before[7]]}, seven had. That is a "
                 "text match on the dock identifiers; it does not check that each dock was attached to the right courier. A copy run is "
                 f"not always the end of a reply: {seq(cr['copy_run_finished'])} replies with one went on to finish, and scored "
                 f"{seq([f3(x) for x in cr['copy_run_finished_score']])} ({', '.join(code(a) for a in ARMS4)}). <code>compact</code> has "
                 f"more replies with a copy run than the others ({cr['with_copy_run'][iC]} against "
                 f"{seq([cr['with_copy_run'][i] for i in iO])}) and fewer of them finished ({cr['copy_run_finished'][iC]} against "
                 f"{seq([cr['copy_run_finished'][i] for i in iO])}). Across the four configurations, "
                 f"{EN['join_127k_items_with_unfinished_any_arm']} of the 20 <code>join</code> items have at least one unfinished reply "
                 "at 127K.</p>")
    s = {a: SC[a]["p1234"] for a in ARMS4}
    def scell(v, fo): return f'{f3(v)}<small class="t">finished only {f3(fo)}</small>'
    rows = [[arm(a)] + [scell(s[a]["by_family"][f]["score"], s[a]["by_family"][f]["finished_only"]) for f in FAMS] +
            [scell(s[a]["score"], s[a]["finished_only"])] for a in ARMS4]
    t_fam = rich("Score at 127K by task family, and of the finished replies alone", "Four passes, 80 requests per family and configuration. "
                 "Unfinished replies score 0 in the first figure and are left out of the second",
                 ["Configuration"] + [f"<code>{f}</code>" for f in FAMS] + ["All families"], rows)
    fo = {f: {a: s[a]["by_family"][f]["finished_only"] for a in ARMS4} for f in FAMS}
    GP = ("anchor - compact", "hqa - compact", f"{REF} - compact")
    if (list(G) != list(GP) or any(max(fo[f][a] for a in others) - fo[f]["compact"] > 0.01 for f in FAMS)
            or any(G[p]["join"] < 0.8 * G[p]["all"] or abs(G[p]["ledger"]) > 0.01 or G[p]["trace"] > 0 for p in GP)
            or any(abs(s[a]["score"] - BL[a]["p1234"]["128k"]["score"][0]) > 0.0006 for a in ARMS4)):
        stale("the split of the 127K gap by family")
    rows = [[pair4(p)] + [s3(G[p][k_]) for k_ in ("all",) + FAMS] for p in GP]
    t_gap = rich("The 127K difference in score, split by task family", "Each family is a third of the requests at 127K, so a difference "
                 "in score there is the sum of three parts up to rounding (each family's own difference divided by 3). No intervals: this is "
                 "arithmetic on the table above",
                 ["Difference in score at 127K", "All", "From <code>join</code>", "From <code>ledger</code>", "From <code>trace</code>"], rows)
    PS = (("p12", "Passes 1-2"), ("p34", "Passes 3-4"), ("p1234", "All four passes"))
    SCOPE = (("unfinished_127k", "all families"), ("unfinished_127k_join", "<code>join</code>"), ("unfinished_127k_ledger", "<code>ledger</code>"))
    rows = []
    for key, name in SCOPE:
        rows.append(("grp", f"At 127K, {name.replace('<code>', '').replace('</code>', '')}"))
        rows += [[pair4(f"compact - {o}")] + [dcell(P[f"compact - {o}"][ps][key], 0.35) for ps, _ in PS] for o in ("anchor", "hqa", REF)]
    allp = [(pr, ps, key, v) for pr, d_ in P.items() for ps, c_ in d_.items() for key, v in c_.items()]
    shown = [x for x in allp if x[0].startswith("compact - ") and x[2] in dict(SCOPE)]
    n_ps, n_shown, n_ex, n_exs = len(allp), len(shown), sum(excl(x[3]) for x in allp), sum(excl(x[3]) for x in shown)
    t_pair = rich("Paired difference in the share of unfinished replies", "Right of the line: <code>compact</code> had more unfinished "
                  "replies. Paired by item, repeats averaged within the item; 95% interval from 10,000 resamples of the items (Python "
                  "<code>random.Random(5)</code>; the sorted draws at indices 250 and 9,749); 60 items in the all-families rows, 20 "
                  "in the <code>join</code> and <code>ledger</code> rows; solid bar: the interval excludes 0; bar edge = 0.35",
                  ["Difference"] + [n for _, n in PS], rows,
                  foot=f"Post hoc. This table shows {n_shown} of the {n_ps} intervals of this kind in SUMMARY.json (5 pairs, 3 pass sets, "
                       f"4 cells); {n_ex} of the {n_ps} exclude 0, {n_exs} of them here. They come on top of the intervals of the "
                       "four-pass tables, none was selected by a rule and no correction is applied. A single interval of this table is "
                       "not evidence on its own.")
    if (n_shown, n_ps) != (3 * (len(rows) - len(SCOPE)), 60): stale("the count of share intervals")
    ft = {a: FT[a]["128k"] for a in ARMS4}
    end_len = (f"<p>Finished replies at 127K are about as long in every configuration: median {min(ft[a]['median'] for a in ARMS4) / 1000:.1f} to "
               f"{max(ft[a]['median'] for a in ARMS4) / 1000:.1f} thousand tokens, 99th percentile "
               f"{min(ft[a]['p99'] for a in ARMS4) / 1000:.0f} to {max(ft[a]['p99'] for a in ARMS4) / 1000:.0f} thousand, and "
               f"{seq([ft[a]['over_half_cap'] for a in ARMS4])} of them longer than half the cap.</p>")
    pj = {o: P[f"compact - {o}"]["p1234"]["unfinished_127k_join"] for o in ("anchor", "hqa", REF)}
    items = {a: j[a]["items_with_unfinished"] for a in ARMS4}
    dec = {a: FP["descriptive_speed"]["by_pass_set"]["p1234"][a]["decode_tok_s_median"]["128k"] for a in ARMS4}
    mins = [32768 / v / 60 for v in dec.values()]
    def one_in(a): return f"one in {round(jn / j[a]['unfinished'])}"
    oth_rate = sorted(others, key=lambda a: -j[a]["unfinished"])
    if (not excl(pj["hqa"]) or excl(pj["anchor"]) or P["compact - anchor"]["p12"]["unfinished_127k_join"][0] > 0
            or sum(BP["compact"][:2]) > sum(BP["anchor"][:2]) or one_in("compact") != "one in 8" or min(mins) < 12 or max(mins) > 18
            or kind("compact", "join", "copying") <= max(kind(a, "join", "copying") for a in others)):
        stale("the reading of the endings")
    g_h, g_a = G["hqa - compact"], G["anchor - compact"]
    def fo_line(f): return f"<code>{f}</code> {f3(fo[f]['compact'])} against {span([fo[f][a] for a in others], f3)}"
    end_reading = ("<ul>"
                   "<li><b><code>compact</code>'s 127K gap is <code>join</code> replies that did not finish, not answers that were "
                   f"wrong.</b> Of the {f3(g_h['all'])} between <code>hqa</code> and <code>compact</code> at 127K, {f3(g_h['join'])} is "
                   f"<code>join</code>; of the {f3(g_a['all'])} between <code>anchor</code> and <code>compact</code>, {f3(g_a['join'])}. "
                   f"The finished replies score level in every family ({', '.join(fo_line(f) for f in FAMS)}). Basis: "
                   f"{n_all} requests per configuration, every unfinished reply classified. Strength: this is a count of what "
                   "happened, not an estimate; it holds for these four passes.</li>"
                   "<li><b>The ending is one every configuration shows, the BF16-core <code>anchor</code> included.</b> The reasoning "
                   "has written all or all but one of the answers, starts copying the records and does not come back. <code>anchor</code> has "
                   f"{kind('anchor', 'join', 'copying')} such replies of {jn}, <code>hqa</code> {kind('hqa', 'join', 'copying')} and one "
                   f"just under the copying threshold, {code(REF)} {kind(REF, 'join', 'copying')}, <code>compact</code> "
                   f"{kind('compact', 'join', 'copying')} and one of another kind. It is a way this model's reasoning fails to terminate on a long lookup task under these settings, "
                   "seen at every core precision measured here; <code>compact</code> shows it more often.</li>"
                   "<li><b>Whether the K6 <code>q_b_proj</code> and <code>o_proj</code> raise its rate is indicated, not "
                   "established.</b> For: <code>hqa</code> and <code>compact</code> are one checkpoint and differ in those two "
                   f"projections alone, and <code>compact</code> has {j['compact']['unfinished']} unfinished of {jn} against "
                   f"{j['hqa']['unfinished']} ({iv3(pj['hqa'])}), over {items['compact']} items against {items['hqa']}. Against: "
                   "<code>anchor</code>, whose projections are BF16 as <code>hqa</code>'s are, has "
                   f"{j['anchor']['unfinished']}, and the interval against it includes 0 ({iv3(pj['anchor'])}); by pass the counts are "
                   f"{seq(BP['compact'])} for <code>compact</code> against {seq(BP['anchor'])} for <code>anchor</code>, so the first "
                   f"two passes alone show no excess. The event is rare ({len(jr)} replies of {len(ARMS4) * jn}), the items are 20 and "
                   "the classification is post hoc.</li>"
                   '<li><b>What this changes in the sections above.</b> The size of the gap stands. Its nature is narrower than "a cost '
                   'of about one point" suggests: about one <code>join</code> reply in eight at 127K did not return an answer (the other '
                   f"configurations: {one_in(oth_rate[0])} to {one_in(oth_rate[-1])}), and "
                   "no loss of accuracy is measured on the replies that did. A reply that runs to the cap takes "
                   f"{min(mins):.0f} to {max(mins):.0f} minutes at the median decode rates above and returns nothing.</li>"
                   "<li><b>Not measured:</b> " + "; ".join(E(x) for x in EN["not_measured"]) + ". With the cap as it was, whether these "
                   "replies would have ended on their own is not known. <code>trace</code> and the shorter lengths show no excess for "
                   f"<code>compact</code> (one loop abort at 16K).</li></ul>")
    if BAFL["compact"]["trace"]["16k"] != 1 or sum(BAFL[a]["trace"][k_] for a in ARMS4 for k_, _ in LENS) != 1: stale("the trace cell")
    end_limits = "<p>Limits: " + "; ".join(E(x) for x in EN["limits"]) + ".</p>"
    ends = (h2("endings", "How the replies ended") + end_intro + t_end + t_cells + end_where + end_terms + t_kind + t_join + end_shape +
            t_fam + t_gap + t_pair + end_len + end_reading + end_limits)

    how = '<a href="#endings">How the replies ended</a>'
    jo3 = seq([j[a]["unfinished"] for a in others])
    quote = {
        "fp": (f" <b>Added later on 2026-11-12:</b> {how} counts every reply's ending and locates the gap over the four passes: "
               f"<code>join</code> replies at 127K that did not finish, {j['compact']['unfinished']} of {jn} "
               f"against {jo3}, with an ending every configuration shows. Of the {f3(g_h['all'])} between <code>hqa</code> and "
               f"<code>compact</code> at 127K, {f3(g_h['join'])} is <code>join</code>, and where <code>compact</code> answered it was as "
               "right as the others. What stays unsettled is whether the K6 projections raise the rate of such replies."),
        "trade": (f" <b>Added later on 2026-11-12:</b> {how} locates it. The gap is <code>join</code> replies at 127K that did not "
                  f"finish ({j['compact']['unfinished']} of {jn} against {jo3} in "
                  f"{', '.join(code(a) for a in others[:-1])} and {code(others[-1])}); where <code>compact</code> answered it was as "
                  "right as the others. Whether the K6 projections cause the higher rate is indicated, not established."),
        "lede_gap": (f"indicated, not established. Over the four passes the gap is replies to <code>join</code>, one of the three "
                     "task families, at 127K that did not finish "
                     f"({j['compact']['unfinished']} of {jn} against {jo3}), not answers that were wrong, and every configuration shows "
                     f"that ending ({how})"),
        "lede_bits": (f"<p><b>Size</b>: by bits the four configurations with 4-bit experts are {pc1(min(rel[a] for a in ARMS4))} to "
                      f"{pc1(max(rel[a] for a in ARMS4))} of the BF16 model ({f2(min(b4))} to {f2(max(b4))} bits per weight); "
                      + k5["lede_size"] + f" ({pc1(rel[K325])}). "
                      '<a href="#bits">Bits per weight</a> has the table and a short primer on the formats.</p>'),
        "open": (f"Later on 2026-11-12, on the question above: over the four passes it is replies that did not finish, in "
                 f"<code>join</code> ({how}). Still open: whether the K6 projections raise the rate of such replies (indicated, not "
                 "established), and whether those replies would end on their own under a larger reply cap."),
        "k325_term": k5["k325_term"]}
    data = (f'<p class="sign">Added later on 2026-11-12. How the replies ended: {gh(f"{RD}/analysis/endings.csv", "<code>endings.csv</code>")} '
            "(counts over each reply's reasoning, no text) and "
            f'{gh(f"{RD}/analysis/endings.py", "<code>endings.py</code>")}, which recomputes that section from the four CSVs into '
            f'{gh(f"{RD}/analysis/ENDINGS.json", "<code>ENDINGS.json</code>")}; {gh(f"{RD}/analysis/make_endings.py", "<code>make_endings.py</code>")} '
            "made the counts from the saved replies, which are not published. Bits per weight: "
            f'{gh(f"{RD}/analysis/bpw.py", "<code>bpw.py</code>")} and {gh(f"{RD}/analysis/BPW.json", "<code>BPW.json</code>")}.</p>')
    return bits, ends, quote, data


def extension_sections(S, h2, gh):
    """Added 2026-11-12, after the frozen two-pass result: what each configuration trades, the distance of each from the BF16
    model, and the four-pass reading (RESULTS.md sections 13, 12 and 11). Returns the page's lede, the three sections and the
    data line. Sentences that state a reading check the numbers they rest on, so the text cannot outlive a change in the data."""
    k5_body, k5, k5_data = amend2_sections(S, h2, gh) if "amendment_2" in S else ("", None, "")
    sz_bits, sz_ends, sz, sz_data = sized_sections(S, h2, gh, k5) if "endings" in S and "bits_per_weight" in S and k5 else ("", "", None, "")
    FP, BD, TO, AM = S["four_pass"], S["bf16_distance"], S["trade_offs"], S["amendment_1"]
    code = lambda a: f"<code>{a}</code>"
    LAB = {"all": "all lengths", "4k": "4K", "16k": "16K", "64k": "64K", "128k": "127K", "4k+16k": "4K and 16K pooled", "64k+128k": "64K and 127K pooled"}
    SETS = (("p12", "Passes 1-2"), ("p34", "Passes 3-4"), ("p1234", "All four passes"))

    # ================================================================ four passes
    BL, PD, IV, AP = FP["by_length"], FP["paired"], FP["intervals"], FP["added_passes"]
    def sc(a, k, ps="p1234"): return BL[a][ps][k]["score"]
    def d(p, k="all", ps="p1234", m="score"): return PD[p][ps][m][k]
    if AP["errors"] or AP["seeds_reused_within_an_arm"] or len(set(AP["prompt_tokens_equal_to_anchor_first_pass"])) != 1:
        stale("the added passes' request counts")
    fp_intro = (f'<p>{gh(f"{RD}/{AM["file"]}", "Amendment 1")} was written after the two-pass results '
                '(<a href="#frozen">further down this page</a>) were read and before the first request of the passes it adds: '
                "single-message passes 3 and 4 for all four configurations, with the same items, lengths, reply cap, concurrency and "
                "sampling settings and new seed blocks. The total of four passes per configuration was fixed before the first request of "
                f"pass 3, so the stopping point does not depend on what the added passes show. They ran {E(AP['ran'])}: "
                f"{n0(AP['requests'])} requests, {AP['errors']} errors, no seed reused within an arm, prompt tokens equal to "
                f"<code>anchor</code>'s first pass on {n0(AP['prompt_tokens_equal_to_anchor_first_pass'][0])} of "
                f"{n0(AP['prompt_tokens_equal_to_anchor_first_pass'][1])} requests.</p>"
                "<p>The rule is the frozen one applied to more passes: request score = fields right / fields if the reply finished on its "
                "own, else 0; repeats averaged within the item; differences paired by item; 95% interval from 10,000 resamples of the 60 "
                "items (seed 5). Three pass sets are shown side by side: passes 1-2 (the frozen protocol's result), passes 3-4 alone, and "
                "all four. <b>The four-pass reading is an extension decided after the two-pass results were read.</b> "
                f"{code(REF)} differs from the three probe arms as a whole checkpoint, so no difference from one of them is attributable "
                "to one component.</p>")

    def cell(a, k):
        c = BL[a]["p1234"][k]
        return bar(c["score"][0], 1.0, f3(c["score"][0]), sub=f'all 8 right {c["right"]} of {c["n"]}')
    rows = [[arm(a)] + [cell(a, k) for k, _ in LENS] +
            [lvl(sc(a, "all")), f'{BL[a]["p1234"]["all"]["right"]} of {BL[a]["p1234"]["all"]["n"]}',
             f'{BL[a]["p1234"]["all"]["unfinished"]} <span class="ci">({BL[a]["p1234"]["128k"]["unfinished"]} at 127K)</span>',
             f3(BL[a]["p1234"]["128k"]["score_finished_only"])] for a in ARMS4]
    def passes(k): return "; ".join(f"{code(a)} " + ", ".join(f3(x) for x in BL[a]["score_by_pass"][k]) for a in ARMS4)
    SP = FP["single_pass_spread"]
    t_arms = rich("Share of answer fields right, four passes", f"Single message, four passes pooled: {FP['requests_per_arm']} requests per "
                  "configuration, 240 per length. Unfinished replies score 0. Second figure: replies with every field right. Interval: "
                  "95% over items",
                  ["Configuration"] + [n for _, n in LENS] + ["All lengths", "Every field right", "Unfinished replies", "Finished replies only, 127K"], rows,
                  foot=f"Score per pass, all lengths (passes 1, 2, 3, 4): {passes('all')}. At 127K: {passes('128k')}. A single pass of one "
                       f"configuration moves by up to {SP['all_lengths']:.2f} over all lengths and {SP['at_127k']:.2f} at 127K.")

    def state(p):
        e = [excl(d(p, "all", ps)) for ps, _ in SETS]
        if e == [False, False, True]: return badge(True, "excludes 0 only at four passes")
        if e[2]: return badge(True, "excludes 0")
        if e[0] and not e[1]: return badge(False, no="includes 0") + "<small>excluded 0 at passes 1-2 only</small>"
        if e == [False, True, False]: return badge(False, no="includes 0") + "<small>excluded 0 at passes 3-4 only</small>"
        return badge(False, no="includes 0")
    if [excl(d("hqa - compact", "all", ps)) for ps, _ in SETS] != [False, False, True]: stale("the hqa - compact intervals by pass set")
    if [excl(d(f"{REF} - compact", "all", ps)) for ps, _ in SETS] != [True, False, False]: stale(f"the {REF} - compact intervals by pass set")
    rows = [[pair4(p)] + [dcell(d(p, "all", ps), 0.08) for ps, _ in SETS] + [state(p)] for p in PD]
    t_sets = rich("Paired difference in field score, all lengths: three pass sets", "Right of the line: the first-named configuration scored "
                  "higher. Paired by item, 95% interval over the 60 items; solid bar: the interval excludes 0; bar edge = 0.08",
                  ["Difference", "Passes 1-2 (frozen protocol)", "Passes 3-4 alone", "All four passes", "Four-pass interval"], rows,
                  foot="Passes 3-4 alone and the four-pass column are the extension; passes 1-2 are the frozen comparison and the post hoc "
                       f"reading of {code(REF)} as published on 2026-11-11.")
    rows = [[pair4(p)] + [dcell(d(p, k), 0.08) for k, _ in LENS] for p in PD]
    t_len = rich("Paired difference in field score by length, four passes", "Same reading as the table above; bar edge = 0.08",
                 ["Difference"] + [n for _, n in LENS], rows)

    EX = IV["excluding_zero"]
    MEAS = {"score": "field score", "every field right": "every field right"}
    def meas(x):
        m, _, fam = x["measure"].partition(", ")
        return MEAS[m] + (f" in <code>{fam}</code>" if fam else "") + f", {LAB[x['lengths']]}"
    six = "; ".join(f"{pair4(x['pair'])} on {meas(x)} ({iv3(x['value'])})" for x in IV["excluding_zero_at_four_passes"])
    if len(IV["excluding_zero_at_four_passes"]) != EX["p1234"]["count"] or IV["per_pass_set"] != 102: stale("the interval counts")
    P12, P34 = IV["excluding_zero_at_passes_1_2"], IV["excluding_zero_at_passes_3_4"]
    def cnt(xs, f): return sum(1 for x in xs if f(x))
    P34C = [cnt(P34, lambda x: x["pair"].startswith(REF)), cnt(P34, lambda x: x["pair"] == f"{REF} - hqa"),
            cnt(P34, lambda x: x["measure"] == "every field right" and x["lengths"] == "4k"), cnt(P34, lambda x: x["measure"].endswith(", join"))]
    if (len(P12) != EX["p12"]["count"] or len(P34) != EX["p34"]["count"] or IV["excluding_zero_in_both_two_pass_sets"]
            or cnt(P12, lambda x: x["pair"].startswith(REF)) != len(P12) or min(P34C) < 1):
        stale("the intervals excluding 0 in the two-pass sets")
    twelve = "; ".join(f"{pair4(x['pair'])} on {meas(x)}" for x in P12)
    counts = (f"<p><b>How many intervals exclude 0.</b> Each pass set holds {IV['per_pass_set']} intervals: six pairs × 17 (field score at "
              "four lengths, all lengths and two length groups; every field right at four lengths, all lengths and 64K + 127K; "
              "<code>ledger</code> field score at 64K + 127K; field score in each of three task families), with no correction for "
              f"their number. {EX['p12']['count']} exclude 0 at passes 1-2, {EX['p34']['count']} at passes 3-4 and {EX['p1234']['count']} "
              f"at four passes. At a 95% level about 5 of {IV['per_pass_set']} would exclude 0 with no difference anywhere, so a single "
              f"interval of these tables is not evidence on its own. The {EX['p1234']['count']} at four passes: {six}. The "
              f"{EX['p12']['count']} at passes 1-2 all involve {code(REF)}: {twelve}. Of the {EX['p34']['count']} at passes 3-4, {P34C[0]} "
              f"involve {code(REF)} ({P34C[1]} of them against <code>hqa</code>), {P34C[2]} are every field right at 4K and {P34C[3]} are "
              "in <code>join</code> (the three groups overlap). <b>No interval excludes 0 in both two-pass sets.</b> The lists are in <code>SUMMARY.json</code> "
              "(<code>four_pass.intervals</code>).</p>")

    ha, ca, hc, ra, rh, rc = (d(p) for p in PD)
    if list(PD) != ["hqa - anchor", "compact - anchor", "hqa - compact"] + [f"{REF} - {a}" for a in ARMS]: stale("the pair names")
    if any(excl(d("hqa - anchor", "all", ps)) for ps, _ in SETS) or excl(ca) or excl(d("compact - anchor", "128k")) or excl(ra) or excl(rh) or excl(rc):
        stale("the four-pass intervals")
    if not excl(d("hqa - compact", "128k")) or excl(d(f"{REF} - compact", "128k")): stale("the 127K intervals")
    others = [a for a in ARMS4 if a != "compact"]
    for ps in ("p12", "p34"):
        if sc("compact", "all", ps)[0] >= min(sc(a, "all", ps)[0] for a in others): stale("compact's place in each pass set")
        if d("compact - anchor", "all", ps)[0] >= 0 or d("hqa - compact", "all", ps)[0] <= 0: stale("the sign of compact's gap in each pass set")
    bp = {a: BL[a]["score_by_pass"]["128k"] for a in ARMS4}
    rng = {a: max(bp[a]) - min(bp[a]) for a in ARMS4}
    if any(h <= c_ for h, c_ in zip(bp["hqa"], bp["compact"])) or min(rng, key=rng.get) != "compact": stale("the per-pass scores at 127K")
    hmar = [h - c_ for h, c_ in zip(bp["hqa"], bp["compact"])]
    if [a_ < c_ for a_, c_ in zip(bp["anchor"], bp["compact"])] != [True, False, False, False]: stale("anchor and compact pass by pass at 127K")
    short = [d("compact - anchor", k) for k in ("4k", "16k", "64k")]
    if any(excl(v) for v in short): stale("compact's differences up to 64K")
    A7 = FP["at_127k"]
    CAPC, CAPR = S["capture"]["against_text"]["prefill"]["arms"]["compact"], S["capture"]["between_arms"]["prefill"]["rows"]
    if CAPC["nll_minus_ref"][0] > 0 or CAPC["top1_minus_ref"][1] > 0 or CAPC["top1_minus_ref"][2] < 0: stale("the capture figures for compact")
    def a7(ps, key, arms=ARMS4, f=str): return [f(A7[ps][a][key]) for a in arms]
    fo = {ps: {a: A7[ps][a]["score_finished_only"] for a in ARMS4} for ps, _ in SETS}
    if (A7["p12"]["compact"]["unfinished"] != A7["p12"]["anchor"]["unfinished"] or fo["p12"]["compact"] >= fo["p12"]["anchor"]
            or max(fo["p34"], key=fo["p34"].get) != "compact" or A7["p34"]["compact"]["unfinished"] <= max(A7["p34"][a]["unfinished"] for a in others)):
        stale("the unfinished and finished-only figures at 127K by pass set")
    CU, LE, HW = FP["compact_unfinished_all_lengths"], FP["ledger_every_field_right_64k_128k"], FP["half_width_ratio_four_over_two_passes"]
    r34, r127, h127 = d(f"{REF} - compact", "all", "p34"), d(f"{REF} - compact", "128k"), d("hqa - compact", "128k")
    if abs(r127[0] - h127[0]) > 0.01: stale("the two 127K differences over compact")
    bound = max(abs(x) for v in (ra, rh) for x in v[1:3])
    right = {a: BL[a]["p1234"]["all"]["right"] for a in ARMS4}
    if right[REF] >= min(right["anchor"], right["hqa"]) or LE[REF][0] >= min(LE[a][0] for a in ARMS): stale("the every-field-right counts")
    if BL[REF]["score_by_pass"]["all"].index(min(BL[REF]["score_by_pass"]["all"])) != 2: stale("the reference checkpoint's per-pass scores")
    era, erh = (PD[f"{REF} - {a}"]["p1234"]["every_field_right"] for a in ("anchor", "hqa"))
    if excl(era["all"]) or excl(erh["all"]) or not excl(era["64k+128k"]) or right[REF] > right["compact"]: stale("the every-field-right intervals")
    lg = {ps: PD["compact - anchor"][ps]["ledger_64k+128k_score"] for ps, _ in SETS}
    ph12 = S["post_hoc_long_context"]["64k+128k"]["compact - anchor"]["ledger"]["score"]["single"]
    if abs(ph12[0] - lg["p12"][0]) > 0.0006 or max(abs(ph12[i] - lg["p12"][i]) for i in (1, 2)) > 0.003: stale("the two resamplings of the passes 1-2 ledger interval")
    lgh = PD["hqa - compact"]["p1234"]["ledger_64k+128k_score"]
    FAM = FP["by_family"]
    def lcount(ps): return [sum(FAM[a]["ledger"][k][ps]["right"] for k in ("64k", "128k")) for a in ARMS]
    def lnum(ps): return sum(FAM["anchor"]["ledger"][k][ps]["n"] for k in ("64k", "128k"))
    if (lg["p12"][0] >= 0 or lg["p34"][0] <= 0 or any(excl(v) for v in lg.values()) or excl(lgh) or lcount("p12")[2] >= lcount("p12")[1]
            or lcount("p34")[2] < max(lcount("p34")[:2]) or [a_ + b_ for a_, b_ in zip(lcount("p12"), lcount("p34"))] != [LE[a][0] for a in ARMS]):
        stale("the ledger slice by pass set")
    s4k, s127 = [sc(a, "4k")[0] for a in ARMS4], [sc(a, "128k")[0] for a in ARMS4]
    hp, hr_, hm = [HW["paired_score_all"][p] for p in PAIRS], [HW["paired_score_all"][f"{REF} - {a}"] for a in ARMS], HW["arm_mean_all"]
    f2 = lambda x: f"{x:.2f}"
    o127 = [sc(a, "128k")[0] for a in others]
    def fam(ps, f): return PD["hqa - compact"][ps]["by_family_all_lengths"][f]
    def top_fam(ps): return max(("join", "ledger", "trace"), key=lambda f: fam(ps, f)[0])
    FALL = {a: round(round(FP["by_length"][a]["p1234"]["4k"]["score"][0], 3) - round(FP["by_length"][a]["p1234"]["128k"]["score"][0], 3), 3)
            for a in ARMS4}                                   # differences of the figures as shown in the table above
    fall_rest = sorted(FALL[a] for a in ARMS4 if a != "compact")
    fall_extra = FALL["compact"] - fall_rest[1]
    if ([top_fam(ps) for ps, _ in SETS] != ["ledger", "join", "join"] or max(FALL, key=FALL.get) != "compact"
            or f"{min(FALL.values()):.2f}" != "0.06" or f"{fall_extra:.2f}" != "0.03"):
        stale("the family split of hqa - compact or the falls with length")
    fp_reading = ("<ul>"
                  f"<li><b><code>hqa</code> against <code>anchor</code>: no difference measured, and the bound is tighter.</b> {iv3(ha)}: the "
                  f"95% interval reaches down to {s3(ha[1])}. Basis: four passes, 60 items, {FP['requests_per_arm']} requests per "
                  "configuration; the same reading in both pass sets.</li>"
                  "<li><b><code>compact</code> is the lowest configuration in both pass sets, by about one point over four passes, and the "
                  f"gap is at 127K.</b> Up to 64K it is level with the others (differences from <code>anchor</code> of "
                  f"{', '.join(s3(v[0]) for v in short)}). At 127K it scores {f3(sc('compact', '128k')[0])} against "
                  f"{span(o127, f3)}, and its four single passes there ({span(bp['compact'], f3)}) are the steadiest of the four configurations. "
                  f"Against <code>hqa</code> the four-pass interval excludes 0 ({iv3(hc)} over all lengths, {iv3(h127)} at 127K); against "
                  f"<code>anchor</code> it does not ({iv3(ca)}; at 127K {iv3(d('compact - anchor', '128k'))}). Strength: indicated, not "
                  "established. It rests on the same sign in both pass sets and on the single passes at 127K, not on one interval among "
                  f"{IV['per_pass_set']}: there <code>compact</code> is below <code>hqa</code> in every pass (by {f3(min(hmar))} in the "
                  f"closest, pass {hmar.index(min(hmar)) + 1}) and below <code>anchor</code> in three of four (pass 1 reverses: "
                  f"{f3(bp['anchor'][0])} against {f3(bp['compact'][0])}).</li>"
                  "<li><b>Where <code>compact</code>'s 127K gap comes from: these tables do not settle it; the replies themselves do.</b> "
                  "Pooled over four passes it matches the "
                  f"unfinished replies: {A7['p1234']['compact']['unfinished']} of {A7['p1234']['compact']['n']} at 127K against "
                  f"{', '.join(a7('p1234', 'unfinished', others)[:-1])} and {a7('p1234', 'unfinished', others)[-1]}, while replies that "
                  f"finished score level ({f3(fo['p1234']['compact'])} against {span([fo['p1234'][a] for a in others], f3)}). The two pass "
                  f"sets do not agree on that split. In passes 1-2 <code>compact</code> had as many unfinished replies at 127K as "
                  f"<code>anchor</code> ({A7['p12']['compact']['unfinished']} and {A7['p12']['anchor']['unfinished']}) and a lower "
                  f"finished-only score ({f3(fo['p12']['compact'])} against {f3(fo['p12']['anchor'])}); in passes 3-4 it had "
                  f"{A7['p34']['compact']['unfinished']} unfinished against {', '.join(a7('p34', 'unfinished', others)[:-1])} and "
                  f"{a7('p34', 'unfinished', others)[-1]} and the highest finished-only score ({f3(fo['p34']['compact'])}). Of its "
                  f"{CU['unfinished']} unfinished replies over all lengths, {CU['reply_cap']} reached the reply cap and {CU['repetition']} "
                  "ended on the repetition abort. By task family the pass sets disagree as well: over four passes "
                  f"<code>hqa</code> {MINUS} <code>compact</code> sits in <code>join</code> ({iv3(fam('p1234', 'join'))}; "
                  f"<code>ledger</code> {s3(fam('p1234', 'ledger')[0])}, <code>trace</code> {s3(fam('p1234', 'trace')[0])}), but passes "
                  f"1-2 put it in <code>ledger</code> ({s3(fam('p12', 'ledger')[0])}, <code>join</code> {s3(fam('p12', 'join')[0])}) and "
                  f"passes 3-4 in <code>join</code> ({s3(fam('p34', 'join')[0])}, <code>ledger</code> {s3(fam('p34', 'ledger')[0])}). "
                  'The <a href="#capture">scoring capture</a> reads other texts, long and given, in one launch per configuration, and '
                  f"samples nothing. It shows no deficit for <code>compact</code> at predicting text: its NLL minus <code>anchor</code>'s is "
                  f"{iv4(CAPC['nll_minus_ref'])} (lower is better), share of positions whose top token is the given one "
                  f"{iv4(CAPC['top1_minus_ref'])} (exploratory, one capture, {n0(CAPR)} positions to 128K). The capture does not locate "
                  "the gap. It shows only that <code>compact</code> is not worse at next-token prediction on long given text; the gap "
                  "was seen in generated replies at 127K." + (sz["fp"] if sz else "") + "</li>"
                  f'<li><b>The two-pass lead of {code(REF)} over <code>compact</code> (<a href="#reference">reference checkpoint</a>) did '
                  f"not repeat.</b> Passes 3-4 alone give {iv3(r34)} and the four-pass interval includes 0 ({iv3(rc)}). At 127K the "
                  f"four-pass difference is {iv3(r127)}, the same size as <code>hqa</code>'s over <code>compact</code>.</li>"
                  f"<li><b>{code(REF)} sits with <code>anchor</code> and <code>hqa</code> on score</b> ({s3(ra[0])} and {s3(rh[0])}, "
                  f"intervals within ±{bound:.3f}). It has fewer replies fully right than those two in count: {right[REF]} of "
                  f"{FP['requests_per_arm']} against {right['anchor']} and {right['hqa']} (<code>compact</code> {right['compact']}). "
                  f"Over all lengths those two intervals include 0 ({iv3(era['all'])} and {iv3(erh['all'])}, as a share of replies); "
                  f"at 64K + 127K pooled the one against <code>anchor</code> excludes 0 ({iv3(era['64k+128k'])}), one of the "
                  f"{EX['p1234']['count']} listed above. On <code>ledger</code> at 64K + 127K it has {LE[REF][0]} of {LE[REF][1]} fully "
                  f"right against {', '.join(str(LE[a][0]) for a in ARMS[:-1])} and {LE[ARMS[-1]][0]} (<code>anchor</code>, "
                  "<code>hqa</code>, <code>compact</code>). Whole-checkpoint difference; not attributable to one component.</li>"
                  '<li><b>The two-pass lean against the K6 core on running totals (<a href="#ledger">further down</a>) did not '
                  f"repeat.</b> On <code>ledger</code> at 64K + 127K, <code>compact</code> {MINUS} <code>anchor</code> in field score was "
                  f"{iv3(lg['p12'])} in passes 1-2, {iv3(lg['p34'])} in passes 3-4 and is {iv3(lg['p1234'])} over four; "
                  f"<code>hqa</code> {MINUS} <code>compact</code> is {iv3(lgh)} over four. Replies with every field right there: "
                  f"{', '.join(str(x) for x in lcount('p12')[:-1])} and {lcount('p12')[-1]} of {lnum('p12')} in passes 1-2, "
                  f"{', '.join(str(x) for x in lcount('p34')[:-1])} and {lcount('p34')[-1]} of {lnum('p34')} in passes 3-4 "
                  "(<code>anchor</code>, <code>hqa</code>, <code>compact</code>). Twenty items; every one of these intervals includes "
                  f"0. The two-pass section further down gives the passes 1-2 interval as {iv3(ph12)}: the same requests, resampled "
                  "with another seed.</li>"
                  f"<li><b>Accuracy still falls with length in every configuration</b>: {span(s4k, f3)} at 4K to {span(s127, f3)} at 127K "
                  f"over four passes, a fall of {', '.join(f3(FALL[a]) for a in ARMS4[:-1])} and {f3(FALL[ARMS4[-1]])} "
                  f"({', '.join(code(a) for a in ARMS4)}). About {min(FALL.values()):.2f} of it is common to the four, the BF16-core "
                  "<code>anchor</code> included, so that part does not come from the settings that differ between them; "
                  f"<code>compact</code>'s further {fall_extra:.2f} is its 127K gap above. The four share the model family, the "
                  "engine, the sampling settings, the reply cap and the tasks themselves, whose distractor text grows with length. No "
                  "unquantized model and no other engine ran these tasks, so this run does not say where the common fall comes "
                  "from.</li>"
                  f"<li><b>Precision gained.</b> The amendment stated in advance that four passes would narrow paired intervals to "
                  f"{E(HW['stated_before_the_data']['paired'])} of their two-pass half-width and arm means to "
                  f"{E(HW['stated_before_the_data']['arm_mean'])} of theirs. Measured: {', '.join(f2(x) for x in hp[:-1])} and {f2(hp[-1])} "
                  f"for the three probe pairs, {span(hr_, f2)} for pairs with {code(REF)}; arm means {span([hm[a] for a in ARMS], f2)} for "
                  f"the probe arms and {f2(hm[REF])} for {code(REF)} (its third pass was its lowest).</li></ul>")
    SPD, AG = FP["descriptive_speed"]["by_pass_set"], FP["agreement"]
    fp_desc = ("<p>Descriptive, four passes, median per stream under the mixed load of eight requests (not an arm comparison under the "
               "protocol): decode tokens/s at 4K / 16K / 64K / 127K " +
               ", ".join(f"{code(a)} " + " / ".join(f"{SPD['p1234'][a]['decode_tok_s_median'][k]:.1f}" for k, _ in LENS) for a in ARMS4) +
               "; first token at 127K " + ", ".join(f"{SPD['p1234'][a]['first_token_s_median_127k']:.1f}" for a in ARMS4) +
               f" s (same order). Of {AG['of']} item, length and pass cells, all four configurations had every field right in "
               f"{AG['all_four_arms_right']} and none did in {AG['no_arm_right']}.</p>")

    # ================================================================ distance from the BF16 model
    FS, TP, AR, DF, RD_, YS = BD["sets"]["fidelity_set"], BD["sets"]["teacher_panel"], BD["arms"], BD["differences"], BD["reading"], BD["yardsticks"]
    fp8, k325 = YS["official_fp8_release"], YS["k3.25_on_cuteafd"]
    kl = {a: AR[a]["fidelity_set"]["kl"] for a in ARMS4}
    kt = {a: AR[a]["teacher_panel"]["kl"] for a in ARMS4}
    order = sorted(ARMS4, key=lambda a: kl[a][0])
    BK = list(FS["buckets"])
    reach = f"{FS['last_generated_position'] / 1000:.1f}K"
    Q = "results/2026-10-26-cuteafd-vs-vllm/q"
    if (reach != "14.4K" or BK != ["0-2K", "2-8K", "8-16K"] or not fp8["fidelity_set_kl"] < kl[order[0]][0]
            or not kl[order[-1]][0] < k325["fidelity_set_kl"] or not max(kt.values(), key=lambda v: v[0])[0] < k325["teacher_panel_kl"]):
        stale("the reach of the reference sets or the place of the two figures for scale")
    bf_intro = ("<p>The graded tasks compare the configurations with each other, and the "
                '<a href="#capture">scoring capture</a> further down reads them against given text. Neither says how far a configuration '
                "is from the unquantized model. This stage measures that on two reference sets that hold BF16 outputs. Its plan "
                f'({gh(f"{RD}/{BD["plan"]["file"]}", "<code>ADDENDUM-BF16REF.md</code>")}, hashes in '
                f'{gh(f"{RD}/{BD["plan"]["hashes"]}", "<code>FROZEN.json</code>")}) was written {E(BD["plan"]["written"])}. Status: '
                f'{E(BD["plan"]["status"])}. Ran {E(BD["ran"])}. The engine scores fixed token ids on its prefill path, so no sampling, '
                "seeds or thinking setting are involved. "
                f"Engine build <code>{E(BD['engine_source'])}</code>: {E(BD['engine_source_note'])}.</p>"
                "<p><b>The two sets use different measures and are not comparable with each other. Neither reaches past "
                f"{reach}: the 64K and 127K lengths of the task runs have no BF16 reference here.</b></p>")
    def lv(v): return bar(v[0], 0.05, f4(v[0])) + f' <span class="ci">[{f4(v[1])}, {f4(v[2])}]</span>'
    def pt(x): return bar(x, 0.05, f4(x))
    rows = [["Official FP8 model<small>baseline recorded in the fidelity set's manifest, on the engine author's build and hardware; quoted, not recomputed here</small>", pt(fp8["fidelity_set_kl"]), "", "", "", ""]]
    rows += [[arm(a), lv(kl[a])] + [f4(AR[a]["fidelity_set"]["by_bucket"][b]["kl"][0]) for b in BK] + [lv(kt[a])] for a in order]
    rows += [["K3.25 checkpoint on this engine<small>measured 2026-10-26 on an earlier release; same sets and measures</small>",
              pt(k325["fidelity_set_kl"]), "", "", "", pt(k325["teacher_panel_kl"])]]
    t_kl = rich("KL from the BF16 model", f"Nats; 0 is identical, lower is closer. Fidelity set: generated positions, contexts to {reach}. "
                "Teacher panel: 2K contexts. 95% interval over windows. Ordered by the fidelity-set figure; bar edge = 0.05",
                ["Configuration", "Fidelity set, generated positions"] + BK + ["Teacher panel"], rows,
                foot="The first and last rows are for scale and come from other measurements. Official FP8 model: the baseline the "
                     "engine author (tpurtell) recorded in the fidelity set's manifest (<code>calibration.baseline_metrics</code>, prefill "
                     f"path; {f4(fp8['fidelity_set_kl'])} in both of its repeats) for the checkpoint <code>zai-org/GLM-5.3-Flash</code> "
                     "against the same BF16 root, with this set's measure, on the author's engine build and hardware. It is quoted, not "
                     f'recomputed here (it is also quoted in {gh(f"{Q}/RESULTS-Q.md", "<code>RESULTS-Q.md</code>")} of the 2026-10-26 '
                     "run). K3.25 checkpoint: measured here on 2026-10-26 on an earlier engine release, the K3.25 Core-FP8 checkpoint on "
                     "CuteAFD v3.0.1 "
                     f'({gh(f"{Q}/pb/pb-C1.json", "<code>pb-C1.json</code>")}, {gh(f"{Q}/pa/pa-C1.json", "<code>pa-C1.json</code>")}). '
                     "The bucket columns hold this stage's generated positions and are left empty for those two rows. "
                     f"{E(BD['fidelity_gate'][:1].upper() + BD['fidelity_gate'][1:])}.")
    rows = [["Source", f'the engine author\'s published fidelity set, config <code>{E(FS["config"])}</code>', "published BF16 teacher logits for GLM 5.3 Flash"],
            ["Size", f'{FS["windows"]} windows, {FS["scored_positions_per_window"]} scored positions each; {n0(FS["generated_positions"])} generated '
                     f'positions in {FS["windows_with_generated_positions"]} windows', f'{TP["windows"]} windows of {n0(TP["tokens_per_window"])} tokens; {n0(TP["scored_rows"])} scored rows'],
            ["Measure", "KL over the reference's top 1,024 tokens plus one term for the rest (the author's rule), ratio of sums over generated positions",
             "KL over the full vocabulary, mean over rows"],
            ["Context length", f"to {reach}; buckets " + ", ".join(BK), E(TP["context_length"])],
            ["Interval", "window bootstrap, 5,000 draws", "window bootstrap, 20,000 draws"]]
    t_refsets = rich("The two reference sets", "", ["", "Fidelity set", "Teacher panel"], rows)
    def two(a, key, f): return f"{f(AR[a]['fidelity_set'][key])} / {f(AR[a]['teacher_panel'][key])}"
    rows = [[arm(a), two(a, "top1", f4), two(a, "nll_above_bf16", s4), two(a, "confident_top1", f4)] for a in ARMS4]
    t_other = rich("Other measures against BF16", "Fidelity set / teacher panel",
                   ["Configuration", "Most likely token same as BF16's", "NLL above BF16, nats", "Same, where BF16 is confident"], rows)
    RP, PC = BD["repeat"]["by_arm"], BD["port_against_cli"]["by_arm"]
    same = {tuple(RP[a]["same_argmax_generated_positions"]) for a in ARMS4}
    recs = {tuple(x["records_agreeing"]) for a in ARMS4 for x in PC[a].values()}
    if (len(same) != 1 or len(recs) != 1 or any(RP[a]["kl_difference"] for a in ARMS4) or any(x["largest_kl_difference"] for a in ARMS4 for x in PC[a].values())
            or len({*next(iter(same))}) != 1 or len({*next(iter(recs))}) != 1):
        stale("the repeat launch and the port check")
    g, r = next(iter(same))[0], next(iter(recs))[0]
    repeat = (f"<p><b>Repeat.</b> A second launch of each configuration reproduced the fidelity-set result exactly: KL difference 0.0 and "
              f"the same most likely token on {n0(g)} of {n0(g)} generated positions, in all four. The float64 port used for the intervals "
              f"and the engine CLI agree on {n0(r)} of {n0(r)} records per configuration and launch (largest KL difference 0.0).</p>")

    if max(kl[a][1] for a in ARMS4) >= min(kl[a][2] for a in ARMS4): stale("the overlap of the four fidelity-set intervals")
    NAME = {"anchor": "anchor: BF16 core (reference)", "hqa": "hqa: BF16 q_b_proj + o_proj, rest K6", "compact": "compact: K6 core", REF: f"{REF}: EXLR8 K4 checkpoint"}
    panel = ([("Official FP8 model (recorded baseline)", fp8["fidelity_set_kl"], "r")] + [(NAME[a], kl[a][0], "c") for a in order] +
             [("K3.25 checkpoint (measured 2026-10-26)", k325["fidelity_set_kl"], "c")])
    svg = SC.bars([("KL from the BF16 model · fidelity set, generated positions", panel)], label_w=270,
                  aria="KL from the BF16 model on the fidelity set: the four configurations between the official FP8 model and the K3.25 checkpoint")
    trows = [[E(lab), f4(v), "baseline recorded in the set's manifest; quoted, not recomputed here" if k == "r" else ("measured 2026-10-26 on CuteAFD v3.0.1" if "K3.25" in lab else
              f"[{f4(kl[lab.split(':')[0]][1])}, {f4(kl[lab.split(':')[0]][2])}]")] for lab, v, k in panel]
    fig = SC.figure("bf16-scale", "Distance from the BF16 model, with two figures for scale",
                    f"KL from the BF16 model on the fidelity set (generated positions, contexts to {reach}), one bar per configuration, between "
                    "the baseline recorded for the official FP8 model in the set's manifest and the K3.25 checkpoint measured on this engine on 2026-10-26. The "
                    "bars carry no interval; the table above and the table view give them.",
                    [(svg, None, None)],
                    "The four middle bars sit close together and their own 95% intervals overlap. That overlap does not decide any "
                    "pair; the paired differences table below, computed on the same rows, does. The first and last bars come from "
                    f"other measurements. Nothing here reaches past {reach}.",
                    rich("", "", ["Row", "KL, nats", "95% interval or source"], trows),
                    legend_items=[("bc", "CuteAFD: the four configurations, and the K3.25 checkpoint on an earlier release"),
                                  ("br", "official FP8 model: baseline recorded in the set's manifest, not recomputed here")])

    if list(DF) != ["hqa - anchor", "compact - anchor", "compact - hqa"] + [f"{REF} - {a}" for a in ARMS]: stale("the pair names of the BF16 differences")
    rows = [[pair4(p), dcell4(DF[p]["fidelity_set"]["overall"], 0.01)] + [dcell4(DF[p]["fidelity_set"][b], 0.01) for b in BK] +
            [dcell4(DF[p]["teacher_panel"], 0.01)] for p in DF]
    BI = BD["intervals"]
    if any(x["set"] != "fidelity set" for x in BI["excluding_zero"]) or BI["selected"] != "none": stale("the list of BF16 intervals excluding 0")
    t_diff = rich("Differences between configurations on the same rows", "KL of the first-named minus KL of the second, nats. Left of the "
                  "line: the first-named is closer to BF16. Solid bar: the 95% interval excludes 0. Bar edge = 0.01",
                  ["Difference", "Fidelity set, generated positions"] + BK + ["Teacher panel"], rows,
                  foot="The three probe arms share their K4 experts, so a difference between two of them reflects what differs outside "
                       "the experts: <code>ATTENTION_MODE</code> alone between <code>hqa</code> and <code>compact</code>; the rest of the "
                       'core and the output head between <code>anchor</code> and either (FP8 settings as logged: '
                       '<a href="#trade-terms">terms</a>). '
                       f"A difference involving {code(REF)} is a whole-checkpoint difference and is not attributable to one "
                       f"component. {BI['listed']} intervals are listed ({BI['fidelity_set']} on the fidelity set, {BI['teacher_panel']} on "
                       f"the teacher panel) with no correction for their number; {len(BI['excluding_zero'])} exclude 0, all on the fidelity "
                       "set. None was selected.")

    dha, dca, dch = DF["hqa - anchor"], DF["compact - anchor"], DF["compact - hqa"]
    dr = [DF[f"{REF} - {a}"] for a in ARMS]
    far, close = RD_["farthest_bucket_in_every_arm"], RD_["closest_bucket_in_every_arm"]
    for a in ARMS4:
        b = {x: AR[a]["fidelity_set"]["by_bucket"][x]["kl"][0] for x in BK}
        if max(b, key=b.get) != far or min(b, key=b.get) != close: stale("the buckets' order")
    probe_gap = RD_["largest_difference_between_probe_arms"]
    if (not excl(dha["fidelity_set"]["overall"]) or dha["fidelity_set"]["overall"][0] >= 0 or excl(dha["teacher_panel"])
            or probe_gap / min(kl[a][0] for a in ARMS) >= 0.1 or order[0] != "hqa" or order[-1] != REF
            or any(not excl(v["fidelity_set"]["overall"]) or v["fidelity_set"]["overall"][0] <= 0 or excl(v["teacher_panel"]) for v in dr)
            or excl(dca["fidelity_set"]["overall"]) or excl(dch["fidelity_set"]["overall"]) or excl(dca["teacher_panel"]) or excl(dch["teacher_panel"])):
        stale("the BF16 distances")
    f3_ = lambda x: f"{x:.3f}"
    short_task = max(abs(d(p, k)[0]) for p in PAIRS for k in ("4k", "16k"))
    x1, x2 = RD_["exlr8_k4_farther_than_each_probe_arm"]
    bf_reading = ("<ul>"
                  "<li><b>All four configurations sit in one band, between the official FP8 model and K3.25.</b> "
                  f"{f3_(RD_['band_fidelity_set'][0])} to {f3_(RD_['band_fidelity_set'][1])} on the fidelity set: "
                  f"{RD_['times_the_fp8_figure'][0]:.1f} to {RD_['times_the_fp8_figure'][1]:.1f} times the FP8 baseline and "
                  f"{RD_['share_of_the_k3.25_figure'][0]:.2f} to {RD_['share_of_the_k3.25_figure'][1]:.2f} of the K3.25 figure.</li>"
                  "<li><b>What differs between the three probe arms is a small part of that distance.</b> They share their K4 "
                  "experts. <code>hqa</code> and <code>compact</code> differ in <code>ATTENTION_MODE</code> alone, and between those two "
                  f"the distance does not move measurably (<code>compact</code> {MINUS} <code>hqa</code> "
                  f"{iv4(dch['fidelity_set']['overall'])} on the fidelity set, {iv4(dch['teacher_panel'])} on the teacher panel). "
                  "<code>anchor</code> differs from them in the rest of the core and in the output head: it is launched with the "
                  "engine's three FP8 conversion settings off, which keeps both at BF16 "
                  '(<a href="#trade-terms">FP8 settings as logged</a>). '
                  f"Between the three the distance moves by at most {f3_(probe_gap)}, under a tenth of the total; the rest is "
                  "common to the three. The plan stated before the first request that <code>anchor</code>'s "
                  "distance would not be zero (quantized experts and the engine's numerics; the two are not separated here). "
                  f"<code>anchor</code> is also not the closest: <code>hqa</code> is {f4(abs(dha['fidelity_set']['overall'][0]))} "
                  f"closer on the fidelity set ({iv4(dha['fidelity_set']['overall'])}, interval excludes 0) and level on the teacher "
                  f"panel ({iv4(dha['teacher_panel'])}); <code>compact</code> {MINUS} <code>anchor</code> is "
                  f"{iv4(dca['fidelity_set']['overall'])} on the fidelity set, interval includes 0. <code>anchor</code> is also a "
                  "locally derived checkpoint; why it measures slightly farther than <code>hqa</code> on one set is an "
                  '<a href="#open">open question</a>.</li>'
                  f"<li><b>{code(REF)} is {f3_(x1)} to {f3_(x2)} farther than each probe arm on the fidelity set and level with them on the "
                  "teacher panel.</b> The two sets place it differently, and this stage does not say which is nearer. Each set has its "
                  "own provenance. The fidelity set is the engine author's; its relation to the calibration data of either checkpoint "
                  "is not known. The teacher panel is drawn from the corpus the producer of the K4 experts published and can favour "
                  "the experts the three probe arms carry (stated in the plan before the first request); a tilt of that kind would "
                  "run toward the probe arms on that panel, which is the set where the four are level; it does not bear on the "
                  f"fidelity set, where {code(REF)} is farther. Whole-checkpoint difference.</li>"
                  f"<li><b>In every configuration the {far} bucket is the farthest and {close} the closest.</b> The buckets hold different "
                  f"texts ({far} is long code reading), so this is not a length trend on its own.</li>"
                  "<li><b>Where both kinds of measurement exist, both show small differences.</b> Up to 16K the task scores of the three probe arms are "
                  f"within {short_task:.2f} of each other over four passes, and their distances from BF16 within {f3_(probe_gap)}. The one "
                  "task difference indicated on this page, <code>compact</code> at 127K, lies beyond the reach of either reference set, so "
                  "this stage neither supports nor contradicts it. Added later on 2026-11-12: the fifth configuration's task difference at 127K "
                  "lies beyond both sets too.</li></ul>")
    bf_limits = "<p>Limits: " + "; ".join(E(x) for x in BD["limits"]) + ".</p>"

    # ================================================================ what each configuration trades
    CO, WB = TO["columns"], TO["weights_outside_experts_mib_back"]
    def row(label, key, f): return [label] + [f(CO[a][key]) for a in ARMS4]
    def outside(a):
        t = CO[a]["outside_the_experts"]
        return E(t) if a != REF else E(t.replace(" (section 9)", "")) + ' (<a href="#reference">reference checkpoint</a>)'
    if not CO[REF]["outside_the_experts"].endswith(" (section 9)") or CO[REF]["weights_outside_experts_mib_both_gpus"] is None: stale("the trade-off table's cells")
    rows = [("grp", "What is loaded"),
            ["Outside the experts"] + [outside(a) for a in ARMS4],
            row("Weights outside the experts, both GPUs, MiB", "weights_outside_experts_mib_both_gpus", n0),
            row("Resident weights, both GPUs, MiB", "resident_weights_mib_both_gpus", n0),
            ("grp", f"Distance from the BF16 model: KL in nats, lower is closer; contexts to {reach} only"),
            row(f"Fidelity set, to {reach}", "kl_from_bf16_fidelity_set", f4),
            row("Teacher panel, 2K", "kl_from_bf16_teacher_panel", f4),
            ("grp", f"Graded tasks, four passes: {FP['requests_per_arm']} requests per configuration"),
            row("Field score, all lengths", "score_four_passes_all_lengths", f3),
            row("Field score at 127K", "score_four_passes_127k", f3),
            row(f"Every field right, of {FP['requests_per_arm']}", "every_field_right_of_960", str),
            row(f"Unfinished replies, of {FP['requests_per_arm']}", "unfinished_of_960", str),
            ("grp", "Speed as run: median per stream under a mixed load of eight requests; descriptive, not an arm comparison"),
            row("Decode tokens/s at 127K", "decode_tok_s_127k_median", lambda x: f"{x:.1f}"),
            row("First token at 127K, s", "first_token_s_127k_median", lambda x: f"{x:.1f}")]
    t_trade = rich("Cost and measured quality, side by side", "One column per configuration; every figure is from a section below or, for the "
                   "two memory rows, from the launch logs. Intervals are in those sections",
                   [""] + [code(a) for a in ARMS4], rows,
                   foot=f"{code(REF)} is another checkpoint, not a setting of the same one. The two distance rows use different measures and "
                        "are not comparable with each other.")
    sp = {ps: SPD[ps] for ps in ("p12", "p34")}
    for ps in sp:
        tok = {a: sp[ps][a]["decode_tok_s_median"]["128k"] for a in ARMS4}; ft = {a: sp[ps][a]["first_token_s_median_127k"] for a in ARMS4}
        if max(tok, key=tok.get) != "anchor" or min(ft, key=ft.get) != "anchor" or max(ft, key=ft.get) != REF: stale("the speeds as run")
    if (round(kl[order[-1]][0] - kl[order[0]][0], 4) != RD_["largest_difference_between_the_four"]
            or dha["fidelity_set"]["overall"][0] > 0 or dha["teacher_panel"][0] > 0):
        stale("the distances behind the trade-off bullets")
    kf, ff, fall = RD_["k3.25_farther_than_the_four"], RD_["fp8_closer_than_the_four"], FP["fall_4k_to_127k"]
    RB, SCL = TO["resident_weights_mib_back"], S["launch"]["kv_pool_tokens_scoring_launches"]
    AP_, HP_, FB, WM, RL = (TO["anchor_to_hqa_parts"], TO["hqa_to_compact_parts"], TO["left_under_memory_cap_mib_back"],
                            TO["workspaces_mib_more_than_anchor"], TO["resident_less_weights_outside_experts_mib"])
    HD = AP_["head_mib"]
    if (AP_["sum_mib"] != WB["anchor_to_hqa"] or 2 * AP_["layers_mib_per_gpu"] + AP_["head_difference_mib"] != WB["anchor_to_hqa"]
            or HD["anchor"] - HD["hqa"] != AP_["head_difference_mib"] or 2 * HP_["layers_mib_per_gpu"] != WB["hqa_to_compact"]
            or any(abs(RB[k] - WB[k]) > 2 for k in WB) or max(RL[a] for a in ARMS) - min(RL[a] for a in ARMS) > 2 or RL[REF] <= RL["anchor"]
            or any(FB[k] >= WB[k] for k in WB) or min(WM.values()) <= 0
            or SCL["anchor"][0] >= SCL["hqa"][0] or {SCL["hqa"][0], SCL["compact"][0]} != {TO["kv_pool_tokens_every_serving_launch"]}):
        stale("the memory figures or the scoring-launch pools")
    SV = S["launch"]["serving"]
    def left(g): return g["cap_mib"] - g["weights_mib"] - g["workspaces_mib"] - g["reserve_mib"] - g["kv_pool_mib"]
    per_gpu = {a: {tuple(left(x["gpus"][g]) for g in ("rtx0", "rtx1")) for x in SV[a]} for a in ARMS}
    if any(len(v) != 1 or sum(next(iter(v))) != TO["left_under_memory_cap_mib_both_gpus"][a] for a, v in per_gpu.items()):
        stale("the per-GPU memory left under the cap")
    left_min = {a: min(next(iter(v))) for a, v in per_gpu.items()}
    caps = {x["gpus"][g]["cap_mib"] for a in ARMS for x in SV[a] for g in ("rtx0", "rtx1")}
    pools = {x["gpus"][g]["kv_pool_mib"] for a in ARMS for x in SV[a] for g in ("rtx0", "rtx1")}
    if max(caps) - min(caps) > 5 or len(pools) != 1 or not left_min["anchor"] < left_min["hqa"] < left_min["compact"]:
        stale("the per-GPU cap and pool figures")
    cap_gpu, pool_gpu = max(caps), next(iter(pools))
    fp8log = {a: {(x["kda_fp8"], x["fp8_prefill"], x["head"]) for x in SV[a]} for a in ARMS}
    if fp8log != {"anchor": {("Off", "[None]", "BF16")}, "hqa": {("Off", "[Mla, Ffn]", "K6")}, "compact": {("Off", "[Mla, Ffn]", "K6")}}:
        stale("the FP8 settings as logged")
    n_serv = sum(len(SV[a]) for a in ARMS)
    def beyond(x): return (sum(g["weights_outside_experts_mib"] for g in x["gpus"].values()) - 2 * x["coordinator_weights_gib"] * 1024
                           - x["head_mib"] - x["token_embedding_mib"])
    rest_ref = {round(beyond(x)) for x in S["reference"]["launch"]["serving"]}
    if any(abs(beyond(x)) > 2 for a in ARMS for x in SV[a]) or len(rest_ref) != 1 or min(rest_ref) < 100:
        stale("what the weights outside the experts add up to")
    rest_ref = next(iter(rest_ref))
    trade_reading = ("<ul>"
                     f"<li><b>BF16 core to <code>hqa</code>: {n0(WB['anchor_to_hqa'])} MiB of weights back over the two GPUs, no quality cost "
                     f"measured.</b> Task score {iv3(ha)} over four passes; distance from BF16 not larger on either set. Strength: the "
                     f"best-supported reading here ({FP['requests_per_arm']} requests per configuration, both pass sets, two reference "
                     "sets). The step changes two things together: the core outside the two projection groups and the output head, "
                     'both BF16 in <code>anchor</code> and K6 in <code>hqa</code> (<a href="#trade-terms">FP8 settings as logged</a>). '
                     "It does not separate the two.</li>"
                     f"<li><b><code>hqa</code> to <code>compact</code>: a further {n0(WB['hqa_to_compact'])} MiB back; a score about one "
                     "point lower over all lengths is indicated, and it is replies at 127K that did not finish, not answers that were "
                     "wrong.</b> The two differ in <code>ATTENTION_MODE</code> alone. "
                     f"Over all lengths <code>hqa</code> {MINUS} <code>compact</code> is {iv3(hc)} and <code>compact</code> {MINUS} "
                     f"<code>anchor</code> {iv3(ca)}. "
                     "Up to 64K <code>compact</code>'s task score is level with the other two, and its overall distance from BF16 is "
                     "level with theirs on both reference sets (intervals include 0). At 127K it "
                     f"scores {f3(sc('compact', '128k')[0])} against {f3(sc('hqa', '128k')[0])} (<code>hqa</code> {MINUS} "
                     f"<code>compact</code> {iv3(h127)}); against <code>anchor</code> the interval includes 0 "
                     f"({iv3(d('compact - anchor', '128k'))}). The "
                     '<a href="#capture">scoring capture</a>, on other long given texts, shows no deficit for <code>compact</code> at '
                     "next-token prediction; it does not locate the gap, which was seen in generated replies at 127K. Pooled over "
                     f"four passes the gap matches unfinished replies: {A7['p1234']['compact']['unfinished']} of "
                     f"{A7['p1234']['compact']['n']} at 127K against {', '.join(a7('p1234', 'unfinished', others)[:-1])} and "
                     f"{a7('p1234', 'unfinished', others)[-1]}, with finished replies level ({f3(fo['p1234']['compact'])} against "
                     f"{span([fo['p1234'][a] for a in others], f3)}). The two pass sets do not agree on that split or on the task "
                     "family, so these tables alone do not say where the gap comes from." + (sz["trade"] if sz else "") +
                     " Strength of the gap itself: indicated, not established "
                     '(<a href="#four-pass">four passes</a>).</li>'
                     f"<li><b>What the memory buys on this hardware.</b> Of the first step, {n0(2 * AP_['layers_mib_per_gpu'])} MiB is "
                     f"in the 45 layers ({n0(AP_['layers_mib_per_gpu'])} MiB on each GPU) and {n0(AP_['head_difference_mib'])} MiB is the "
                     f"output head ({n0(HD['anchor'])} MiB in BF16 against {n0(HD['hqa'])} MiB in K6), which <code>ATTENTION_MODE</code> "
                     f"does not select; the second step is all in the layers ({n0(HP_['layers_mib_per_gpu'])} MiB on each GPU). "
                     f"Resident weights fall by the same amounts to within 2 MiB ({n0(RB['anchor_to_hqa'])} and "
                     f"{n0(RB['hqa_to_compact'])} MiB). Not all of it arrives as free memory: <code>hqa</code> and <code>compact</code> "
                     f"hold larger workspaces ({n0(WM['hqa'])} and {n0(WM['compact'])} MiB more than <code>anchor</code> over both GPUs), "
                     "so the memory left under the engine's cap after weights, workspaces, reserve and KV pool rises by "
                     f"{n0(FB['anchor_to_hqa'])} MiB from <code>anchor</code> to <code>hqa</code> (which also holds "
                     f"{TO['reserve_mib_less_than_anchor']['hqa']} MiB less reserve) and by a further "
                     f"{n0(FB['hqa_to_compact'])} MiB to <code>compact</code>. The cap is per GPU (about {n0(cap_gpu)} MiB, of which "
                     f"the KV pool holds {n0(pool_gpu)} MiB); the smaller of the two per-GPU figures is {n0(left_min['anchor'])}, "
                     f"{n0(left_min['hqa'])} and {n0(left_min['compact'])} MiB (<code>anchor</code>, <code>hqa</code>, "
                     "<code>compact</code>). In the serving launches, with eight requests at once, "
                     f"every configuration was admitted the maximum KV pool ({n0(TO['kv_pool_tokens_every_serving_launch'])} tokens), so "
                     "there the saving stayed as unused memory, not as pool size. It was seen to convert once: in the scoring launches "
                     'of the exploratory depth profile (<a href="#checks">checks before the graded runs</a>), with 16 requests at once, '
                     f"<code>anchor</code> was admitted {n0(SCL['anchor'][0])} tokens and <code>hqa</code> and "
                     '<code>compact</code> the maximum (<a href="#memory">launch figures</a>). No launch here showed '
                     "<code>compact</code> admitted a larger pool than <code>hqa</code>. That is one launch setting read from "
                     "logs; pool and batch size were not varied as a measurement.</li>"
                     "<li><b>Speed is not an arm comparison under the protocol.</b> As run, <code>anchor</code> had the highest median "
                     f"decode speed and the shortest first-token time at 127K in both pass sets, and {code(REF)} the longest first-token "
                     "time. These are medians under one mixed load; the protocol did not isolate speed and no cause is claimed.</li>"
                     f"<li><b>{code(REF)}: task score level with <code>anchor</code> and <code>hqa</code>; fewer replies fully right in count "
                     "(over all lengths those intervals include 0); "
                     f"{f3_(x1)} to {f3_(x2)} farther from BF16 on one set and level on the other.</b> It differs in the whole checkpoint, "
                     "so none of this is attributable to one component.</li>"
                     "<li><b>The larger differences are outside this comparison.</b> Between these four, distance from BF16 moves by "
                     f"{f3_(RD_['largest_difference_between_the_four'])} at most. The K3.25 checkpoint, measured on an earlier "
                     f"release of this engine, sits {f3_(kf[0])} to {f3_(kf[1])} "
                     f"farther than they do and the official FP8 model {f3_(ff[0])} to {f3_(ff[1])} closer "
                     '(<a href="#bf16">rows from other measurements</a>). Task accuracy falls with length in every configuration, '
                     f"<code>anchor</code> included, by {span(list(fall.values()), f2)} from 4K to 127K (<code>compact</code>'s is the largest, "
                     '<a href="#four-pass">Four passes</a>); the largest difference between two of these four '
                     f"configurations at one length is {f3(FP['largest_difference_at_one_length'])} (the fifth configuration, added later, is in "
                     "<a href='#k325'>its own section</a>). The tasks and the engine are shared "
                     "too, and no unquantized model ran these tasks, so the run does not say where the common fall comes from.</li></ul>")
    trade_intro = ("<p><code>anchor</code> is the reference of the probe, not a recommendation. The table puts cost and measured quality "
                   'side by side, and the reading under it says what each step gives and costs. Added 2026-11-12. The terms are '
                   'defined <a href="#trade-terms">under the reading</a>; the configurations and the tasks are set out under '
                   '<a href="#arms">What was tested</a>.</p>'
                   "<p>What can be obtained: <code>hqa</code> and <code>compact</code> are two settings of one checkpoint, "
                   f"K4-Core-K6-HQA. {E(S['hqa_checkpoint']['availability'])} {code(REF)} is a published checkpoint "
                   '(<a href="#reference">reference checkpoint</a>).</p>')
    terms = [
        ("Probe arms and configurations", "the three probe arms are <code>anchor</code>, <code>hqa</code> and <code>compact</code>, which "
                    f"share their K4 experts; the four configurations are those three and {code(REF)}."),
        ("Reference", "used for three things on this page. <code>anchor</code> is the reference arm of the probe, the all-BF16 core "
                    f"the other arms are read against. {code(REF)} is a reference checkpoint in another quantisation format. The BF16 "
                    "model is the unquantized model that distance is measured from. <code>anchor</code> is not the BF16 model: its "
                    "experts are K4."),
        ("Experts", "the model's mixture-of-experts feed-forward weights, most of its size; K4 in the three probe arms "
                    "(<code>anchor</code>, <code>hqa</code>, <code>compact</code>)."),
        ("Core", "the attention and other layer weights outside the experts."),
        ("Head", "the output matrix that turns the last hidden state into token scores."),
        ("K4 and K6", "quantized formats at about 4 and 6 bits per weight (BF16 holds 16)."),
        ("K3.25", "a checkpoint of the same model in the same family of formats, with routed experts at about 3.25 bits per weight and "
                  "an FP8 core, measured here on 2026-10-26 on an earlier engine release (CuteAFD v3.0.1); in the distance tables it "
                  "is a row for scale, not part of that comparison." + (sz["k325_term"] if sz else "")),
        ("FP8 settings", "the engine has three FP8 conversion settings (<code>GLM5_FLASH_KDA_FP8</code>, "
                  "<code>GLM5_FLASH_FP8_HEAD</code>, <code>GLM5_FLASH_FP8_PREFILL</code>). <code>anchor</code> is launched with all "
                  "three off, which keeps its BF16 core matrices and head at BF16. As logged at load, KDA FP8 reads Off in all "
                  f"{n_serv} serving launches of the three probe arms; the FP8 prefill setting reads none in <code>anchor</code> and "
                  "<code>[Mla, Ffn]</code> in <code>hqa</code> and <code>compact</code>; the head reads BF16 in <code>anchor</code> "
                  "and K6 in the other two. Switching the prefill setting off on <code>hqa</code> left every recorded distribution "
                  'bit-identical in a <a href="#checks">check before the graded runs</a>.'),
        ("Passes and pass sets", f"a pass is one run of a configuration's {FP['requests_per_arm'] // 4} requests (60 items at four "
                  "lengths). Passes 1-2 are the frozen two-pass result, passes 3-4 were added under amendment 1, and \"four passes\" "
                  "pools them."),
        ("HQA", "the checkpoint that carries BF16 copies of two attention projections (<code>q_b_proj</code>, <code>o_proj</code>) "
                "beside its K6 core; <code>ATTENTION_MODE</code> selects which copies run."),
        ("Field score (task score, the partial-credit score)", "the share of a reply's eight answer fields that are right, 0 for a "
                "reply that did not finish; higher is better, and one point is 0.01."),
        ("Every field right (the strict measure)", "the count of replies with all eight right."),
        ("Weights outside the experts", "what the engine's startup plan places on the two GPUs outside the experts: the 45 layers' "
                "weights (one copy on each GPU; the load line's \"coordinator weights\"), the output head and the token embedding "
                "table (each on one GPU). In the three probe arms those parts add up to the plan's figure; in "
                f"{code(REF)} the plan's figure is {n0(rest_ref)} MiB more than they add up to, and the logs do not itemize that "
                "remainder. The count of 45 layers is the engine's load line; the HQA checkpoint holds 46 BF16 "
                "<code>o_proj</code> matrices (layer indices 0 to 45) and 12 <code>q_b_proj</code>. Both counts are as read, from "
                "different sources."),
        ("Resident weights", "everything held as weights on the two GPUs after load, experts included. The part that is not "
                "weights outside the experts is the same in the three probe arms "
                f"({', '.join(n0(RL[a]) for a in ARMS[:-1])} and {n0(RL[ARMS[-1]])} MiB) and {n0(RL[REF])} MiB in {code(REF)}, which "
                "brings its own experts; that is why its resident total is not the smallest although its weights outside the "
                "experts are."),
        ("Left under the memory cap", "the engine's per-GPU memory cap minus weights, workspaces, reserve and KV pool."),
        ("Workspaces and reserve", "two items of the engine's admission line beside weights and KV pool, per GPU; read from each "
                "launch's log, not measured here."),
        ("KV pool", "the tokens of attention cache the engine admits for all simultaneous requests together."),
        ("Depth profile and scoring capture", "two exploratory readings of given text, scored position by position with nothing "
                "sampled; the first ran before the graded runs, the second after them with the reference checkpoint. Their launches "
                "are the scoring launches."),
        ("KL", "how far a configuration's next-token probabilities are from the BF16 model's at the same position; the fidelity "
               "set computes it over the reference's top 1,024 tokens plus one term for the rest, the teacher panel over the full "
               "vocabulary."),
        ("Generated positions", f"the scored positions the fidelity set marks as generated text ({n0(FS['generated_positions'])}), as "
               "opposed to context; its figures here are over those."),
        ("Where BF16 is confident", "positions where the BF16 model gives its most likely token a probability of at least 0.5.")]
    trade_terms = ('<p id="trade-terms"><b>Terms used above.</b></p><dl class="gl">'
                   + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in terms) + "</dl>")
    trade_limits = ("<p>Limits: " + "; ".join(E(x) for x in TO["limits"]) + ".</p>"
                    + ("<p>Added later on 2026-11-12: this section and its table are about the four configurations above. The "
                       "fifth is not a K4-class checkpoint and is set beside them in <a href='#k325'>its own section</a>.</p>" if k5 else ""))

    lede = ("<p>CuteAFD v5.0.0 adds <code>ATTENTION_MODE</code>, which selects the precision at which two groups of attention "
            "projections of the HQA checkpoint of GLM 5.3 Flash run. It has three values; the graded runs here cover two, "
            "<code>hqa</code> (BF16 copies) and <code>compact</code> (K6 copies), and the third, <code>fp8-compact</code>, appears only "
            'in an <a href="#checks">exploratory check</a>. A locally derived all-BF16 core (<code>anchor</code>) is the reference here, not a '
            f"recommendation, and {code(REF)} is a reference checkpoint in another quantisation format. Updated 2026-11-12 with "
            "additions to the frozen two-pass result: four graded passes per configuration, the distance of each configuration from "
            "the unquantized BF16 model and, later that day, how the replies ended, the size of each checkpoint in bits per "
            "weight and a fifth configuration.</p>" + (sz["lede_bits"] if sz else "") +
            f"<p><b>Distance from BF16</b> (two reference sets, contexts to {reach}): the four configurations with 4-bit experts sit in "
            "one band, KL "
            f"{f3_(RD_['band_fidelity_set'][0])} to {f3_(RD_['band_fidelity_set'][1])} on the fidelity set, between the recorded baseline "
            f"for the official FP8 model ({f4(fp8['fidelity_set_kl'])}) and a K3.25 checkpoint measured on an earlier release of this engine "
            f"({f4(k325['fidelity_set_kl'])}; measured on this release as the fifth configuration, below); the three probe arms are within "
            f"{f3_(probe_gap)} of each other. <b>Graded tasks</b>, 4K to 127K, "
            f"four passes: <code>hqa</code> {MINUS} <code>anchor</code> {iv3(ha)} and {code(REF)} {MINUS} <code>anchor</code> {iv3(ra)}, "
            "no difference measured; of these four, <code>compact</code> is the "
            f"lowest in both pass sets, with the gap at 127K ({f3(sc('compact', '128k')[0])} against {span(o127, f3)}): " +
            (sz["lede_gap"] if sz else "indicated, not established, and where it comes from is not settled") +
            ". That 127K difference "
            f"lies beyond the {reach} reach of both reference sets. Accuracy falls with length in every configuration, "
            '<code>anchor</code> included. <a href="#trades">What each configuration trades</a> puts cost and measured quality side by '
            "side.</p>" + (k5["lede"] if k5 else ""))
    body = (sz_bits + h2("trades", "What each configuration trades") + trade_intro + t_trade + trade_reading + trade_terms + trade_limits +
            h2("bf16", "Distance from the BF16 model") + bf_intro + t_kl + fig + t_refsets + t_other + repeat + t_diff + bf_reading + bf_limits +
            h2("four-pass", "Four passes") + fp_intro + t_arms + t_sets + t_len + counts + fp_reading + fp_desc + sz_ends + k5_body)
    data = (f'<p class="sign">Added 2026-11-12. Four passes: {gh(f"{RD}/analysis/samples-extension.csv", "<code>samples-extension.csv</code>")} '
            f'(one row per request of passes 3 and 4, no text) and {gh(f"{RD}/analysis/fourpass.py", "<code>fourpass.py</code>")}, which '
            f'recomputes the four-pass tables from the three CSVs into {gh(f"{RD}/analysis/FOURPASS.json", "<code>FOURPASS.json</code>")} '
            f'(standard library only). Distance from BF16: {gh(f"{RD}/bf16ref/BF16REF.json", "<code>BF16REF.json</code>")}, with the '
            "per-window figures every fidelity-set value and interval follows from; the stage's score files, per-row tables and dumps are "
            "not published.</p>") + sz_data + k5_data
    four = '<a href="#four-pass">Four passes</a>'
    notes = {
        "hc": f"2026-11-12: over four passes this interval excludes 0 ({iv3(hc)}); indicated, not established ({four}).",
        "ledger": f"2026-11-12: the gap did not repeat in passes 3 and 4 ({four}).",
        "fall": f"2026-11-12, four passes: a fall of about {min(FALL.values()):.2f} is common to all four configurations, {code(REF)} "
                f"included, and <code>compact</code>'s is about {fall_extra:.2f} larger ({four}).",
        "open": [f"Dated 2026-11-12, on the first question: over four passes a fall of about {min(FALL.values()):.2f} from 4K to 127K "
                 f"is common to the four configurations, {code(REF)} included. No unquantized model and no other engine ran these "
                 "tasks, so where it comes from is still open.",
                 "Dated 2026-11-12, on the second question: the nominal gap did not repeat. On <code>ledger</code> at 64K + 127K, "
                 f"<code>compact</code> {MINUS} <code>anchor</code> was {iv3(lg['p12'])} in passes 1-2, {iv3(lg['p34'])} in passes 3-4 "
                 f"and is {iv3(lg['p1234'])} over four ({four}).",
                 "Added 2026-11-12: is <code>compact</code>'s lower score at 127K real, and does it come from replies that do not "
                 "finish, from wrong fields in replies that do, or from one task family? Over four passes it is indicated, not "
                 f"established, and the two pass sets disagree on each of those splits ({four})." + (" " + sz["open"] if sz else ""),
                 "Added 2026-11-12: why does <code>anchor</code>, with a BF16 core and head, measure slightly farther from the "
                 f"BF16 model than <code>hqa</code> on the fidelity set (<code>hqa</code> {MINUS} <code>anchor</code> "
                 f"{iv4(dha['fidelity_set']['overall'])}) and level with it on the teacher panel ({iv4(dha['teacher_panel'])})? "
                 "The two share their experts, and <code>anchor</code> is a locally derived checkpoint "
                 '(<a href="#bf16">distance from the BF16 model</a>).'],
        "limits": f"Added 2026-11-12: with the reference checkpoint {code(REF)} the experts are no longer the same in every "
                  "configuration; those four are K4-class checkpoints, and the fifth, added later that day, has K3.25 experts. The additions at "
                  "the top of the page carry two further limits: "
                  f"one engine release, and a BF16 reference that reaches {reach} only."}
    return lede, body, data, notes


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
                   f"{IV['computed']} intervals, so it is a lead and not a finding. It is on the field score (partial credit) only: on every field "
                   f"right the pair does not separate ({iv3(rc_strict)}). Being a whole-checkpoint difference, it does not say which "
                   "component carries it. 2026-11-12: the lead did not repeat in passes 3 and 4, and the four-pass interval includes 0 "
                   '(<a href="#four-pass">Four passes</a>).</li>'
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
                 "<p><b>This capture does not measure distance from the unquantized BF16 model.</b> All four "
                 "are quantized: <code>anchor</code> has a BF16 core and K4 experts, so a difference from <code>anchor</code> is a "
                 'difference from another quantization. The <a href="precision.html">BF16-referenced panels</a> of this repository (texts '
                 "to 14.4K tokens) cover other checkpoints. What this capture references to something fixed is the given text. "
                 'Added 2026-11-12: that distance was measured afterwards for these four configurations, on two reference sets that reach '
                 '14.4K (<a href="#bf16">Distance from the BF16 model</a>).</p>'
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
    if AM["status"] != "complete" or AM["pending"]:
        raise SystemExit("v5 page: amendment 1 is not complete; the page is written for the finished passes")
    amend += (f'<p>Added 2026-11-12: both passes are complete for all four configurations ({E(AM["ran"])}). Their numbers are under '
              '<a href="#four-pass">Four passes</a>; the tables of this part of the page hold passes 1 and 2 only.</p>')
    rows = [[arm(a), badge(True, "done", "pending"), badge(True, "done", "pending")] for a in ARMS4]
    am2 = amend2_sections(S, h2, gh)[1]["am2"] if "amendment_2" in S else ""
    t_am = rich("Passes added by amendment 1", "Complete 2026-11-12",
                ["Arm", "Single message, pass 3", "Single message, pass 4"], rows)

    lede = (f"<p>Added after these results were read: a reference checkpoint in another quantisation format, {code}, on the same items "
            f"(two single-message passes). No difference from <code>anchor</code> ({iv3(ra)}) or from <code>hqa</code> ({iv3(rh)}) is "
            "measured; it differs from the arms as a whole checkpoint, so no difference from an arm is attributable to one component "
            '(<a href="#reference">reference checkpoint</a>). Added 2026-11-12: two further single-message passes per arm, added under '
            '<a href="#amendment">amendment 1</a>, are complete and are read under <a href="#four-pass">Four passes</a>.</p>')
    bullet = (f"<li><b>Reference checkpoint {code}, added after the results were read: no difference from <code>anchor</code> or "
              f"<code>hqa</code> measured</b> ({iv3(ra)} and {iv3(rh)} pooled). Against <code>compact</code> its field score is higher post "
              f"hoc ({iv3(rc)}), on the field score (partial credit) only: a lead, not a finding. Each is a whole-checkpoint difference "
              '(<a href="#reference">details</a>). Added 2026-11-12: the lead over <code>compact</code> did not repeat in passes 3 and 4, '
              'and the four-pass interval includes 0 (<a href="#four-pass">Four passes</a>).</li>')
    body = (h2("reference", "Reference checkpoint: EXLR8 K4") + intro + ref_reading + t_score + t_cls + t_pair + t_agree + t_cost +
            h2("capture", "Scoring capture on the reference checkpoint") + cap_intro + cap_reading + t_abs + t_band + t_heavy + cap_between +
            h2("amendment", "Amendment 1: passes 3 and 4") + amend + t_am + am2)
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
                      "Added 2026-11-12: the tasks are shared as well, and their distractor text grows with length; no unquantized "
                      "model and no other engine ran them, so the run does not locate the fall. "
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
                  f"[{s3(lc['score']['single'][1])}, {s3(lc['score']['single'][2])}], and only the strict measure (every field right) excludes 0. Twenty items "
                  f"cannot tell \"the K6 core costs nothing on running totals at long context\" from \"it costs about {abs(lc['score']['single'][1]):.2f} in field score\". An "
                  f'extension with more <code>ledger</code> items was written down before the data and is held, not run '
                  f'({gh(f"{RD}/notes/ledger-extension-hold.md", "note")}).</p>')
    if "four_pass" in S:
        l4 = {ps: S["four_pass"]["paired"]["compact - anchor"][ps]["ledger_64k+128k_score"] for ps in ("p12", "p34", "p1234")}
        if l4["p34"][0] < 0 or any(v[1] > 0 or v[2] < 0 for v in l4.values()): stale("the dated note on running totals at four passes")
        ledger_txt += ('<p>Added 2026-11-12: two more passes were run after this section was written. Over four passes the '
                       f"lean did not repeat: <code>compact</code> &minus; <code>anchor</code> in <code>ledger</code> field score at 64K + 127K was "
                       f"{s3(l4['p12'][0])} [{s3(l4['p12'][1])}, {s3(l4['p12'][2])}] in passes 1&ndash;2 (resampled separately from the interval "
                       f"above, same data), {s3(l4['p34'][0])} [{s3(l4['p34'][1])}, {s3(l4['p34'][2])}] in passes 3&ndash;4 and is "
                       f"{s3(l4['p1234'][0])} [{s3(l4['p1234'][1])}, {s3(l4['p1234'][2])}] over four. "
                       '<a href="#four-pass">Four passes</a> gives the counts. The tables in this section are the two-pass data as read at the time.</p>')

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
        rows.append([arm(a), bar(L["coordinator_weights_gib"], 7, f'{L["coordinator_weights_gib"]:.2f} GiB'),
                     f'{E(L["head"])}<small>{n0(L["head_mib"])} MiB</small>',
                     f'{n0(g0["weights_outside_experts_mib"])} / {n0(g1["weights_outside_experts_mib"])}',
                     f'{n0(g0["weights_mib"])} / {n0(g1["weights_mib"])}', f'{n0(g0["workspaces_mib"])} / {n0(g1["workspaces_mib"])}',
                     n0(L["kv_pool_tokens"]), f"{n0(free[0])} / {n0(free[1])}"])
    sc = LA["kv_pool_tokens_scoring_launches"]
    mem = rich("What each arm loads and is admitted", "From each serving launch's log; the three launches of an arm report the same figures. MiB per GPU: first / second",
               ["Arm", "Layer weights outside the experts, per GPU", "Head", "Weights outside the experts, MiB", "Resident weights, MiB",
                "Workspaces, MiB", "KV pool, tokens", "Left under the memory cap, MiB"], rows,
               foot=f"Every arm was admitted the configured maximum KV pool ({n0(kv['anchor'])} tokens) in all nine serving launches, so on "
                    "this hardware the memory the cheaper settings save stayed unused under the cap in these launches and did not enlarge "
                    "the pool. Layer weights outside the experts: the load line's \"coordinator weights\", one copy on each GPU. Weights "
                    "outside the experts add the output head and the token embedding table "
                    f"({n0(LA['serving']['anchor'][0]['token_embedding_mib'])} MiB in every arm), each on one GPU. Left under the memory "
                    "cap: cap minus resident weights, workspaces, reserve and KV pool. The column labels and this note were revised "
                    "2026-11-12 and the fourth column added. A smaller pool for <code>anchor</code> "
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
               f"[{s3(lc['score']['single'][1])}, {s3(lc['score']['single'][2])}]); that is open, not shown.<!--note:ledger--></li>"
               f"<li><b><code>hqa</code> against <code>compact</code>: no difference measured</b>, {s3(hc[0])} [{s3(hc[1])}, {s3(hc[2])}] pooled.<!--note:hc--></li>"
               "<li><b>The long-context loss is shared.</b> The reference loses about as much as the other arms, so core precision does not "
               "produce it; a third to a half of it is replies that did not finish.<!--note:fall--></li>"
               "<li><b>Split delivery shows no accuracy cost</b> within intervals of about 0.07; whether model-written history does is untested here.</li></ul>")
    ref_lede, ref_bullet, ref_body, ref_data = reference_sections(S, h2, gh) if "reference" in S else ("", "", "", "")
    lede += ref_lede
    reading = reading[:-len("</ul>")] + ref_bullet + "</ul>"
    ext_lede, ext_body, ext_data, ext_notes = extension_sections(S, h2, gh) if "four_pass" in S else ("", "", "", {})
    for k in ("hc", "ledger", "fall"):
        mark = f"<!--note:{k}-->"
        if reading.count(mark) != 1: stale(f"the place of the dated note '{k}'")
        reading = reading.replace(mark, " " + ext_notes[k] if ext_notes else "")
    if ext_body:
        frozen = (h2("frozen", "The frozen two-pass result, as published 2026-11-11") +
                  "<p><b>Everything from here down is the result of the frozen protocol: two single-message passes and one eight-turn pass "
                  "per arm, as published on 2026-11-11.</b> It is unchanged apart from pointers dated 2026-11-12. Where a four-pass figure "
                  'exists for the same quantity it is under <a href="#four-pass">Four passes</a>, and the two are not interchangeable: the '
                  "two-pass tables are the frozen comparison, the four-pass tables an extension decided after these results were read. "
                  "The summary published with it:</p>" + lede)
        lede = ext_lede
    else:
        frozen = ""
    openq = "<ul>" + "".join(f"<li>{E(q)}</li>" for q in S["open_questions"]) + "".join(f"<li>{q}</li>" for q in ext_notes.get("open", [])) + "</ul>"
    limits = ("<p>" + (lambda t: t[:1].upper() + t[1:])("; ".join(E(x) for x in S["limits"])) + ".</p>"
              + (f"<p>{ext_notes['limits']}</p>" if ext_notes else ""))
    data = (f'<p class="sign">Numbers: {gh(f"{RD}/SUMMARY.json", "<code>SUMMARY.json</code>")}. Result as read, with dated corrections: '
            f'{gh(f"{RD}/RESULTS.md", "<code>RESULTS.md</code>")}. One row per request, no text: '
            f'{gh(f"{RD}/analysis/samples.csv", "<code>samples.csv</code>")}; {gh(f"{RD}/analysis/posthoc.py", "<code>posthoc.py</code>")} '
            f'recomputes the scores, differences and intervals from it (launch figures and the left-out counts come from logs and '
            f'replies, which are not in the table). Folder: {gh(RD, "<code>" + RD + "</code>")}. Reply texts are not published.</p>')

    repro = ("<ul>"
             f'<li><b>Recompute.</b> In {gh(RD, "the results folder")}, <code>python3 analysis/posthoc.py</code> (standard library only) '
             "rebuilds the scores, differences and intervals on this page from <code>samples.csv</code> and writes <code>POSTHOC.json</code>; "
             "<code>python3 tools/verify.py</code> at the repository root checks <code>docs/findings.json</code> against the same table. "
             "Run from a clean copy of the published folder on 2026-11-11: same output. Added 2026-11-12: <code>python3 analysis/fourpass.py</code> "
             "rebuilds the four-pass tables from the three CSVs and writes <code>FOURPASS.json</code>, and <code>tools/verify.py</code> "
             "recomputes the fidelity-set figures and intervals of the BF16 stage from the per-window figures in "
             "<code>bf16ref/BF16REF.json</code>.</li>"
             "<li><b>Rebuild the inputs.</b> <code>drivers/gen_tasks.py --items 20 --first 100</code> regenerates the 240 rendered items "
             "from their seeds; it needs the <code>tokenizers</code> package and the model's <code>tokenizer.json</code> (set the path at "
             "the top of the script; its SHA-256 is checked). <code>items/measured/index.json</code> lists the SHA-256 of every rendered item. Regenerated from the published script on "
             "2026-11-11: 240 of 240 hashes match.</li>"
             "<li><b>Re-measure.</b> <code>chain.sh</code>, <code>drivers/run_tasks.py</code> and <code>configs/</code> are what ran, with the "
             "image digest and checkpoint revisions in <code>RUN.json</code>. The HQA checkpoint is no longer on the hub, so "
             "<code>hqa</code> and <code>compact</code> cannot be re-measured without a copy of it; <code>anchor</code>'s checkpoint is "
             "assembled locally, with every core matrix taken from the original BF16 weights, and was never a release. The items and "
             "the scoring do not depend on the engine.</li></ul>")
    body = (ext_body + frozen +
            h2("reading", "What the two-pass results show" if ext_body else "What the results show") + reading +
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
            h2("reproduce", "Reproducing this") + repro + data + ref_data + ext_data)
    page("v5.html", "CuteAFD v5.0.0: core precision at long context", lede, body)


def build(root, page, h2, gh, details):
    if (Path(root) / RD / "SUMMARY.json").exists():
        page_v5(load(root), page, h2, gh, details)
