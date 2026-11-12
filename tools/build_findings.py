#!/usr/bin/env python3
"""Machine-readable entry points for agents and scripts: docs/findings.json and docs/llms.txt.

findings.json lists the claims of the Thinking length investigation (TL-*) and of the CuteAFD v5 context probe (CP-*), one entry per claim: the question, the answer as
the page states it, its status (frozen measurement, extension, planned descriptive, post hoc, exploratory, source reading), the value with
its interval, and where it comes from: a file and a JSON pointer (RFC 6901) into it, plus the per-reply data and the
script that recompute it. Every value is read from the results at build time, never typed here. tools/verify.py
re-resolves every pointer and recomputes the code-study ratios and the context-probe differences from the published
per-reply tables, and the context probe's distances from the BF16 model on the fidelity set from the published per-window
figures.

llms.txt is a plain-text orientation for language-model agents: what the repository is, how to read it, where the
machine-readable data lives, and how to validate it.

    python3 tools/build_findings.py        (run by the export after tools/build_site.py)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/UrbanAstroLA/cuteafd-eval"
SITE_URL = "https://urbanastrola.github.io/cuteafd-eval"
TLD, CSD = "results/2026-11-02-thinking-length", "results/2026-11-03-cuteafd-core-swap"
CTD, APD = "results/2026-11-05-code-thinking", "results/2026-11-05-attn-position"
NQD, VCD = "results/2026-11-06-new-questions", "results/2026-11-06-vllm-code-thinking"
FAD = "results/2026-11-06-cuteafd-fp8-ablation"
CPD = "results/2026-11-10-context-probe"
CP_ARMS = ("anchor", "hqa", "compact")
CUTEAFD5 = "tpurtell/cuteafd v5.0.0, unmodified launcher"
CUTEAFD = "tpurtell/cuteafd v4.0.0, unmodified launcher"
VLLM = "tpurtell vLLM fork v0.9.2-experimental with a local loader modification (route b), not a tpurtell release"
K6 = "wrldsuksgo2mars/GLM-5.3-Flash-EXL3-K4-Core-K6 @ 5d3fffe1"

_cache = {}


def at(file, pointer):
    """Resolve an RFC 6901 pointer in a repository JSON file."""
    if file not in _cache:
        _cache[file] = json.loads((ROOT / file).read_text())
    v = _cache[file]
    for part in pointer.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        v = v[int(part)] if isinstance(v, list) else v[part]
    return v


def esc(key):
    return key.replace("~", "~0").replace("/", "~1")


def ev(file, pointer, what):
    return {"file": file, "pointer": pointer, "what": what, "value": at(file, pointer)}


def ratio_result(file, base, what):
    """A seed-paired ratio reading: value, 95% interval over prompts, detected, counts."""
    r = at(file, base)
    return ({"name": what, "value": r["ratio"], "ci95": r["ratio_ci95_prompts"], "ci_over": "prompts", "detected": r["detected"],
             "pairs": r["pairs"], "prompts": r["prompts"], "prompts_above_1": r.get("prompts_above_1")},
            [ev(file, base + "/ratio", what), ev(file, base + "/ratio_ci95_prompts", "95% interval over prompts"),
             ev(file, base + "/detected", "rule: interval excludes 1")])


def delta_result(file, pointer, what):
    v = at(file, pointer)
    return ({"name": what, "value": v[0], "ci95": [v[1], v[2]], "ci_over": "questions", "detected": v[1] > 0 or v[2] < 0},
            [ev(file, pointer, what + " [estimate, 2.5%, 97.5%]")])


def finding(fid, question, answer, status, result, evidence, engine, run, page, data=(), recompute=None, direction=None, note=None):
    f = {"id": fid, "question": question, "answer": answer, "status": status, "result": result, "direction": direction,
         "engine": engine, "run": run, "page": f"{SITE_URL}/{page}", "evidence": evidence, "data": list(data)}
    if recompute: f["recompute"] = recompute
    if note: f["note"] = note
    return {k: v for k, v in f.items() if v is not None}


def findings():
    out = []
    S = f"{VCD}/SUMMARY.json"; C = f"{CTD}/SUMMARY.json"; N = f"{NQD}/SUMMARY.json"; A = f"{APD}/SUMMARY.json"; CS = f"{CSD}/SUMMARY.json"
    code_prompts = list(range(4, 16))

    r, e = ratio_result(S, "/reading/core/primary_p4_p15", "reasoning tokens, V-K6 / V-BF16, 12 new code prompts")
    out.append(finding(
        "TL-code-vllm-core", "On the vLLM fork, does K4-Core-K6's 6-bit core change how long code replies think, against the original BF16 core?",
        f"No: {r['value']:.2f}x [{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}], not detected.", "measurement: frozen rule", r, e, VLLM, VCD,
        "thinking.html#code", [f"{VCD}/analysis/samples.csv"],
        {"kind": "seed_paired_ratio", "data": f"{VCD}/analysis/samples.csv", "a": "V-K6", "b": "V-BF16", "prompts": code_prompts,
         "script": f"{VCD}/analysis/analyze_vct.py", "bootstrap": {"draws": 4000, "seed": 20261106, "unit": "prompt", "rng": "Python random.Random"}},
        "ratio above 1 = the 6-bit core thought longer"))

    r, e = ratio_result(C, "/reading/primary_p4_p15", "reasoning tokens, C-K6 / C-K6x, 12 new code prompts")
    out.append(finding(
        "TL-code-cuteafd-core", "On CuteAFD v4.0.0, does the native 6-bit core change how long code replies think, against the BF16 core converted to FP8 at load?",
        f"Yes: {r['value']:.2f}x [{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}], detected, every prompt above 1. See TL-code-engines and "
        "TL-code-fp8-arm for which arm differs and TL-fp8-ablation for which FP8 setting carries it.", "measurement: frozen rule", r, e, CUTEAFD, CTD, "thinking.html#code",
        [f"{CTD}/analysis/samples.csv"],
        {"kind": "seed_paired_ratio", "data": f"{CTD}/analysis/samples.csv", "a": "C-K6", "b": "C-K6x", "prompts": code_prompts,
         "script": f"{CTD}/analysis/analyze_ct.py", "bootstrap": {"draws": 4000, "seed": 20261105, "unit": "prompt", "rng": "Python random.Random"}},
        "ratio above 1 = the 6-bit core thought longer"))

    ec = at(S, "/reading/engine_comparison/primary_p4_p15")
    out.append(finding(
        "TL-code-engines", "Do the two engines agree on the core's effect on code thinking length?",
        f"No: vLLM ratio / CuteAFD ratio = {ec['vllm_over_cuteafd_ratio']:.2f} [{ec['ci95_prompts'][0]:.2f}, {ec['ci95_prompts'][1]:.2f}] "
        "(exp of the vLLM log ratio minus the CuteAFD log ratio, paired by prompt). "
        "By the reading stated before the run, the CuteAFD gap goes with how CuteAFD serves the core, not with the weight values.",
        "measurement: frozen rule",
        {"name": "vLLM ratio / CuteAFD ratio, by prompt", "value": ec["vllm_over_cuteafd_ratio"], "ci95": ec["ci95_prompts"], "ci_over": "prompts",
         "detected": ec["ci95_prompts"][1] < 1 or ec["ci95_prompts"][0] > 1, "prompts": ec["prompts"]},
        [ev(S, "/reading/engine_comparison/primary_p4_p15/vllm_over_cuteafd_ratio", "engine comparison"),
         ev(S, "/reading/engine_comparison/primary_p4_p15/ci95_prompts", "95% interval over prompts")],
        "both", VCD, "thinking.html#code", [f"{VCD}/analysis/samples.csv", f"{CTD}/analysis/samples.csv"],
        direction="below 1 = the vLLM ratio is smaller than the CuteAFD ratio"))

    x = at(S, "/post_hoc_cross_engine/ratios/C-K6x~1V-BF16/p4_p15")
    out.append(finding(
        "TL-code-fp8-arm", "Which of the four code configurations thinks differently?",
        f"CuteAFD's BF16-core configuration (core, KDA projections, vocabulary head and prefill activations in FP8): {x['ratio']:.2f}x the "
        f"vLLM BF16 core on the {x['prompts']} new prompts ({at(S, '/post_hoc_cross_engine/ratios/C-K6x~1V-BF16/all_p0_p15/ratio'):.2f}x over all 16), "
        f"shorter on every prompt; the other three sit within about 4% of each other.",
        "measurement: post hoc",
        {"name": "C-K6x / V-BF16, cross_engine_ratio (see definitions)", "value": x["ratio"], "ci95": None, "prompts": x["prompts"],
         "prompts_above_1": x["prompts_above_1"],
         "medians_of_finished": at(S, "/post_hoc_cross_engine/median_reasoning_tokens")},
        [ev(S, "/post_hoc_cross_engine/ratios/C-K6x~1V-BF16/p4_p15/ratio", "C-K6x / V-BF16"),
         ev(S, "/post_hoc_cross_engine/ratios/C-K6~1V-BF16/p4_p15/ratio", "C-K6 / V-BF16"),
         ev(S, "/post_hoc_cross_engine/median_reasoning_tokens", "median reasoning tokens per arm, finished replies")],
        "both", VCD, "thinking.html#code", [f"{VCD}/analysis/samples.csv", f"{CTD}/analysis/samples.csv"],
        {"kind": "cross_engine_ratio", "data_a": f"{CTD}/analysis/samples.csv", "a": "C-K6x", "data_b": f"{VCD}/analysis/samples.csv",
         "b": "V-BF16", "prompts": code_prompts, "script": f"{VCD}/analysis/cross_engine.py"},
        "below 1 = C-K6x thought less",
        "Not in either frozen rule. Method (definitions/cross_engine_ratio): seed-matched log ratios over finished pairs, averaged within each "
        "prompt, then over prompts. Seed matching only pairs like with like; the unit is the prompt."))

    out.append(finding(
        "TL-code-tests", "Does the length difference change the result on code?",
        "Not between the two cores on either engine: CuteAFD 6-bit 50 and FP8-from-BF16 49 of 64; vLLM fork 6-bit 53 of 64 and BF16 58 of "
        "63 finished; paired intervals include 0. Post hoc across all arms: TL-code-pass-pairs.", "measurement: descriptive",
        {"name": "finished replies passing all hidden tests", "value": {
            "C-K6": at(C, "/per_arm/C-K6/all_tests_pass"), "C-K6x": at(C, "/per_arm/C-K6x/all_tests_pass"),
            "V-K6": at(S, "/per_arm/V-K6/all_tests_pass_of_finished"), "V-BF16": at(S, "/per_arm/V-BF16/all_tests_pass_of_finished")},
         "of_finished": {"C-K6": at(C, "/per_arm/C-K6/finished"), "C-K6x": at(C, "/per_arm/C-K6x/finished"),
                         "V-K6": at(S, "/per_arm/V-K6/finished"), "V-BF16": at(S, "/per_arm/V-BF16/finished")},
         "requests_per_arm": 64},
        [ev(C, "/per_arm/C-K6/all_tests_pass", "C-K6"), ev(C, "/per_arm/C-K6x/all_tests_pass", "C-K6x"),
         ev(S, "/per_arm/V-K6/all_tests_pass_of_finished", "V-K6, of finished"), ev(S, "/per_arm/V-BF16/all_tests_pass_of_finished", "V-BF16, of finished")],
        "both", VCD, "thinking.html#code", [f"{CTD}/analysis/samples.csv", f"{VCD}/analysis/samples.csv"],
        {"kind": "count_all_pass", "data": [f"{CTD}/analysis/samples.csv", f"{VCD}/analysis/samples.csv"]}))

    out.append(finding(
        "TL-fp8-path", "What differs between CuteAFD's two core formats besides the core's weights?",
        "With a BF16 core, CuteAFD v4.0.0's launcher also puts the KDA projections (including three gate projections outside the core) and the "
        "vocabulary head in FP8, and prefill runs the MLA and MLP projections with FP8 activations; with the native 6-bit core these stay on the "
        "6-bit kernels or in BF16. On a two-GPU head split the FP8 KDA path also comes with KDA output sharding, which v4 accepts only "
        "with FP8 KDA and clears for the native core. These are the launcher's defaults (its comment at run-family.sh:2337-2351, v4.0.0), with the author's stated reasons: decode "
        "speed and pool size, and output sharding to avoid rounding the GPUs' partial outputs, checked on teacher-forced top-1 and KL. The "
        "model notes (docs/models/glm5_flash.md 'Default precision') and the --kda-fp8 option text (mod.rs:189-197) describe BF16 KDA as the "
        "two-GPU default; the documents differ, and the launcher's choice is what runs.", "source reading",
        None, [{"file": f"{VCD}/CUTEAFD-FP8-PATH.md", "what": "source and launch-log reading with file:line references"}],
        CUTEAFD, VCD, "thinking.html#fit"))

    F = f"{FAD}/SUMMARY.json"; fb = "/reading/contrasts/primary_p4_p15/"
    r, e = ratio_result(F, fb + esc("F-kda / C-K6x"), "reasoning tokens, F-kda / C-K6x (KDA setting off: projections FP8 -> BF16, KDA output sharding off), 12 new code prompts")
    hd, pr_, nk = (at(F, fb + esc(k_)) for k_ in ("F-head / F-kda", "F-pre / F-head", "F-kda / C-K6"))
    inv = lambda c_: (1 / c_["ratio"], 1 / c_["ratio_ci95_prompts"][1], 1 / c_["ratio_ci95_prompts"][0])
    n_ = inv(nk); gs = at(F, "/reading/gap_share/primary_p4_p15/F-kda"); ov = at(F, fb + esc("C-K6 / F-pre"))
    out.append(finding(
        "TL-fp8-ablation", "Which part of CuteAFD's FP8 path goes with the shorter code reasoning of the BF16-core checkpoint (local derived checkpoint, not a producer release)?",
        f"The KDA launch setting: switching the KDA projections from FP8 to BF16 (on this two-GPU layout that also turns off KDA output "
        f"sharding, which v4 runs only with FP8 KDA) gives {r['value']:.2f}x [{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}], detected, every "
        f"prompt above 1; then the vocabulary head {hd['ratio']:.2f}x [{hd['ratio_ci95_prompts'][0]:.2f}, {hd['ratio_ci95_prompts'][1]:.2f}] and "
        f"prefill activations {pr_['ratio']:.2f}x [{pr_['ratio_ci95_prompts'][0]:.2f}, {pr_['ratio_ci95_prompts'][1]:.2f}], not detected. With the "
        f"KDA setting off the gap to the native 6-bit core closes (C-K6 / F-kda {n_[0]:.2f}x [{n_[1]:.2f}, {n_[2]:.2f}]); KDA's share of "
        f"the gap {gs['share']:.2f} [{gs['ci95_prompts'][0]:.2f}, {gs['ci95_prompts'][1]:.2f}] (above 1 = the point estimate passes the native core; "
        "the interval includes 1, consistent with the whole gap). Settings were switched off cumulatively.", "measurement: frozen rule", r,
        e + [ev(F, fb + esc("F-head / F-kda") + "/ratio", "step: head FP8 -> BF16"), ev(F, fb + esc("F-head / F-kda") + "/ratio_ci95_prompts", "its 95% interval"),
             ev(F, fb + esc("F-pre / F-head") + "/ratio", "step: prefill activations unquantized"), ev(F, fb + esc("F-pre / F-head") + "/ratio_ci95_prompts", "its 95% interval"),
             ev(F, fb + esc("F-kda / C-K6") + "/ratio", "F-kda / C-K6 (its inverse is C-K6 / F-kda)"),
             ev(F, fb + esc("F-kda / C-K6") + "/ratio_ci95_prompts", "F-kda / C-K6, 95% interval (invert and swap ends for C-K6 / F-kda)"),
             ev(F, "/reading/gap_share/primary_p4_p15/F-kda/share", "KDA's share of the gap"),
             ev(F, "/reading/gap_share/primary_p4_p15/F-kda/ci95_prompts", "its 95% interval"),
             ev(F, fb + esc("C-K6 / F-pre") + "/ratio_ci95_prompts", "C-K6 / F-pre, 95% interval")],
        CUTEAFD, FAD, "thinking.html#fp8", [f"{FAD}/analysis/samples.csv", f"{CTD}/analysis/samples.csv"],
        {"kind": "seed_paired_ratio", "data_a": f"{FAD}/analysis/samples.csv", "a": "F-kda", "data_b": f"{CTD}/analysis/samples.csv", "b": "C-K6x",
         "prompts": code_prompts, "script": f"{FAD}/analysis/analyze_fa.py",
         "bootstrap": {"draws": 4000, "seed": 20261106, "unit": "prompt", "rng": "Python random.Random"}},
        "ratio above 1 = the arm with the setting off thought longer",
        f"Cumulative design: each step is measured with the earlier settings already off. Post hoc (the frozen remainder clause was written for a "
        f"shortfall): with all three off the BF16 core thinks a little longer "
        f"than the native core on the 12 new prompts (C-K6 / F-pre {ov['ratio']:.2f}x [{ov['ratio_ci95_prompts'][0]:.2f}, "
        f"{ov['ratio_ci95_prompts'][1]:.2f}]); not on all 16. Not separated: FP8 format vs the power-of-two scale rule; which packed KDA "
        "projections matter; whether the KDA weights' format or the KDA split path that changes with it carries the length; where the "
        "overshoot comes from is not located. C-K6x and C-K6 are the code study's arms, paired by seed; a replayed "
        "request was identical. analyze_fa.py reads the Block L analyzer's merged output (not published); analysis/samples.csv carries the "
        "same per-reply fields. C-K6 / C-K6x here uses bootstrap seed 20261106, the code study 20261105, so its interval differs in the third decimal."))

    PPF = f"{FAD}/SUMMARY.json"; pb = "/post_hoc_pass_pairs_across_arms/contrasts/"
    pk = lambda c_, w: ev(PPF, pb + esc(c_) + "/all_pass_difference/" + w, f"{c_}: all-pass difference, {w}")
    out.append(finding(
        "TL-code-pass-pairs", "Across the code-thinking arms of both engines, does passing all hidden tests differ in paired replies?",
        "Post hoc, every contrast looked at (13): the arms with CuteAFD's FP8 settings switched off (F-kda, F-head, F-pre) and the vLLM BF16 "
        "core pass more often than both CuteAFD code-study arms; 5 of 13 intervals exclude 0, all that way, and 2 after allowing for 13 looks "
        "(F-pre, all three settings off, against each code-study arm). The two CuteAFD cores, a fifth apart in reasoning length, pass equally "
        "often: passing does not follow length, and the native core (none of the FP8 settings) passes about as often as the FP8-from-BF16 "
        "core.", "measurement: post hoc",
        {"name": "all-pass difference, first arm minus second, share of paired finished replies",
         "value": {c_: v["all_pass_difference"]["mean"] for c_, v in at(PPF, "/post_hoc_pass_pairs_across_arms/contrasts").items()},
         "contrasts_examined": at(PPF, "/post_hoc_pass_pairs_across_arms/contrasts_examined")},
        [pk("C-K6 vs C-K6x", "mean"), pk("C-K6 vs C-K6x", "ci95_prompts"), pk("V-K6 vs C-K6", "ci95_prompts"),
         pk("V-BF16 vs C-K6x", "ci95_prompts"), pk("F-kda vs C-K6x", "ci95_prompts"), pk("F-pre vs C-K6", "ci95_prompts"),
         pk("F-pre vs C-K6", "bonferroni_ci"), pk("F-pre vs C-K6x", "bonferroni_ci")],
        "both", FAD, "thinking.html#fp8", [f"{CTD}/analysis/samples.csv", f"{VCD}/analysis/samples.csv", f"{FAD}/analysis/samples.csv"],
        {"kind": "pass_pairs", "data": [f"{CTD}/analysis/samples.csv", f"{VCD}/analysis/samples.csv", f"{FAD}/analysis/samples.csv"],
         "script": f"{FAD}/analysis/pass_pairs.py", "bootstrap": {"draws": 4000, "seed": 20261108, "unit": "prompt", "rng": "Python random.Random"}},
        "above 0 = the first arm passed more often",
        "Pairs: same prompt and seed, both finished. 95% bootstrap over the 16 prompts (4,000, seed 20261108); Bonferroni intervals for 13 "
        "looks from 20,000 draws, same seed. The F arms ran a day after the C arms (a replayed request was identical) and V-* is another "
        "engine. One prompt family; the share of tests passed moves by up to about 4 points."))

    out.append(finding(
        "TL-fp8-where", "Where in CuteAFD does the code-length difference arise: prefill or generation?",
        "Most likely on the generation path (decode and speculative verify); prefill is not excluded. Prompts are 1,155-1,758 tokens against "
        "medians of 50-68K reasoning tokens; speculative verify steps run on the decode programs, which read the FP8 KDA copies, and KDA output "
        "sharding is not limited to prefill. The KDA setting also changes the KDA projections in prefill, and the prompt's recurrent state seeds "
        "every later token. Not separated: KDA in prefill against generation, plain decode against speculative verify.",
        "judgement: source and measurements", None,
        [{"file": f"{FAD}/FA-RESULT.md", "what": "section 'Where in the engine', with tpurtell/cuteafd v4.0.0 engine.rs line references"},
],
        CUTEAFD, FAD, "thinking.html#fp8",
        note="The prefill-activation switch (F-pre) covers the MLA and MLP activations, not the KDA projections, so it does not bear on this. "
             "The teacher-forced results (stop decision, KL) run through the prefill programs on science-question traces and do not measure this path on code."))

    r, e = ratio_result(CS, "/step1/contrasts/experts", "reasoning tokens, K4-Core-K6's experts / K4's, 8 prompts")
    out.append(finding(
        "TL-experts", "Do the routed experts change thinking length?", f"No measurable contribution: {r['value']:.2f}x "
        f"[{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}].", "measurement: frozen rule", r, e, CUTEAFD, CSD, "thinking.html#cuteafd",
        [f"{CSD}/analysis/samples.csv"], direction="ratio above 1 = K4-Core-K6's experts thought longer"))

    r, e = delta_result(N, "/cuteafd/core_bf16_minus_6bit_lp_close", "log p(</think>) at the close, BF16 core - 6-bit core, CuteAFD, 30 new questions")
    out.append(finding(
        "TL-stop-cuteafd", "On CuteAFD, does the core change when the model decides to stop on fixed science-question reasoning traces?",
        f"No: {r['value']:+.4f} [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] on the new questions; no effect on the earlier 11 either.",
        "exploratory", r, e, CUTEAFD, NQD, "thinking.html#at-a-glance", [f"{NQD}/analysis/NQ.json"],
        direction="BF16 core minus 6-bit core, as in the source file; the page shows the same numbers with the sign flipped (6-bit minus BF16)"))

    r, e = delta_result(N, "/secondary/all_minus_k6_lp_close", "log p(</think>) at the close, BF16 core - 6-bit core, vLLM fork, 30 new questions")
    out.append(finding(
        "TL-stop-vllm", "On the vLLM fork, does the core change when the model decides to stop on fixed science-question reasoning traces?",
        f"No: {r['value']:+.4f} [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] on the new questions.", "exploratory", r, e, VLLM, NQD,
        "thinking.html#at-a-glance", [f"{NQD}/analysis/NQ.json"], direction="BF16 core minus 6-bit core, as in the source file; the page shows the same numbers with the sign flipped (6-bit minus BF16)"))

    r0, e0 = delta_result(A, "/qbo/lp_close/delta_by_question", "q_b + output projections BF16 - 6-bit, 11 questions")
    r1, e1 = delta_result(N, "/primary_qbo_minus_k6/delta_by_question", "q_b + output projections BF16 - 6-bit, 30 new questions")
    out.append(finding(
        "TL-qbo", "Do q_b and the output projections in BF16 move the stop decision?",
        f"Not in general: {r0['value']:+.4f} on the 11 questions they were found on, {r1['value']:+.4f} [{r1['ci95'][0]:+.4f}, "
        f"{r1['ci95'][1]:+.4f}] on 30 new questions, not replicated.", "exploratory",
        {"original_11": r0, "new_30": r1, "pooled_41": at(N, "/pooled_qbo_minus_k6_lp_close")}, e0 + e1 +
        [ev(N, "/pooled_qbo_minus_k6_lp_close", "pooled over 41 questions [estimate, 2.5%, 97.5%]")],
        VLLM, NQD, "thinking.html#at-a-glance", [f"{NQD}/analysis/NQ.json"], direction="BF16 side minus 6-bit side"))

    out.append(finding(
        "TL-identity", "Do two launches of the same model agree?",
        "CuteAFD: bit-identical on every scored row, also two days later. vLLM fork: no; the launch difference is as large as the core's.",
        "measurement: frozen rule",
        {"cuteafd_rows_bit_identical": [at(CS, "/step2/identity_second_launch/rows_bit_identical"), at(CS, "/step2/identity_second_launch/rows")],
         "cuteafd_cross_day": [at(A, "/cuteafd_cross_day_recheck/rows_bit_identical"), at(A, "/cuteafd_cross_day_recheck/rows")]},
        [ev(CS, "/step2/identity_second_launch/rows_bit_identical", "rows bit-identical, second launch"),
         ev(A, "/cuteafd_cross_day_recheck/rows_bit_identical", "rows bit-identical, two days later")],
        "both", CSD, "thinking.html#at-a-glance"))
    return out + cp_findings()


def cp_findings():
    """The CuteAFD v5.0.0 context probe (results/2026-11-10-context-probe): one engine, three core precisions."""
    if not (ROOT / CPD / "SUMMARY.json").exists():
        return []
    out = []
    S = f"{CPD}/SUMMARY.json"; data = [f"{CPD}/analysis/samples.csv"]; single = ["single-rep0", "single-rep1"]
    def s3(x): return "0.000" if round(x, 3) == 0 else f"{x:+.3f}"
    def iv(v): return f"{s3(v[0])} [{s3(v[1])}, {s3(v[2])}]"
    def res(pointer, what):
        v = at(S, pointer)
        return ({"name": what, "value": v[0], "ci95": [v[1], v[2]], "ci_over": "items", "detected": v[1] > 0 or v[2] < 0, "items": v[3]},
                [ev(S, pointer, what + " [estimate, 2.5%, 97.5%, items]")])
    def frozen(a, b):
        return {"kind": "item_paired_difference", "estimator": "frozen", "data": data[0], "a": a, "b": b, "passes": single,
                "lengths": ["4k", "16k", "64k", "128k"], "script": f"{CPD}/analysis/posthoc.py",
                "bootstrap": {"draws": 10000, "seed": 5, "unit": "item", "rng": "Python random.Random", "indices": [250, 9749]}}
    page = "v5.html"
    for fid, a, b, q, tail in (
            ("CP-hqa-vs-anchor", "anchor", "hqa",
             "On CuteAFD v5.0.0, does the default HQA core (BF16 q_b_proj and o_proj, rest K6) score lower than a BF16 core on graded tasks from 4K to 127K tokens?",
             "No difference measured. Basis: 60 items at four lengths, two passes; strength: moderate (one model family, synthetic tasks). "
             "Per-length intervals at 64K and 127K are wider (see SUMMARY.json)."),
            ("CP-compact-vs-anchor", "anchor", "compact",
             "On CuteAFD v5.0.0, does the K6 core (ATTENTION_MODE=compact) score lower than a BF16 core on the same tasks?",
             "No difference measured; compact's largest nominal gap is running totals at 64K and 127K (CP-ledger-long-context)."),
            ("CP-hqa-vs-compact", "compact", "hqa",
             "Do the two modes of the K4-Core-K6-HQA checkpoint, hqa and compact, differ on the same tasks?", "No difference measured.")):
        r, e = res(f"/frozen_rule/differences/{b} - {a}/single/all", f"field score, {b} - {a}, single message, all lengths")
        out.append(finding(fid, q, f"{iv([r['value']] + r['ci95'])} in field score, pooled over lengths; the interval includes 0. {tail}",
                           "measurement: frozen rule", r, e, CUTEAFD5, CPD, f"{page}#differences", data, frozen(a, b),
                           f"above 0 = {b} scored higher than {a}"))

    sc = {a: {k: at(S, f"/score_by_length/{a}/single/{k}/score") for k in ("4k", "16k", "64k", "128k")} for a in CP_ARMS}
    fin = {a: at(S, f"/score_by_length/{a}/single/128k/score_finished_only") for a in CP_ARMS}
    out.append(finding(
        "CP-length-effect", "Does accuracy fall with context length, and does core precision produce the fall?",
        f"It falls in every arm, the BF16 reference included: field score {min(v['4k'] for v in sc.values()):.2f} "
        f"at 4K and {min(v['128k'] for v in sc.values()):.2f} to {max(v['128k'] for v in sc.values()):.2f} at 127K. The reference loses about as much "
        "as the other arms (0.08 against 0.07 and 0.09), so core precision does not produce it. A third to a half of the loss is replies "
        "that did not finish (cap or repetition abort, scored 0): among finished replies the 127K score is "
        + ", ".join(f"{a} {fin[a]:.3f}" for a in CP_ARMS) + ". Where the rest sits is open: the arms share the model, the K4 experts, the engine, "
        "the drafter, the sampling settings and the reply cap.", "measurement: descriptive",
        {"name": "field score by arm and length, single message, two passes", "value": sc, "finished_only_127k": fin},
        [ev(S, f"/score_by_length/{a}/single/{k}/score", f"{a}, {k}") for a in CP_ARMS for k in ("4k", "128k")], CUTEAFD5, CPD, f"{page}#by-length", data))

    base = "/post_hoc_long_context/64k+128k/compact - anchor/ledger"
    r, e = res(f"{base}/score/single", "ledger field score, compact - anchor, 64K and 127K pooled, single message")
    st = at(S, f"{base}/every_field_right/single"); st3 = at(S, f"{base}/every_field_right/single+turns")
    lh = at(S, "/post_hoc_long_context/64k+128k/hqa - anchor/ledger/score/single")
    r["every_field_right"] = {"single": st, "single+turns": st3}
    e += [ev(S, f"{base}/every_field_right/single", "every field right, single message [estimate, 2.5%, 97.5%, items]"),
          ev(S, f"{base}/every_field_right/single+turns", "every field right, with the eight-turn pass")]
    out.append(finding(
        "CP-ledger-long-context", "Does the K6 core cost accuracy on running totals (ledger tasks) at 64K and 127K?",
        f"Open. compact - anchor is {iv([r['value']] + r['ci95'])} in field score (includes 0) and {iv(st)} in every-field-right "
        "(excludes 0), on 20 items. Post hoc: 48 such intervals were computed and two exclude 0, both compact - anchor on ledger "
        f"every-field-right (single message; with the eight-turn pass): a lead, not a finding. hqa - anchor on the same slice is {iv(lh)} "
        "in field score (includes 0).", "measurement: post hoc", r, e, CUTEAFD5, CPD, f"{page}#ledger", data,
        {"kind": "item_paired_difference", "estimator": "pooled", "data": data[0], "a": "anchor", "b": "compact", "passes": single,
         "lengths": ["64k", "128k"], "family": "ledger", "strict": False, "script": f"{CPD}/analysis/posthoc.py",
         "bootstrap": {"draws": 10000, "seed": 7, "unit": "item", "rng": "Python random.Random", "indices": [250, 9750]}},
        "above 0 = compact scored higher than anchor"))

    mw = {a: {k: at(S, f"/turns/model_written_share/{a}/{k}/median") for k in ("4k", "16k", "64k", "128k")} for a in CP_ARMS}
    out.append(finding(
        "CP-turns-scope", "Did the eight-turn pass test a conversation whose history the model wrote?",
        "No. Decode ran in every reply, but the model's own turns were a median "
        f"{100 * mw['anchor']['4k']:.0f}% of the final prompt at 4K and {100 * min(v['128k'] for v in mw.values()):.1f}-{100 * max(v['128k'] for v in mw.values()):.1f}% "
        "at 127K: at long context over 99% of the history was written by prefill. What the pass shows is split delivery: delivering "
        "the same input as eight messages shows no accuracy cost (16K to 127K: every interval includes 0, a cost up to about 0.07 is not "
        "excluded; 4K: eight turns score slightly higher in anchor and hqa, intervals exclude 0). The turn design is to be revised.", "measurement: descriptive",
        {"name": "model-written share of the final prompt, median over 60 sessions", "value": mw,
         "turns_minus_single": {a: at(S, f"/turns/turns_minus_single/{a}") for a in CP_ARMS}},
        [ev(S, f"/turns/model_written_share/{a}/{k}/median", f"{a}, {k}") for a in CP_ARMS for k in ("4k", "128k")] +
        [ev(S, "/turns/scope", "scope note"), ev(S, "/turns/status", "status")], CUTEAFD5, CPD, f"{page}#turns", data))

    ic = {a: at(S, f"/turns/intermediate_caps/{a}") for a in CP_ARMS}
    out.append(finding(
        "CP-intermediate-caps", "In the eight-turn pass, how often was a delivery turn's reply not the requested acknowledgement, and how often did it run to its 4,096-token cap?",
        "Not the bare acknowledgement: " + ", ".join(f"{a} {ic[a]['turns_not_the_acknowledgement']}" for a in CP_ARMS) + " turns. Ran to the cap: " +
        "; ".join(f"{a} {ic[a]['turns_not_stop']} of {ic[a]['delivery_turns']} turns ({ic[a]['sessions_with_one']} sessions)" for a in CP_ARMS) +
        f". {ic['compact']['most_in_one_session']} of compact's capped turns were in one session. Descriptive; the final answers were scored as usual.",
        "measurement: descriptive", {"name": "delivery turns that did not finish with stop", "value": {a: ic[a]["turns_not_stop"] for a in CP_ARMS},
         "not_the_acknowledgement": {a: ic[a]["turns_not_the_acknowledgement"] for a in CP_ARMS}},
        [ev(S, f"/turns/intermediate_caps/{a}/turns_not_stop", a) for a in CP_ARMS] +
        [ev(S, f"/turns/intermediate_caps/{a}/turns_not_the_acknowledgement", f"{a}, not the acknowledgement") for a in CP_ARMS], CUTEAFD5, CPD, f"{page}#turns", data))

    kv = {a: at(S, f"/launch/kv_pool_tokens_serving/{a}") for a in CP_ARMS}
    out.append(finding(
        "CP-kv-pool", "On two RTX PRO 6000, do the cheaper core settings admit a larger KV pool than the BF16 core?",
        f"Not in the graded runs: every arm was admitted the configured maximum, {kv['anchor']:,} tokens, in all nine serving launches. The "
        "saving shows as resident weights and unallocated memory under the cap. A smaller pool for anchor was seen only in the scoring "
        "launches of the exploratory depth profile (16 requests at once).", "source reading",
        {"name": "KV pool admitted, tokens, serving launches", "value": kv,
         "resident_weights_mib_rtx0_rtx1": at(S, "/launch/resident_weights_mib_rtx0_rtx1"),
         "scoring_launches": at(S, "/launch/kv_pool_tokens_scoring_launches")},
        [ev(S, f"/launch/kv_pool_tokens_serving/{a}", a) for a in CP_ARMS] + [ev(S, "/launch/note", "correction note")],
        CUTEAFD5, CPD, f"{page}#memory"))

    out.append(finding(
        "CP-exploratory-checks", "What did the checks before the graded runs show?",
        "Depth profile (five arms: anchor, hqa, compact, fp8c = ATTENTION_MODE=fp8-compact, core-fp8 = the BF16-core checkpoint with the engine's default FP8 conversions; texts to 128K, not the task items): no arm measurably worse than the BF16 reference at predicting the text at any depth. "
        "GLM5_FLASH_FP8_PREFILL=off on the HQA checkpoint: every recorded distribution bit-identical, so not an arm. Two launches of the "
        "same arm: bit-identical rows. Prefix-cache resume against a decode replay: bit-identical in 45 of 46 conversations over four arms together (the "
        "exception is a harness artifact). Greedy output alone and eight at once: one text in all 260 requests per arm. One capture "
        "each; numbers are in the protocol text only.", "exploratory", {"name": "see protocol sections 10 to 13"},
        [{"file": f"{CPD}/protocol/PROTOCOL.md", "what": "sections 10 to 13 (exploratory results recorded before the freeze)"}],
        CUTEAFD5, CPD, f"{page}#checks"))

    if "reference" in json.loads((ROOT / S).read_text()):
        REFA, RJ = "exlr8-k4", f"{CPD}/analysis/REFERENCE.json"
        rdata = data + [f"{CPD}/analysis/samples-reference.csv"]
        whole = at(S, "/reference/whole_checkpoint")
        rp = {a: f"/reference/paired/{REFA} - {a}" for a in CP_ARMS}
        ra, rh, rc = (at(S, rp[a] + "/score/all") for a in CP_ARMS)
        rcl, rcs, rcx = at(S, rp["compact"] + "/score/64k+128k"), at(S, rp["compact"] + "/score/4k+16k"), at(S, rp["compact"] + "/every_field_right/all")
        nint, nex = at(S, "/reference/intervals/computed"), len(at(S, "/reference/intervals/excluding_zero"))
        def out0(v): return v[1] > 0 or v[2] < 0
        if out0(ra) or out0(rh) or not out0(rc) or not out0(rcl) or out0(rcs) or out0(rcx):
            raise SystemExit("findings: the reference checkpoint's intervals no longer match the answer written for them")
        results, evs = {}, []
        for a in CP_ARMS:
            r, e = res(rp[a] + "/score/all", f"field score, {REFA} - {a}, single message, four lengths, two passes")
            results[f"{REFA} - {a}"] = r; evs += e
        evs += [ev(S, rp["compact"] + "/score/64k+128k", f"field score, {REFA} - compact, 64K and 127K pooled [estimate, 2.5%, 97.5%, items]"),
                ev(S, rp["compact"] + "/score/4k+16k", f"field score, {REFA} - compact, 4K and 16K pooled"),
                ev(S, rp["compact"] + "/every_field_right/all", f"every field right, {REFA} - compact, four lengths"),
                ev(S, "/reference/intervals/computed", "intervals computed for the reference reading"),
                ev(S, "/reference/intervals/excluding_zero", "the intervals that exclude 0"),
                ev(S, f"/reference/by_length/{REFA}/all/score", f"{REFA}: field score over four lengths [estimate, 2.5%, 97.5%, items]"),
                ev(S, f"/reference/requests/{REFA}", "requests"), ev(S, f"/reference/errors/{REFA}", "errors"),
                ev(S, f"/reference/prompt_tokens_equal_to_anchor/{REFA}", "requests whose prompt token count equals anchor's"),
                ev(S, "/reference/checkpoint", "checkpoint and revision"),
                ev(RJ, f"/paired/{esc(REFA + ' - anchor')}/score/all", "the same interval in the analysis output")]
        out.append(finding(
            "CP-reference-exlr8-k4",
            "How does a native EXLR8 K4 checkpoint of the same model, served by the same engine, score on the same graded tasks from 4K to 127K tokens?",
            f"No difference measured from anchor or hqa: {iv(ra)} against anchor and {iv(rh)} against hqa. Against compact its field score is "
            f"higher post hoc: {iv(rc)} over four lengths, {iv(rcl)} at 64K and 127K pooled, {iv(rcs)} at 4K and 16K. That is a lead, not a finding: "
            f"the checkpoint was added after the results were read, and this is one of {nint} intervals computed without correction, of which {nex} "
            f"exclude 0 (all exlr8-k4 - compact on field score). It is on the partial-credit score only: on every field right the pair does not "
            f"separate ({iv(rcx)}). {whole} Basis: two single-message passes, 60 items, 480 requests per arm, 0 errors, prompt tokens equal to "
            "anchor's on every request; strength: low for the difference from compact (post hoc, one of many intervals), moderate for the absence "
            "of a measured difference from anchor and hqa (one model family, synthetic tasks, intervals of about 0.013 either side).",
            "measurement: post hoc", results, evs, CUTEAFD5, CPD, f"{page}#reference", rdata + [RJ],
            {"kind": "item_paired_difference", "estimator": "frozen", "data": rdata, "a": "compact", "b": REFA, "passes": single,
             "lengths": ["4k", "16k", "64k", "128k"], "script": f"{CPD}/analysis/reference.py", "result": f"{REFA} - compact",
             "bootstrap": {"draws": 10000, "seed": 5, "unit": "item", "rng": "Python random.Random", "indices": [250, 9749],
                           "draw": "items sorted by id; each draw is statistics.fmean of n values vals[rng.randrange(n)], one "
                                   "randrange call per element; the 10,000 draws are sorted and read at the two indices",
                           "definition": "definitions.context_probe.item_paired_difference_frozen"}},
            "b - a with the reference checkpoint as b: above 0 = exlr8-k4 scored higher",
            note="Outside the frozen comparison: the reference checkpoint was added after the three-arm results were read. The estimator is the "
                 "frozen rule's (item_paired_difference_frozen), applied post hoc. The eight-turn pass was not run on it."))

        pk = lambda path, pair, key: f"/capture/between_arms/{path}/all/pairs/{esc(pair)}/{key}"
        pairs = list(at(S, "/capture/between_arms/prefill/all/pairs"))
        refp, prbp = [p for p in pairs if REFA in p], [p for p in pairs if REFA not in p]
        km = {p: at(S, pk("prefill", p, "kl_median")) for p in pairs}; td = {p: at(S, pk("prefill", p, "top1_differs")) for p in pairs}
        ab = lambda path, key: f"/capture/against_text/{path}/arms/{REFA}/{key}"
        nd, hv = at(S, ab("prefill", "nll_minus_ref")), at(S, ab("prefill", "nll_difference_rows"))
        t1 = [at(S, ab(path, "top1_minus_ref")) for path in ("prefill", "decode")]
        nrows = at(S, "/capture/against_text/prefill/rows")
        if (min(km[p] for p in refp) <= max(km[p] for p in prbp) or min(td[p] for p in refp) <= max(td[p] for p in prbp) or any(out0(v) for v in t1)
                or hv["median"] != 0 or hv["share_rows_arm_better"] >= 0.5):
            raise SystemExit("findings: the scoring capture's numbers no longer match the answer written for them")
        rng = lambda d, ps, f: f"{f(min(d[p] for p in ps))} to {f(max(d[p] for p in ps))}"
        bf16_line = ("; that distance was measured afterwards for these four configurations, on two reference sets that reach 14.4K "
                     "(CP-bf16-distance, added 2026-11-12)." if "bf16_distance" in json.loads((ROOT / S).read_text()) else
                     " for these four configurations; the repository's BF16-referenced panels (texts to 14.4K tokens) cover other checkpoints.")
        k4 = lambda x: f"{x:.4f}"; pc = lambda x: f"{100 * x:.2f}%"
        out.append(finding(
            "CP-reference-capture",
            "With the engine scoring given texts instead of generating, does the EXLR8 K4 reference checkpoint predict the text worse than the three probe arms, and how far apart are the arms?",
            f"Not measurably worse at predicting the text: over the whole capture the most likely token is the given one as often as for anchor "
            f"({t1[0][0]:+.4f} [{t1[0][1]:+.4f}, {t1[0][2]:+.4f}] on the prefill path; the interval spans 0 on both paths); values by depth band are "
            f"published without intervals. Its mean NLL is lower than anchor's ({nd[0]:+.4f} [{nd[1]:+.4f}, {nd[2]:+.4f}] nats, prefill path), which "
            f"is not read as an improvement: {hv['rows_over_1_nat']} of {nrows:,} positions carry {hv['sum_of_those']:+.2f} of the {hv['sum']:+.2f} nat "
            f"({100 * hv['sum_of_those'] / hv['sum']:.0f}% of the sum), the median per-position difference is 0 and the arm is ahead on fewer than "
            "half of the positions. This capture does not measure distance from the unquantized BF16 model" + bf16_line + " Between arms, which is not a distance from the BF16 "
            f"model: the three probe arms share their experts, so the distance between two of them reflects the settings outside the experts alone, the core and for anchor the output head (prefill path, "
            f"median KL {rng(km, prbp, k4)}, most likely token different on {rng(td, prbp, pc)} of positions); exlr8-k4 has its own experts, so its "
            f"distance to any probe arm ({rng(km, refp, k4)}; {rng(td, refp, pc)}) includes both expert quantizations and does not rank it against "
            f"the probe arms by closeness to the BF16 model. {whole} Basis: one capture per arm, five texts (not the task items), assistant frame; "
            "strength: low (exploratory, one capture, no correction for the number of comparisons).",
            "exploratory", {"name": "share of positions whose most likely token is the given one, exlr8-k4 minus anchor, prefill path",
                            "value": t1[0][0], "ci95": [t1[0][1], t1[0][2]], "ci_over": "runs of consecutive positions within each text",
                            "detected": out0(t1[0])},
            [ev(S, ab("prefill", "top1_minus_ref"), "share with the given token most likely, minus anchor's, prefill path [estimate, 2.5%, 97.5%]"),
             ev(S, ab("decode", "top1_minus_ref"), "the same on the decode path"),
             ev(S, ab("prefill", "nll_minus_ref"), "NLL minus anchor's, prefill path [estimate, 2.5%, 97.5%]"),
             ev(S, ab("prefill", "nll_difference_rows/median"), "median per-position NLL difference from anchor"),
             ev(S, ab("prefill", "nll_difference_rows/share_rows_arm_better"), "share of positions where the arm's NLL is lower"),
             ev(S, ab("prefill", "nll_difference_rows/rows_over_1_nat"), "positions more than 1 nat from anchor"),
             ev(S, ab("prefill", "nll_difference_rows/sum_of_those"), "their summed difference, nats"),
             ev(S, ab("prefill", "nll_difference_rows/sum"), "summed difference over all positions, nats"),
             ev(S, "/capture/against_text/prefill/rows", "positions on the prefill path")] +
            [ev(S, pk("prefill", p, "kl_median"), f"between arms: median KL, {p}, prefill path") for p in pairs] +
            [ev(S, pk("prefill", p, "top1_differs"), f"between arms: share of positions whose most likely token differs, {p}, prefill path") for p in pairs] +
            [ev(f"{CPD}/exploratory/capture_pairs.json", f"/prefill/all/pairs/{esc(refp[0])}/kl_median", "the same median KL in the capture output")],
            CUTEAFD5, CPD, f"{page}#capture", [f"{CPD}/exploratory/capture_pairs.json", f"{CPD}/exploratory/capture_abs.json"],
            direction="KL with the first-named arm as the reference distribution; NLL differences are arm minus anchor (below 0 = the arm predicts the given token better)",
            note="The dumps and per-position files behind these numbers are not published; the scripts in exploratory/ document the computation. "
                 "All four configurations are quantized: anchor has a BF16 core and K4 experts, so a difference from anchor is a difference from "
                 "another quantization. Full tables: section 10 of RESULTS.md in the run folder."))

    if "four_pass" in json.loads((ROOT / S).read_text()):
        REFA, FJ, BJ = "exlr8-k4", f"{CPD}/analysis/FOURPASS.json", f"{CPD}/bf16ref/BF16REF.json"
        whole = at(S, "/reference/whole_checkpoint")
        A4 = CP_ARMS + (REFA,)
        fdata = data + [f"{CPD}/analysis/samples-reference.csv", f"{CPD}/analysis/samples-extension.csv"]
        four = single + ["single-rep2", "single-rep3"]
        def out0(v): return v[1] > 0 or v[2] < 0
        def fp(pair, k="all", ps="p1234", m="score"): return f"/four_pass/paired/{esc(pair)}/{ps}/{m}/{k}"
        def fv(pair, k="all", ps="p1234", m="score"): return at(S, fp(pair, k, ps, m))
        def fres(pair, k="all", ps="p1234"):
            what = f"field score, {pair}, single message, " + ("four lengths" if k == "all" else "127K") + ", " + {"p12": "passes 1-2", "p34": "passes 3-4", "p1234": "four passes"}[ps]
            return res(fp(pair, k, ps), what)
        def rec4(a, b, lengths=("4k", "16k", "64k", "128k"), result=None):
            r = {"kind": "item_paired_difference", "estimator": "frozen", "data": fdata, "a": a, "b": b, "passes": four,
                 "lengths": list(lengths), "script": f"{CPD}/analysis/fourpass.py",
                 "bootstrap": {"draws": 10000, "seed": 5, "unit": "item", "rng": "Python random.Random", "indices": [250, 9749],
                               "definition": "definitions.context_probe.item_paired_difference_frozen"}}
            if result: r["result"] = result
            return r
        def sc4(a, k="all", ps="p1234"): return at(S, f"/four_pass/by_length/{a}/{ps}/{k}/score")
        def rg(vals, f=lambda x: f"{x:.3f}"): return f"{f(min(vals))} to {f(max(vals))}"
        ext_note = ("Extension, not the frozen comparison: amendment 1 (protocol/AMENDMENT-2026-11-11.md) was written after the two-pass results were "
                    "read and before the first request of passes 3 and 4, and fixed the total at four single-message passes per arm. Estimator: "
                    "the frozen rule's (definitions.context_probe.item_paired_difference_frozen) over passes single-rep0 to single-rep3; request "
                    "score = fields correct / fields if the reply finished with stop, else 0; repeats averaged within the item; the item is the "
                    "unit (60); 95% interval from 10,000 item resamples, random.Random(5). anchor is the reference of the probe, not a "
                    "recommendation.")
        IVS = "/four_pass/intervals"
        n102, n6 = at(S, f"{IVS}/per_pass_set"), at(S, f"{IVS}/excluding_zero/p1234/count")
        ha, ca, hc = fv("hqa - anchor"), fv("compact - anchor"), fv("hqa - compact")
        ha12, ha34 = fv("hqa - anchor", ps="p12"), fv("hqa - anchor", ps="p34")
        hc127, ca127 = fv("hqa - compact", "128k"), fv("compact - anchor", "128k")
        ra, rh, rc = (fv(f"{REFA} - {a}") for a in CP_ARMS)
        rc12, rc34, rc127 = fv(f"{REFA} - compact", ps="p12"), fv(f"{REFA} - compact", ps="p34"), fv(f"{REFA} - compact", "128k")
        A7 = at(S, "/four_pass/at_127k"); others = [a for a in A4 if a != "compact"]
        CAPP = "/capture/against_text/prefill/arms/compact"; capn, capt = at(S, f"{CAPP}/nll_minus_ref"), at(S, f"{CAPP}/top1_minus_ref")
        if capn[0] > 0 or out0(capt): raise SystemExit("findings: the scoring capture no longer matches the sentence written for it")
        bp = {a: at(S, f"/four_pass/by_length/{a}/score_by_pass/128k") for a in A4}
        right = {a: at(S, f"/four_pass/by_length/{a}/p1234/all/right") for a in A4}
        if (any(out0(x) for x in (ha, ha12, ha34, ca, ca127, ra, rh, rc, rc34, rc127)) or not out0(hc) or not out0(hc127) or not out0(rc12)
                or out0(fv("hqa - compact", ps="p12")) or out0(fv("hqa - compact", ps="p34"))
                or any(sc4("compact", "all", ps)[0] >= min(sc4(a, "all", ps)[0] for a in others) for ps in ("p12", "p34"))
                or any(fv("compact - anchor", ps=ps)[0] >= 0 or fv("hqa - compact", ps=ps)[0] <= 0 for ps in ("p12", "p34"))
                or any(h <= c for h, c in zip(bp["hqa"], bp["compact"]))
                or [a < c for a, c in zip(bp["anchor"], bp["compact"])] != [True, False, False, False]
                or A7["p12"]["compact"]["unfinished"] != A7["p12"]["anchor"]["unfinished"]
                or A7["p12"]["compact"]["score_finished_only"] >= A7["p12"]["anchor"]["score_finished_only"]
                or max(others + ["compact"], key=lambda a: A7["p34"][a]["score_finished_only"]) != "compact"
                or A7["p34"]["compact"]["unfinished"] <= max(A7["p34"][a]["unfinished"] for a in others)
                or right[REFA] >= min(right["anchor"], right["hqa"]) or (n102, n6) != (102, 6)):
            raise SystemExit("findings: the four-pass numbers no longer match the answers written for them")

        r, e = fres("hqa - anchor")
        e += [ev(S, fp("hqa - anchor", ps="p12"), "the same difference at passes 1-2 (the frozen protocol's result)"),
              ev(S, fp("hqa - anchor", ps="p34"), "the same difference at passes 3-4 alone"),
              ev(S, "/four_pass/requests_per_arm", "requests per arm over four passes"),
              ev(S, "/four_pass/added_passes/errors", "errors in the added passes"),
              ev(FJ, f"/paired/{esc('hqa - anchor')}/p1234/score/all", "the same interval in the analysis output")]
        out.append(finding(
            "CP-fourpass-hqa-vs-anchor",
            "Over four single-message passes, does the default HQA core (BF16 q_b_proj and o_proj, rest K6) score lower than a BF16 core on graded tasks from 4K to 127K tokens?",
            f"No difference measured, and the bound is tighter than at two passes: {iv(ha)} in field score over four lengths (interval includes "
            f"0); the 95% interval reaches down to {s3(ha[1])}. The same reading in both pass sets: {iv(ha12)} at passes 1-2 and "
            f"{iv(ha34)} at passes 3-4 alone. Basis: four passes, 60 items, {at(S, '/four_pass/requests_per_arm')} requests per arm, 0 errors; "
            "strength: the best-supported reading of this run (both pass sets; distance from BF16 not larger on either reference set, "
            "CP-bf16-distance); limits: one model family, one engine release, synthetic tasks.",
            "measurement: extension", r, e, CUTEAFD5, CPD, f"{page}#four-pass", fdata + [FJ], rec4("anchor", "hqa"),
            "above 0 = hqa scored higher than anchor", note=ext_note))

        results, evs = {}, []
        for key, pair, k in (("hqa - compact, 127K", "hqa - compact", "128k"), ("compact - anchor, 127K", "compact - anchor", "128k"),
                             ("hqa - compact, all lengths", "hqa - compact", "all"), ("compact - anchor, all lengths", "compact - anchor", "all")):
            r, e = fres(pair, k); results[key] = r; evs += e
        evs += ([ev(S, f"/four_pass/by_length/{a}/p1234/128k/score", f"{a}: field score at 127K, four passes [estimate, 2.5%, 97.5%, items]") for a in A4] +
                [ev(S, f"/four_pass/by_length/{a}/score_by_pass/128k", f"{a}: field score at 127K in passes 1, 2, 3, 4") for a in ("anchor", "hqa", "compact")] +
                [ev(S, fp(p, "all", ps), f"field score, {p}, four lengths, {lab}") for p in ("hqa - compact", "compact - anchor")
                 for ps, lab in (("p12", "passes 1-2"), ("p34", "passes 3-4"))] +
                [ev(S, f"/four_pass/at_127k/{ps}/{a}/{key}", f"{a} at 127K, {lab}: {what}") for ps, lab in (("p12", "passes 1-2"), ("p34", "passes 3-4"), ("p1234", "four passes"))
                 for a in A4 for key, what in (("unfinished", "unfinished replies"), ("score_finished_only", "field score of finished replies"))] +
                [ev(S, "/four_pass/compact_unfinished_all_lengths", "compact's unfinished replies over all lengths, by finish class"),
                 ev(S, f"{IVS}/per_pass_set", "intervals per pass set"), ev(S, f"{IVS}/excluding_zero/p1234/count", "intervals excluding 0 at four passes"),
                 ev(S, f"{IVS}/excluding_zero/p12/count", "at passes 1-2"), ev(S, f"{IVS}/excluding_zero/p34/count", "at passes 3-4"),
                 ev(S, "/bf16_distance/sets/fidelity_set/last_generated_position", "last generated position of the fidelity set (tokens)"),
                 ev(S, f"{CAPP}/nll_minus_ref", "scoring capture, given texts to 128K: compact's NLL minus anchor's [estimate, 2.5%, 97.5%]"),
                 ev(S, f"{CAPP}/top1_minus_ref", "the same capture: share of positions whose top token is the given one, compact minus anchor")])
        CU = at(S, "/four_pass/compact_unfinished_all_lengths")
        u = lambda ps, arms: ", ".join(str(A7[ps][a]["unfinished"]) for a in arms)
        fo = lambda ps, a: f"{A7[ps][a]['score_finished_only']:.3f}"
        out.append(finding(
            "CP-fourpass-compact-127k",
            "Over four single-message passes, does the K6 core (ATTENTION_MODE=compact) cost accuracy, and where?",
            f"Indicated, not established. compact is the lowest arm in both pass sets (four lengths, four passes: {sc4('compact')[0]:.3f} against "
            f"{rg([sc4(a)[0] for a in others])}), and the gap is at 127K: {sc4('compact', '128k')[0]:.3f} against "
            f"{rg([sc4(a, '128k')[0] for a in others])}; up to 64K it is level with the others. hqa - compact: {iv(hc127)} at 127K and {iv(hc)} over "
            "four lengths (both exclude 0; over four lengths the interval excludes 0 only at four passes, in neither pass set alone). "
            f"compact - anchor: {iv(ca127)} at 127K and {iv(ca)} over four lengths (both include 0), so hqa and compact separate from each other "
            "while neither separates from anchor. Basis of the strength: the same sign in both pass sets and, at 127K, in every pass against hqa "
            f"(hqa {', '.join(f'{x:.3f}' for x in bp['hqa'])}; compact {', '.join(f'{x:.3f}' for x in bp['compact'])}) and in three of four "
            f"against anchor ({', '.join(f'{x:.3f}' for x in bp['anchor'])}; pass 1 reverses); not one interval among "
            f"{n102}, of which {n6} exclude 0 at four passes where about 5 would with no difference anywhere. Where the gap comes from is not "
            f"settled. Pooled over four passes it matches the unfinished replies ({A7['p1234']['compact']['unfinished']} of "
            f"{A7['p1234']['compact']['n']} at 127K against {u('p1234', others)}; finished replies score {fo('p1234', 'compact')} against "
            f"{rg([A7['p1234'][a]['score_finished_only'] for a in others])}), but the two pass sets do not agree on that split: in passes 1-2 "
            f"compact had as many unfinished replies at 127K as anchor ({A7['p12']['compact']['unfinished']} and "
            f"{A7['p12']['anchor']['unfinished']}) and a lower finished-only score ({fo('p12', 'compact')} against {fo('p12', 'anchor')}); in "
            f"passes 3-4 it had {A7['p34']['compact']['unfinished']} unfinished against {u('p34', others)} and the highest finished-only score "
            f"({fo('p34', 'compact')}). Of its {CU['unfinished']} unfinished replies over all lengths, {CU['reply_cap']} reached the reply cap and "
            f"{CU['repetition']} ended on the repetition abort. A scoring capture on given texts to 128K, which samples nothing, shows no "
            f"deficit for compact at predicting text (NLL minus anchor's {capn[0]:+.4f} [{capn[1]:+.4f}, {capn[2]:+.4f}], lower is better; "
            "exploratory, one capture). The capture scores given text and does not locate the gap, which was seen in generated replies at 127K. The 127K length lies beyond the 14.4K reach of both BF16 reference sets, so the "
            "BF16 stage (CP-bf16-distance) neither supports nor contradicts this.",
            "measurement: extension", results, evs, CUTEAFD5, CPD, f"{page}#four-pass", fdata + [FJ],
            rec4("compact", "hqa", ("128k",), "hqa - compact, 127K"),
            "b - a: above 0 = the first-named arm scored higher", note=ext_note))

        results, evs = {}, []
        for a in reversed(CP_ARMS):
            r, e = fres(f"{REFA} - {a}"); results[f"{REFA} - {a}"] = r; evs += e
        evs += [ev(S, fp(f"{REFA} - compact", ps="p12"), "exlr8-k4 - compact at passes 1-2 (the lead published 2026-11-11)"),
                ev(S, fp(f"{REFA} - compact", ps="p34"), "exlr8-k4 - compact at passes 3-4 alone"),
                ev(S, fp(f"{REFA} - compact", "128k"), "exlr8-k4 - compact at 127K, four passes")] + \
               [ev(S, f"/four_pass/by_length/{a}/p1234/all/right", f"{a}: replies with every field right, of 960") for a in A4] + \
               [ev(S, f"/four_pass/ledger_every_field_right_64k_128k/{a}", f"{a}: ledger replies with every field right at 64K and 127K [count, of]") for a in A4]
        LE = at(S, "/four_pass/ledger_every_field_right_64k_128k")
        era, erh = (at(S, fp(f"{REFA} - {a}", m="every_field_right")) for a in ("anchor", "hqa"))
        era_long = at(S, fp(f"{REFA} - anchor", "64k+128k", m="every_field_right"))
        if out0(era) or out0(erh) or not out0(era_long) or era_long[0] > 0:
            raise SystemExit("findings: exlr8-k4's every-field-right intervals no longer match the answer written for them")
        evs += [ev(S, fp(f"{REFA} - {a}", m="every_field_right"), f"exlr8-k4 - {a}: share of replies with every field right, four lengths") for a in ("anchor", "hqa")] + \
               [ev(S, fp(f"{REFA} - anchor", "64k+128k", m="every_field_right"), "exlr8-k4 - anchor: the same share at 64K and 127K pooled")]
        out.append(finding(
            "CP-fourpass-exlr8-k4",
            "Did the two-pass lead of the EXLR8 K4 reference checkpoint over compact repeat, and where does that checkpoint sit over four passes?",
            f"The lead did not repeat. exlr8-k4 - compact was {iv(rc12)} at passes 1-2 (interval excluded 0, post hoc); passes 3-4 alone give "
            f"{iv(rc34)} and the four-pass interval includes 0 ({iv(rc)}). At 127K the four-pass difference is {iv(rc127)}, the same size as "
            f"hqa's over compact ({iv(hc127)}). On score exlr8-k4 sits with anchor and hqa ({iv(ra)} and {iv(rh)}). It has fewer replies fully "
            f"right than those two in count: {right[REFA]} of 960 against {right['anchor']} and {right['hqa']} (compact {right['compact']}). Over "
            f"four lengths those two intervals include 0 ({iv(era)} and {iv(erh)}, as a share of replies); at 64K and 127K pooled the one "
            f"against anchor excludes 0 ({iv(era_long)}), one of the {n6} among {n102}. On ledger at 64K and 127K it has {LE[REFA][0]} of "
            f"{LE[REFA][1]} fully right against {', '.join(str(LE[a][0]) for a in CP_ARMS)} (anchor, hqa, compact). {whole}",
            "measurement: extension", results, evs, CUTEAFD5, CPD, f"{page}#four-pass", fdata + [FJ],
            rec4("compact", REFA, result=f"{REFA} - compact"),
            "b - a with the reference checkpoint as b: above 0 = exlr8-k4 scored higher",
            note=ext_note + " The reference checkpoint was added after the three-arm results were read; every interval with it is post hoc."))

        B = "/bf16_distance"; FS, TPN = f"{B}/sets/fidelity_set", f"{B}/sets/teacher_panel"
        kl = {a: at(S, f"{B}/arms/{a}/fidelity_set/kl") for a in A4}; kt = {a: at(S, f"{B}/arms/{a}/teacher_panel/kl") for a in A4}
        RDG = at(S, f"{B}/reading"); fp8 = at(S, f"{B}/yardsticks/official_fp8_release/fidelity_set_kl")
        k325 = at(S, f"{B}/yardsticks/k3.25_on_cuteafd"); dfs = at(S, f"{B}/differences"); BI = at(S, f"{B}/intervals")
        order = sorted(A4, key=lambda a: kl[a][0]); dha = dfs["hqa - anchor"]; reach = at(S, f"{FS}/last_generated_position")
        pairs_b = list(dfs)
        if (not fp8 < kl[order[0]][0] or not kl[order[-1]][0] < k325["fidelity_set_kl"] or order[0] != "hqa" or order[-1] != REFA
                or not out0(dha["fidelity_set"]["overall"]) or dha["fidelity_set"]["overall"][0] >= 0 or out0(dha["teacher_panel"])
                or RDG["largest_difference_between_probe_arms"] >= 0.003 or any(x["set"] != "fidelity set" for x in BI["excluding_zero"])
                or any(not out0(dfs[f"{REFA} - {a}"]["fidelity_set"]["overall"]) or out0(dfs[f"{REFA} - {a}"]["teacher_panel"]) for a in CP_ARMS)
                or f"{reach / 1000:.1f}K" != "14.4K" or order == sorted(A4, key=lambda a: kt[a][0])):
            raise SystemExit("findings: the BF16-distance numbers no longer match the answer written for them")
        k4 = lambda x: f"{x:.4f}"; s4 = lambda x: f"{x:+.4f}"; iv4 = lambda v: f"{s4(v[0])} [{s4(v[1])}, {s4(v[2])}]"; lv4 = lambda v: f"{k4(v[0])} [{k4(v[1])}, {k4(v[2])}]"
        boot = {"replicates": 5000, "seed": 20260829, "rng": "SplitMix64", "unit": "window", "percentiles": [2.5, 97.5], "interpolation": "linear",
                "draw": "windows sorted by id; each replicate draws one window index per window, with replacement (rejection sampling "
                        "on the 64-bit output, then modulo), and takes sum of window sums / sum of window positions; the same stream "
                        "serves a difference b - a, whose window sum is positions x (mean KL of b - mean KL of a)",
                "definition": "definitions.context_probe.fidelity_set_coarse_kl"}
        out.append(finding(
            "CP-bf16-distance",
            "How far are the four configurations from the unquantized BF16 model, and how much of that distance lies in what differs between the probe arms?",
            "All four sit in one band. Fidelity set (coarse KL from BF16, generated positions, contexts to 14.4K): "
            + ", ".join(f"{a} {lv4(kl[a])}" for a in order) + f"; that is {RDG['times_the_fp8_figure'][0]:.1f} to {RDG['times_the_fp8_figure'][1]:.1f} "
            f"times the baseline the engine author recorded in the fidelity set's manifest for the official FP8 model ({k4(fp8)}; quoted, not recomputed here) and {RDG['share_of_the_k3.25_figure'][0]:.2f} to "
            f"{RDG['share_of_the_k3.25_figure'][1]:.2f} of a K3.25 Core-FP8 checkpoint measured on CuteAFD v3.0.1 on 2026-10-26 "
            f"({k4(k325['fidelity_set_kl'])}; teacher panel {k4(k325['teacher_panel_kl'])}); both are rows from other measurements, for scale. "
            "Teacher panel (full-vocabulary KL, 2K contexts): " + ", ".join(f"{a} {lv4(kt[a])}" for a in A4) + ". The two sets use different "
            "measures and are not comparable with each other. What differs between the three probe arms is a small part of the distance: they share "
            f"their K4 experts and differ by at most {RDG['largest_difference_between_probe_arms']:.4f} on the fidelity set, under a tenth of "
            "the total. The plan stated in advance that anchor's distance would not be zero (quantized experts and the engine's numerics; "
            "the two are not separated here). anchor is also not the closest: hqa - anchor is "
            f"{iv4(dha['fidelity_set']['overall'])} on the fidelity set (interval excludes 0; hqa closer) and {iv4(dha['teacher_panel'])} on "
            "the teacher panel (includes 0). anchor differs from hqa in its output head as well as its core (both BF16 in anchor, which is launched with "
            "the engine's three FP8 conversion settings off; as logged, KDA FP8 reads Off in every serving launch of the three probe arms and the "
            "FP8 prefill setting reads none in anchor and [Mla, Ffn] in hqa and compact) and is a locally derived "
            "checkpoint; why it measures slightly farther than hqa on one set is an open question (added 2026-11-12). exlr8-k4 is "
            f"{RDG['exlr8_k4_farther_than_each_probe_arm'][0]:.3f} to {RDG['exlr8_k4_farther_than_each_probe_arm'][1]:.3f} farther than each "
            "probe arm on the fidelity set (intervals exclude 0) and level with them on the teacher panel. The two sets place it differently "
            "and this stage does not say which is nearer. The fidelity set is the engine author's; its relation to the calibration data of "
            "either checkpoint is not known. The teacher panel is drawn from the corpus the producer of the K4 experts published and can "
            "favour the experts the three probe arms carry (stated in the plan before the first request); a tilt of that kind would run "
            f"toward the probe arms. {whole} {BI['listed']} intervals are listed "
            f"({BI['fidelity_set']} fidelity set, {BI['teacher_panel']} teacher panel), {len(BI['excluding_zero'])} exclude 0, all on the "
            "fidelity set; none was selected. Neither set reaches past 14.4K: the 64K and 127K lengths of the task runs have no BF16 reference "
            "here, so the one task difference indicated in this run (CP-fourpass-compact-127k) lies beyond both sets. Basis: one launch per arm "
            "plus an exact repeat (CP-bf16-repeat), two reference sets. Limits: one engine build, one checkpoint revision per arm, prefill path "
            "only, contexts to 14.4K; descriptive, with no gate and no ranking rule, and the two sets do not order the four configurations "
            "the same way.",
            "measurement: planned descriptive",
            {"name": "KL from the BF16 model, fidelity set, generated positions [estimate, 2.5%, 97.5%] per configuration",
             "value": {a: kl[a][0] for a in A4}, "ci95": {a: kl[a][1:] for a in A4}, "ci_over": "windows",
             "teacher_panel": {a: kt[a] for a in A4},
             "for_scale_not_measured_in_this_stage": {"official_fp8_model_fidelity_set": fp8, "k3.25_on_cuteafd_v3.0.1_fidelity_set": k325["fidelity_set_kl"],
                                                      "k3.25_on_cuteafd_v3.0.1_teacher_panel": k325["teacher_panel_kl"]}},
            [ev(S, f"{B}/arms/{a}/fidelity_set/kl", f"{a}: fidelity set, coarse KL from BF16 [estimate, 2.5%, 97.5%]") for a in A4] +
            [ev(S, f"{B}/arms/{a}/teacher_panel/kl", f"{a}: teacher panel, full-vocabulary KL from BF16 [estimate, 2.5%, 97.5%]") for a in A4] +
            [ev(S, f"{B}/differences/{esc(p)}/fidelity_set/overall", f"{p}: fidelity set, difference in KL [estimate, 2.5%, 97.5%]") for p in pairs_b] +
            [ev(S, f"{B}/differences/{esc(p)}/teacher_panel", f"{p}: teacher panel, difference in KL [estimate, 2.5%, 97.5%]") for p in pairs_b] +
            [ev(S, f"{B}/yardsticks/official_fp8_release/fidelity_set_kl", "official FP8 model: the baseline recorded in the fidelity set's manifest by the engine author; quoted, not recomputed in this repository"),
             ev(S, f"{B}/yardsticks/k3.25_on_cuteafd/fidelity_set_kl", "K3.25 Core-FP8 checkpoint on CuteAFD v3.0.1, fidelity set (2026-10-26 run)"),
             ev(S, f"{B}/yardsticks/k3.25_on_cuteafd/teacher_panel_kl", "the same checkpoint on the teacher panel"),
             ev("results/2026-10-26-cuteafd-vs-vllm/q/pb/pb-C1.json", "/summary/gen/overall/kl", "the K3.25 fidelity-set figure at its source"),
             ev(S, f"{B}/reading", "band, ratios and largest differences as read"), ev(S, f"{B}/intervals/listed", "intervals listed"),
             ev(S, f"{FS}/last_generated_position", "last generated position of the fidelity set (tokens)"),
             ev(S, f"{FS}/generated_positions", "generated positions scored"), ev(S, f"{FS}/windows_with_generated_positions", "windows holding them"),
             ev(S, f"{FS}/estimator", "fidelity-set estimator"), ev(S, f"{TPN}/estimator", "teacher-panel estimator"),
             ev(S, f"{B}/plan/written", "when the plan was written"), ev(f"{CPD}/bf16ref/FROZEN.json", "/sha256/ADDENDUM-BF16REF.md", "sha256 of the plan")] +
            [ev(BJ, f"/arms/{order[0]}/fidelity_set/kl", "the same figure in the stage's published file")],
            CUTEAFD5, CPD, f"{page}#bf16", [BJ, f"{CPD}/bf16ref/ADDENDUM-BF16REF.md"],
            {"kind": "window_ratio_bootstrap", "data": BJ, "windows": "/fidelity_set_windows", "bootstrap": boot,
             "checks": [{"b": a, "pointer": f"/arms/{a}/fidelity_set/kl"} for a in A4] +
                       [{"b": p.split(" - ")[0], "a": p.split(" - ")[1], "pointer": f"/differences/{esc(p)}/fidelity_set/overall"} for p in pairs_b]},
            "KL(BF16 || configuration) in nats: 0 is identical, lower is closer; differences are b - a (below 0 = b is closer to BF16)",
            note="Estimators. Fidelity set: coarse KL by the engine author's rule (not full-vocabulary): per position, KL over the reference's top "
                 "1,024 token ids plus one term for the rest of the vocabulary; statistic = sum of per-position KL / number of generated positions "
                 "(ratio of sums; 15,104 positions in 53 windows); 95% interval from a window bootstrap, 5,000 replicates, SplitMix64 seed "
                 "20260829, linear-interpolation percentiles. Teacher panel: full-vocabulary KL per row in float64, mean over 51,175 rows of 25 "
                 "windows; window bootstrap, 20,000 replicates (numpy generator, so tools/verify.py recomputes the fidelity-set intervals only). "
                 "The stage's plan (bf16ref/ADDENDUM-BF16REF.md) was written before its first request and after the two-pass task results were "
                 "read; it is descriptive, with no gate and no ranking rule. The stage's score files, per-row tables and dumps are not "
                 "published; bf16ref/BF16REF.json carries their numbers and the per-window figures. anchor is the reference of the probe, not "
                 "a recommendation."))

        RP, PC = at(S, f"{B}/repeat/by_arm"), at(S, f"{B}/port_against_cli/by_arm")
        same = {tuple(RP[a]["same_argmax_generated_positions"]) for a in A4}; recs = {tuple(x["records_agreeing"]) for a in A4 for x in PC[a].values()}
        gate = {a: at(S, f"{B}/arms/{a}/fidelity_set/fidelity_gate/pass") for a in A4}
        if (len(same) != 1 or len(recs) != 1 or any(RP[a]["kl_difference"] for a in A4) or any(x["largest_kl_difference"] for a in A4 for x in PC[a].values())
                or len(set(next(iter(same)))) != 1 or len(set(next(iter(recs)))) != 1 or not all(gate.values())):
            raise SystemExit("findings: the BF16 stage's repeat and port check no longer match the answer written for them")
        g, rn = next(iter(same))[0], next(iter(recs))[0]
        out.append(finding(
            "CP-bf16-repeat",
            "Does a second launch reproduce the BF16-distance result, and does the float64 port used for the intervals agree with the engine's own scorer?",
            f"Yes, exactly. A second launch of each of the four configurations gave a KL difference of 0.0 on the fidelity set and the same most "
            f"likely token on {g:,} of {g:,} generated positions. The float64 port agrees with the engine CLI's own per-record output on "
            f"{rn:,} of {rn:,} records per configuration and launch (largest KL difference 0.0). All four pass the engine CLI's own fidelity gate "
            "on the fidelity set (KL at most 0.05, top-1 at least 0.93). The overall fidelity-set values and intervals of CP-bf16-distance are "
            "recomputed by tools/verify.py from the published per-window figures. Limits: one engine build, prefill path only.",
            "measurement: planned descriptive",
            {"name": "generated positions with the same most likely token in the second launch, per configuration", "value": g, "of": g,
             "kl_difference_between_launches": 0.0, "port_records_agreeing": [rn, rn]},
            [ev(S, f"{B}/repeat/by_arm/{a}/same_argmax_generated_positions", f"{a}: positions with the same most likely token, second launch [count, of]") for a in A4] +
            [ev(S, f"{B}/repeat/by_arm/{a}/kl_difference", f"{a}: KL difference between the two launches") for a in A4] +
            [ev(S, f"{B}/port_against_cli/by_arm/{a}/{k}/records_agreeing", f"{a}, launch {k}: records where the port and the CLI agree [count, of]")
             for a in A4 for k in PC[a]] +
            [ev(S, f"{B}/arms/{a}/fidelity_set/fidelity_gate/pass", f"{a}: the engine CLI's fidelity gate") for a in A4],
            CUTEAFD5, CPD, f"{page}#bf16", [BJ]))

        AM = at(S, "/amendment_1"); HW = at(S, "/four_pass/half_width_ratio_four_over_two_passes/paired_score_all")
        if AM["status"] != "complete" or AM["pending"]:
            raise SystemExit("findings: amendment 1 is not complete")
        out.append(finding(
            "CP-extension-pending", "Do two further single-message passes per arm change the reading?",
            f"In part. The passes are complete (ran {AM['ran']}; {at(S, '/four_pass/added_passes/requests'):,} added requests, 0 errors); this entry keeps its id "
            "from the time they were pending. hqa against anchor: unchanged, with a tighter bound (CP-fourpass-hqa-vs-anchor). "
            "compact: a cost at 127K is indicated, not established, and hqa - compact excludes 0 at four passes while neither separates from "
            "anchor (CP-fourpass-compact-127k). The two-pass lead of exlr8-k4 over compact did not repeat (CP-fourpass-exlr8-k4). Paired "
            f"intervals narrowed to {min(HW[f'{b} - {a}'] for a, b in (('anchor', 'hqa'), ('anchor', 'compact'), ('compact', 'hqa'))):.2f} to "
            f"{max(HW[f'{b} - {a}'] for a, b in (('anchor', 'hqa'), ('anchor', 'compact'), ('compact', 'hqa'))):.2f} of their two-pass half-width "
            f"for the three probe pairs and {min(HW[f'{REFA} - {a}'] for a in CP_ARMS):.2f} to {max(HW[f'{REFA} - {a}'] for a in CP_ARMS):.2f} for "
            f"pairs with exlr8-k4. Intervals excluding 0 of {n102} per pass set: {at(S, f'{IVS}/excluding_zero/p12/count')} at passes 1-2, "
            f"{at(S, f'{IVS}/excluding_zero/p34/count')} at passes 3-4 alone, {n6} at four passes; about 5 would with no difference anywhere, and "
            "no correction is applied.",
            "measurement: extension", {"name": "intervals excluding 0 at four passes", "value": n6, "of": n102},
            [ev(S, "/amendment_1/status", "status"), ev(S, "/amendment_1/sha256", "sha256 of the amendment file"),
             ev(S, "/amendment_1/written", "when the amendment was written"), ev(S, "/amendment_1/ran", "when the added passes ran"),
             ev(S, "/amendment_1/pending", "passes pending"), ev(S, "/four_pass/added_passes/requests", "added requests"),
             ev(S, "/four_pass/added_passes/errors", "errors in the added passes"),
             ev(S, "/four_pass/added_passes/seeds_reused_within_an_arm", "seeds reused within an arm"),
             ev(S, f"{IVS}/excluding_zero/p1234/count", "intervals excluding 0 at four passes"), ev(S, f"{IVS}/per_pass_set", "intervals per pass set"),
             ev(S, "/four_pass/half_width_ratio_four_over_two_passes/paired_score_all", "half-width of the four-pass interval over the two-pass one, by pair"),
             {"file": f"{CPD}/protocol/AMENDMENT-2026-11-11.md", "what": "the amendment"}],
            CUTEAFD5, CPD, f"{page}#amendment", fdata + [FJ], note=ext_note))

        lg4 = {ps: at(S, f"/four_pass/paired/{esc('compact - anchor')}/{ps}/{esc('ledger_64k+128k_score')}") for ps in ("p12", "p34", "p1234")}
        rb4, scl4 = at(S, "/trade_offs/resident_weights_mib_back"), at(S, "/launch/kv_pool_tokens_scoring_launches")
        if any(out0(v) for v in lg4.values()) or lg4["p12"][0] > 0 or lg4["p34"][0] < 0 or set(scl4["hqa"] + scl4["compact"]) != {2097152}:
            raise SystemExit("findings: the dated notes on running totals and the KV pool no longer match the numbers")
        TO4 = at(S, "/trade_offs"); wb4, fb4 = TO4["weights_outside_experts_mib_back"], TO4["left_under_memory_cap_mib_back"]
        hd4 = TO4["anchor_to_hqa_parts"]["head_difference_mib"]
        rl4 = TO4["reserve_mib_less_than_anchor"]["hqa"]
        fall4 = {a: round(round(at(S, f"/four_pass/by_length/{a}/p1234/4k/score")[0], 3) - round(at(S, f"/four_pass/by_length/{a}/p1234/128k/score")[0], 3), 3) for a in A4}    # differences of the figures as shown on the page
        if (wb4["anchor_to_hqa"], wb4["hqa_to_compact"], hd4, rl4, TO4["reserve_mib_less_than_anchor"]["compact"]) != (4266, 2568, 756, 49, 49) \
                or not all(0.055 <= fall4[a] <= 0.07 for a in A4 if a != "compact") or not 0.085 <= fall4["compact"] <= 0.1:
            raise SystemExit("findings: the memory figures or the falls with length no longer match the dated notes")
        dated = {
            "CP-hqa-vs-anchor": f"Added 2026-11-12: over four passes the same reading with a tighter bound, {iv(ha)} (CP-fourpass-hqa-vs-anchor). "
                                "This entry stays as the frozen protocol's two-pass result.",
            "CP-compact-vs-anchor": f"Added 2026-11-12: over four passes {iv(ca)} over four lengths and {iv(ca127)} at 127K; both intervals include 0. "
                                    "A cost at 127K is indicated, not established (CP-fourpass-compact-127k). This entry stays as the frozen "
                                    "protocol's two-pass result.",
            "CP-hqa-vs-compact": f"Added 2026-11-12: over four passes the interval excludes 0 ({iv(hc)} over four lengths, {iv(hc127)} at 127K); over "
                                 "four lengths it does so in neither pass set alone, and neither arm separates from anchor "
                                 "(CP-fourpass-compact-127k). This entry stays as the frozen protocol's two-pass result.",
            "CP-reference-exlr8-k4": f"Added 2026-11-12: the lead over compact did not repeat. Passes 3-4 alone give {iv(rc34)} and the four-pass "
                                     f"interval includes 0, {iv(rc)} (CP-fourpass-exlr8-k4).",
            "CP-reference-capture": "Added 2026-11-12: distance from the BF16 model was measured afterwards for the four configurations "
                                    "(CP-bf16-distance).",
            "CP-ledger-long-context": f"Added 2026-11-12: over four passes the lean did not repeat. compact - anchor in ledger field score at 64K "
                                      f"and 127K pooled was {iv(lg4['p12'])} at passes 1-2 (the item-paired estimator of the four-pass analysis; "
                                      f"same data as above, resampled separately), {iv(lg4['p34'])} at passes 3-4 alone and is {iv(lg4['p1234'])} "
                                      f"over four; replies with every field right there, of {LE['anchor'][1]}: "
                                      + ", ".join(f"{a} {LE[a][0]}" for a in CP_ARMS) + ". Every one of these intervals includes 0 "
                                      "(four_pass.paired in SUMMARY.json). This entry stays as the two-pass post hoc reading.",
            "CP-length-effect": "Added 2026-11-12: the arms share the tasks as well, and the tasks' distractor text grows with length; no "
                                "unquantized model and no other engine ran these tasks, so the run does not say where the fall comes from. "
                                f"Over four passes the field score falls from 4K to 127K by {', '.join(f'{a} {fall4[a]:.3f}' for a in A4)}: about "
                                "0.06 in every configuration, and compact's further 0.03 is its 127K gap (CP-fourpass-compact-127k).",
            "CP-kv-pool": f"Added 2026-11-12: the saving in resident weights over both GPUs is {rb4['anchor_to_hqa']:,} MiB from anchor to hqa "
                          f"and a further {rb4['hqa_to_compact']:,} MiB to compact (trade_offs.resident_weights_mib_back in SUMMARY.json). "
                          f"Weights outside the experts account for it: {wb4['anchor_to_hqa']:,} MiB less from anchor to hqa, of which {hd4} MiB is "
                          f"the output head (BF16 in anchor, K6 in hqa and compact; ATTENTION_MODE does not change it), and {wb4['hqa_to_compact']:,} "
                          f"MiB less from hqa to compact. With the same pool in every serving launch, the memory left under the engine's cap rose by "
                          f"{fb4['anchor_to_hqa']:,} MiB and a further {fb4['hqa_to_compact']:,} MiB; hqa and compact hold larger workspaces than "
                          f"anchor and {rl4} MiB less reserve (trade_offs in SUMMARY.json). In the "
                          f"scoring launches, with 16 requests at once, anchor was admitted {scl4['anchor'][0]:,} tokens and hqa and compact "
                          "the maximum: one launch setting read from logs; pool and batch size were not varied as a measurement."}
        for f in out:
            if f["id"] in dated:
                f["note"] = (f["note"] + " " if f.get("note") else "") + dated.pop(f["id"])
        if dated:
            raise SystemExit(f"findings: no entry to carry the dated note for {sorted(dated)}")
    return out


STATUS = {"measurement: frozen rule": "protocol and decision rule frozen (hashes in the run's protocol/FROZEN.json) before the first request",
          "measurement: post hoc": "computed from frozen-run data after the run; not part of any decision rule",
          "measurement: descriptive": "counted from frozen-run data; not part of any decision rule",
          "exploratory": "run kind exploratory: useful evidence, not a frozen comparison",
          "source reading": "read in source code and logs, no measurement",
          "judgement: source and measurements": "a conclusion drawn from source reading and published measurements together; not isolated by a run of its own",
          "measurement: extension": "passes added by a dated amendment, written after the frozen result was read and before the first added request; the frozen rule applied to more passes; not the frozen comparison",
          "measurement: planned descriptive": "plan and file hashes written before the first request of the stage, after earlier results were read; descriptive, with no gate and no decision rule"}


def runs():
    out = []
    for d in sorted((ROOT / "results").iterdir()):
        if (d / "RUN.json").exists():
            r = json.loads((d / "RUN.json").read_text())
            out.append((d.name, r.get("kind"), r.get("title")))
    return out


def llms_txt(fs):
    lines = [
        "# cuteafd-eval",
        "",
        "> Results-first public ledger: two inference engines by tpurtell (CuteAFD and tpurtell's vLLM fork) serving GLM-5.3-Flash EXL3",
        "> quantizations on one machine (2x NVIDIA RTX PRO 6000 Blackwell Max-Q). Maintained by Michael M (UrbanAstroLA).",
        "",
        "Every page is generated from the files in the repository; numbers are never typed into pages. Start with the",
        "machine-readable files below rather than scraping HTML.",
        "",
        "## Machine-readable entry points",
        f"- {SITE_URL}/findings.json: the claims of the Thinking length investigation (TL-*) and of the CuteAFD v5 context probe",
        "  (CP-*), one entry per claim, with status, value,",
        "  95% interval, a JSON pointer into the source file, and the per-reply data and script that recompute it.",
        f"- {REPO_URL}/tree/main/results: one folder per run. In each: RUN.json (id, kind, title, protocol, engine,",
        "  checkpoints), SUMMARY.json (every number its page shows), MANIFEST.json (sha256 of every file), README.md.",
        "- results/*/analysis/samples.csv: one row per reply (arm, prompt, seed, finish, reasoning tokens, decode speed, tests).",
        "  The context probe's table has one row per request (arm, pass, item, family, length, seed, finish class, fields, correct);",
        "  its reference checkpoint's rows are in analysis/samples-reference.csv (same columns), recomputed by analysis/reference.py;",
        "  passes 3 and 4 of all four configurations are in analysis/samples-extension.csv (same columns), recomputed by analysis/fourpass.py.",
        "- results/2026-11-10-context-probe/bf16ref/BF16REF.json: distance from the BF16 model of the four configurations, with the",
        "  per-window figures its fidelity-set values and intervals are recomputed from.",
        f"- {REPO_URL}/blob/main/protocol/README.md: the frozen protocol; protocol/HASHES.json binds published files to it.",
        "",
        "## How to read the results",
        "- Run kinds: measurement (protocol frozen before the first request), exploratory (evidence, not a frozen comparison),",
        "  check. A finding's status says which; post hoc numbers are labelled post hoc.",
        "- Intervals are 95% bootstrap intervals over the unit named (prompts, questions, windows, items); \"detected\" means the interval",
        "  excludes the null (1 for ratios, 0 for differences). Bootstrap seeds differ per run: see each run's protocol, or",
        "  recompute.bootstrap in findings.json.",
        "- \"Finished\" = finish_reason stop and not capped. Medians in TL-* entries are over finished replies; the medians on the v5 page",
        "  (thinking length, speed) are over all replies. findings.json has a definitions block",
        "  with every estimator used.",
        "- findings.json pointers are RFC 6901: unescape ~1 to / and ~0 to ~ after splitting (some keys contain a slash).",
        "- Context probe (CP-*): three arms on CuteAFD v5.0.0 that differ in the precision of the tensors outside the experts: anchor",
        "  (BF16 core and BF16 output head, FP8 conversions off; a locally derived checkpoint; the reference, not a recommendation),",
        "  hqa (BF16 q_b_proj and o_proj, rest of the core and the head K6) and compact (K6 core and head). K4 experts and one seed",
        "  list in every arm. A request scores fields correct / fields, 0 if it did not finish with stop; differences are paired by item",
        "  and named \"b - a\" (above 0 = b higher). Data length label 128k is the 127K-token rendering. The K4-Core-K6-HQA repository",
        "  is no longer available on the hub (checked 2026-11-11); the runs used a local copy.",
        "- Reference checkpoint exlr8-k4 (CP-reference-*): added after the three-arm results were read; two single-message passes and one",
        "  scoring capture, then passes 3 and 4 under amendment 1. It is a different checkpoint from the three arms, not a setting of",
        "  the same one: any difference from an arm is",
        "  a whole-checkpoint difference and is not attributable to one component. Its intervals are post hoc.",
        "- Amendment 1 to the context probe (protocol/AMENDMENT-2026-11-11.md in the run folder) added single-message passes 3 and 4 per",
        "  configuration; complete 2026-11-12 (CP-fourpass-*, CP-extension-pending). It was written after the two-pass results were read and",
        "  before the first added request: the frozen rule applied to four passes, an extension, not the frozen comparison. The two-pass",
        "  entries stay as the frozen protocol's result; the three pair entries and the two reference entries carry a dated note. Pass",
        "  sets: p12 = passes 1-2, p34 = passes 3-4 alone, p1234 = all four. No correction for the number of intervals: one interval is",
        "  not evidence on its own.",
        "- Distance from the BF16 model (CP-bf16-*): the four configurations scored against the unquantized BF16 model on two reference",
        "  sets that reach 14.4K tokens, so the 64K and 127K task lengths have no BF16 reference. Fidelity set: coarse KL (the reference's",
        "  top 1,024 token ids plus the rest), ratio of sums over generated positions, window bootstrap. Teacher panel: full-vocabulary KL,",
        "  mean over rows. The two measures are not comparable with each other. The official FP8 model and K3.25 figures quoted beside",
        "  them come from other measurements and were not measured in that stage.",
        "- Thinking-length ratios put K4-Core-K6, or the part under test, first: above 1 = it thought longer. Each finding states",
        "  its own direction.",
        "- Numbers from different model families or tokenizers are not comparable; NLL is per tokenizer.",
        "- \"BF16 core\" means different things on the two engines: BF16 matrices on the vLLM fork, BF16 converted to FP8 at load on",
        "  CuteAFD v4.0.0. The vLLM fork runs with a local loader modification, not a tpurtell release; derived checkpoints are",
        "  local builds, not producer releases.",
        "",
        "## Validate",
        "- `python3 tools/verify.py` checks every manifest hash, every site link and anchor, every findings.json pointer, and",
        "  recomputes the code-study ratios and test counts and the context-probe differences from the per-reply tables, and the",
        "  context probe's fidelity-set distances from BF16 (values and intervals) from the per-window figures.",
        "- Each run folder's code/ and analysis/ hold the scripts that produced its numbers; repro/REPRODUCE.md covers re-running.",
        "",
        "## Status vocabulary in findings.json",
    ] + [f"- {k}: {v}" for k, v in STATUS.items()] + [
        "",
        "## Findings (summary)",
    ] + [f"- {f['id']} [{f['status']}]: {f['question']} {f['answer']}" for f in fs] + [
        "",
        "## Pages",
    ]
    pages = [("index.html", "overview"), ("checkpoints.html", "K3.25, K4 and K4-Core-K6 against each other"),
             ("thinking.html", "thinking length and the 6-bit core (the investigation findings.json covers)"),
             ("precision.html", "closeness to the BF16 model by context"), ("speed.html", "decode and prefill speed"),
             ("v5.html", "CuteAFD v5.0.0: three core precisions and an EXLR8 K4 reference checkpoint at 4K to 127K over four passes, and their distance from the BF16 model (CP-* in findings.json)"), ("v4.html", "CuteAFD v4.0.0 rerun"), ("tools.html", "multi-turn tool calling"), ("method.html", "method"),
             ("reproduce.html", "how to reproduce"), ("audit.html", "independent audit"), ("ledger.html", "every run")]
    lines += [f"- {SITE_URL}/{p}: {d}" for p, d in pages if (ROOT / "docs" / p).exists()]
    lines += ["", "## Runs (results/<id>/RUN.json)"] + [f"- {i} ({k}): {t}" for i, k, t in runs()]
    lines += ["", "## Not published", "Model output text (replies, reasoning), benchmark question text, and raw dumps.", ""]
    return "\n".join(lines)


def main():
    fs = findings()
    doc = {"about": "Claims of the Thinking length investigation (TL-*) and of the CuteAFD v5 context probe (CP-*), generated from the results by tools/build_findings.py. Each evidence "
                    "entry names a repository file and an RFC 6901 JSON pointer; 'value' is what the pointer resolved to at build time. "
                    "tools/verify.py re-resolves every pointer and recomputes entries that carry 'recompute' from the per-reply tables (CP-bf16-distance: from the per-window figures).",
           "repository": REPO_URL, "site": SITE_URL, "status_vocabulary": STATUS,
           "conventions": {"interval": "95% bootstrap over the unit in ci_over (percentile); 4,000 draws for TL-* entries, 10,000 for CP-* entries; TL-* seeds are in each run's protocol; CP-* entries use seed 5 with percentile indices 250 and 9749 (frozen rule), and seed 7 or 20261111 with indices 250 and 9750 (post hoc and by-family readings), stated per entry in recompute.bootstrap and in analysis/posthoc.py; CP-bf16-* entries use window bootstraps (fidelity set: 5,000 replicates, SplitMix64 seed 20260829, linear-interpolation percentiles; teacher panel: 20,000 replicates, numpy generator seed 20260929)",
                           "detected": "interval excludes the null (1 for ratios, 0 for differences)",
                           "paths": "relative to the repository root",
                           "pointers": "RFC 6901: split on '/', then replace '~1' with '/' and '~0' with '~' (keys such as 'C-K6x/V-BF16' contain a slash)"},
           "definitions": {
               "finished": "finish_reason == 'stop' and hit_cap == False (a reply that ended on its own under the 130,048-token cap)",
               "reasoning_tokens": "tokens of the reasoning text, by re-tokenizing it with the model's tokenizer",
               "seed_paired_ratio": "for each (prompt, rep) where both arms finished: log(reasoning tokens A / B); ratio = exp(mean over all "
                                    "such pairs); interval: bootstrap over prompts (resample prompts with replacement, pool their pairs)",
               "bootstrap_draws": "rng = random.Random(seed); each draw: rng.choice(sorted prompt list) repeated once per prompt, mean of the "
                                  "pooled log ratios; sort the 4,000 draw means; interval = exp of values at indices 100 and 3899",
               "cross_engine_ratio": "post hoc: for each (prompt, rep) where both finished: log(A / B); mean within each prompt; mean over "
                                     "prompts; exp. Each prompt weighs the same, so a same-engine contrast differs slightly from seed_paired_ratio",
               "pass_pairs": "post hoc: for each (prompt, rep) where both arms finished: all_tests_pass A minus B (1, 0 or -1); mean over "
                             "the pairs; interval: bootstrap over prompts as bootstrap_draws, on the pooled differences (seed 20261108)",
               "engine_comparison": "vLLM ratio / CuteAFD ratio = exp(mean over prompts of [vLLM prompt log ratio - CuteAFD prompt log ratio])",
               "median_reasoning_tokens": "median over finished replies",
               "context_probe": {
                   "applies_to": "CP-* entries (results/2026-11-10-context-probe); the definitions above apply to TL-* entries",
                   "rows_used": "analysis/samples.csv rows with final == 1 and status == ok (one per request; delivery turns of the eight-turn pass have final == 0); "
                                "for the reference checkpoint, the same rows of analysis/samples-reference.csv beside them; for passes 3 and 4 (CP-fourpass-*), the same rows of analysis/samples-extension.csv beside both",
                   "request_score": "correct / fields if finish_class == 'stop' and fields > 0, else 0 (a reply that hit the cap or was ended by the loop abort scores 0)",
                   "every_field_right": "request_score == 1",
                   "item_paired_difference_frozen": "for each item, over the (pass, length) cells in recompute.passes x recompute.lengths where both arms have a row: "
                                                    "request_score(b) - request_score(a); mean within the item (statistics.fmean); estimate = mean over items, rounded to 4 places. "
                                                    "Interval: items in sorted order, rng = random.Random(5); 10,000 draws, each the fmean of n values vals[rng.randrange(n)]; "
                                                    "sorted draws at indices 250 and 9749",
                   "item_paired_difference_pooled": "post hoc: items of recompute.family (all items if absent), sorted; per item and arm, the mean over passes x lengths of "
                                                    "request_score (or of every_field_right when strict); d = b - a per item; estimate = sum(d) / n. Interval: "
                                                    "rng = random.Random(seed); 10,000 draws, each sum of n values d[rng.randrange(n)] / n; sorted draws at indices 250 and 9750",
                   "sign": "'b - a': above 0 = arm b scored higher",
                   "lengths": {"4k": "4K tokens", "16k": "16K", "64k": "64K", "128k": "127K (the 128k label is the 127K-token rendering)"},
                   "passes": {"single-rep0": "single message, pass 1", "single-rep1": "single message, pass 2 (distinct seeds)", "single-rep2": "single message, pass 3 (amendment 1; new seed block)", "single-rep3": "single message, pass 4 (amendment 1; new seed block)", "turns-p8-rep0": "the same records delivered over eight turns, then the question"},
                   "arms": {"anchor": "BF16 core and BF16 output head, FP8 conversions off; locally derived checkpoint, not a producer release; the reference, not a recommendation",
                            "hqa": "K4-Core-K6-HQA checkpoint, default mode: BF16 q_b_proj (12 matrices) and o_proj (46), rest of the core and the output head K6",
                            "compact": "the same checkpoint with ATTENTION_MODE=compact: K6 core and output head"},
                   "reference_checkpoint": {"exlr8-k4": "native EXLR8 K4 checkpoint (revision in the run's RUN.json), added after the three-arm results were read; two "
                                                        "single-message passes, then passes 3 and 4 under amendment 1; no eight-turn pass. A different checkpoint from the three arms, not a setting of the same "
                                                        "one: a difference from an arm is a whole-checkpoint difference, not attributable to one component"},
                   "amendment_1": "protocol/AMENDMENT-2026-11-11.md adds single-message passes 3 and 4 per configuration (single-rep2, single-rep3), written after the two-pass results were read and before the first added request; complete 2026-11-12; the frozen rule (item_paired_difference_frozen) over four passes, reported as an extension beside the frozen two-pass result",
                   "pass_sets": {"p12": "passes 1-2 (the frozen protocol's result)", "p34": "passes 3-4 alone", "p1234": "all four passes"},
                   "fidelity_set_coarse_kl": "CP-bf16-* entries, fidelity set (the engine author's published set; 64 windows, 512 scored positions each, 15,104 generated positions in 53 windows, contexts to 14.4K): per position, KL(BF16 reference || configuration) in float64 over the reference's top 1,024 token ids plus one term for the rest of the vocabulary (coarse, not full-vocabulary). Statistic: sum of per-position KL over generated positions / number of generated positions (ratio of sums). Interval: window bootstrap, 5,000 replicates, SplitMix64 seed 20260829; windows in sorted order, one window drawn per window with replacement in each replicate; 2.5th and 97.5th percentiles with linear interpolation. A difference b - a uses the same rows and the same stream. Unit: the window",
                   "teacher_panel_kl": "CP-bf16-* entries, teacher panel (published BF16 teacher logits; 25 windows of 2,048 tokens, 51,175 scored rows, 2K contexts): full-vocabulary KL(BF16 teacher || configuration) per row in float64, mean over rows. Interval: window bootstrap, 20,000 replicates, numpy default_rng(20260929), percentile. Unit: the window. Not comparable with fidelity_set_coarse_kl (different measure, different texts)",
                   "bf16_yardsticks": "the official FP8 model figure (the baseline the engine author recorded in the fidelity set's manifest; quoted, not recomputed in this repository) and the K3.25 Core-FP8 figures (CuteAFD v3.0.1, run 2026-10-26-cuteafd-vs-vllm) are rows from other measurements, quoted for scale on the same sets and measures; neither was measured in the BF16 stage of the context probe",
                   "checkpoint_availability": "the K4-Core-K6-HQA repository is no longer available on the hub (checked 2026-11-11); the runs used a local copy downloaded on 2026-11-10"},
               "arms": {"C-K6": "CuteAFD, native 6-bit core", "C-K6x": "CuteAFD, BF16 core converted to FP8 at load (with FP8 KDA projections, head, prefill activations)",
                        "V-K6": "vLLM fork, 6-bit core rebuilt to BF16 at load", "V-BF16": "vLLM fork, original BF16 core",
                        "F-kda": "C-K6x's config with KDA projections in BF16 (and KDA output sharding off)", "F-head": "F-kda plus the vocabulary head in BF16",
                        "F-pre": "F-head plus prefill activations unquantized"}},
           "findings": fs}
    (ROOT / "docs" / "findings.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "docs" / "llms.txt").write_text(llms_txt(fs))
    print(f"wrote docs/findings.json ({len(fs)} findings), docs/llms.txt")


if __name__ == "__main__":
    main()
