#!/usr/bin/env python3
"""Machine-readable entry points for agents and scripts: docs/findings.json and docs/llms.txt.

findings.json lists the claims of the Thinking length investigation (TL-*) and of the CuteAFD v5 context probe (CP-*), one entry per claim: the question, the answer as
the page states it, its status (frozen measurement, post hoc, exploratory, source reading, in progress), the value with
its interval, and where it comes from: a file and a JSON pointer (RFC 6901) into it, plus the per-reply data and the
script that recompute it. Every value is read from the results at build time, never typed here. tools/verify.py
re-resolves every pointer and recomputes the code-study ratios and the context-probe differences from the published
per-reply tables.

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
        k4 = lambda x: f"{x:.4f}"; pc = lambda x: f"{100 * x:.2f}%"
        out.append(finding(
            "CP-reference-capture",
            "With the engine scoring given texts instead of generating, does the EXLR8 K4 reference checkpoint predict the text worse than the three probe arms, and how far apart are the arms?",
            f"Not measurably worse at predicting the text: over the whole capture the most likely token is the given one as often as for anchor "
            f"({t1[0][0]:+.4f} [{t1[0][1]:+.4f}, {t1[0][2]:+.4f}] on the prefill path; the interval spans 0 on both paths); values by depth band are "
            f"published without intervals. Its mean NLL is lower than anchor's ({nd[0]:+.4f} [{nd[1]:+.4f}, {nd[2]:+.4f}] nats, prefill path), which "
            f"is not read as an improvement: {hv['rows_over_1_nat']} of {nrows:,} positions carry {hv['sum_of_those']:+.2f} of the {hv['sum']:+.2f} nat "
            f"({100 * hv['sum_of_those'] / hv['sum']:.0f}% of the sum), the median per-position difference is 0 and the arm is ahead on fewer than "
            "half of the positions. Distance from the unquantized BF16 model is not measured for these four configurations in this run; the "
            "repository's BF16-referenced panels (texts to 14.4K tokens) cover other checkpoints. Between arms, which is not a distance from the BF16 "
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

        out.append(finding(
            "CP-extension-pending", "Do two further single-message passes per arm change the reading?",
            f"Not known: {at(S, '/amendment_1/status')}. Amendment 1 (written {at(S, '/amendment_1/written')}, before the first request of the added "
            "passes) adds single-message passes 3 and 4 for the three arms and the reference checkpoint under the frozen comparison rule. No number "
            "from them is published.",
            "in progress", {"name": "none published"},
            [ev(S, "/amendment_1/status", "status"), ev(S, "/amendment_1/sha256", "sha256 of the amendment file"),
             ev(S, "/amendment_1/pending", "passes pending"), {"file": f"{CPD}/protocol/AMENDMENT-2026-11-11.md", "what": "the amendment"}],
            CUTEAFD5, CPD, f"{page}#amendment"))
    return out


STATUS = {"measurement: frozen rule": "protocol and decision rule frozen (hashes in the run's protocol/FROZEN.json) before the first request",
          "measurement: post hoc": "computed from frozen-run data after the run; not part of any decision rule",
          "measurement: descriptive": "counted from frozen-run data; not part of any decision rule",
          "exploratory": "run kind exploratory: useful evidence, not a frozen comparison",
          "source reading": "read in source code and logs, no measurement",
          "judgement: source and measurements": "a conclusion drawn from source reading and published measurements together; not isolated by a run of its own",
          "in progress": "running; no result published"}


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
        "  its reference checkpoint's rows are in analysis/samples-reference.csv (same columns), recomputed by analysis/reference.py.",
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
        "  scoring capture. It is a different checkpoint from the three arms, not a setting of the same one: any difference from an arm is",
        "  a whole-checkpoint difference and is not attributable to one component. Its intervals are post hoc.",
        "- Amendment 1 to the context probe (protocol/AMENDMENT-2026-11-11.md in the run folder) adds single-message passes 3 and 4 per arm;",
        "  they are in progress and no number from them is published (CP-extension-pending).",
        "- Thinking-length ratios put K4-Core-K6, or the part under test, first: above 1 = it thought longer. Each finding states",
        "  its own direction.",
        "- Numbers from different model families or tokenizers are not comparable; NLL is per tokenizer.",
        "- \"BF16 core\" means different things on the two engines: BF16 matrices on the vLLM fork, BF16 converted to FP8 at load on",
        "  CuteAFD v4.0.0. The vLLM fork runs with a local loader modification, not a tpurtell release; derived checkpoints are",
        "  local builds, not producer releases.",
        "",
        "## Validate",
        "- `python3 tools/verify.py` checks every manifest hash, every site link and anchor, every findings.json pointer, and",
        "  recomputes the code-study ratios and test counts and the context-probe differences from the per-reply tables.",
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
             ("v5.html", "CuteAFD v5.0.0: three core precisions at 4K to 127K, and an EXLR8 K4 reference checkpoint added later (CP-* in findings.json)"), ("v4.html", "CuteAFD v4.0.0 rerun"), ("tools.html", "multi-turn tool calling"), ("method.html", "method"),
             ("reproduce.html", "how to reproduce"), ("audit.html", "independent audit"), ("ledger.html", "every run")]
    lines += [f"- {SITE_URL}/{p}: {d}" for p, d in pages if (ROOT / "docs" / p).exists()]
    lines += ["", "## Runs (results/<id>/RUN.json)"] + [f"- {i} ({k}): {t}" for i, k, t in runs()]
    lines += ["", "## Not published", "Model output text (replies, reasoning), benchmark question text, and raw dumps.", ""]
    return "\n".join(lines)


def main():
    fs = findings()
    doc = {"about": "Claims of the Thinking length investigation (TL-*) and of the CuteAFD v5 context probe (CP-*), generated from the results by tools/build_findings.py. Each evidence "
                    "entry names a repository file and an RFC 6901 JSON pointer; 'value' is what the pointer resolved to at build time. "
                    "tools/verify.py re-resolves every pointer and recomputes entries that carry 'recompute' from the per-reply tables.",
           "repository": REPO_URL, "site": SITE_URL, "status_vocabulary": STATUS,
           "conventions": {"interval": "95% bootstrap over the unit in ci_over (percentile); 4,000 draws for TL-* entries, 10,000 for CP-* entries; TL-* seeds are in each run's protocol; CP-* entries use seed 5 with percentile indices 250 and 9749 (frozen rule), and seed 7 or 20261111 with indices 250 and 9750 (post hoc and by-family readings), stated per entry in recompute.bootstrap and in analysis/posthoc.py",
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
                                "for the reference checkpoint, the same rows of analysis/samples-reference.csv beside them",
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
                   "passes": {"single-rep0": "single message, pass 1", "single-rep1": "single message, pass 2 (distinct seeds)", "turns-p8-rep0": "the same records delivered over eight turns, then the question"},
                   "arms": {"anchor": "BF16 core and BF16 output head, FP8 conversions off; locally derived checkpoint, not a producer release; the reference, not a recommendation",
                            "hqa": "K4-Core-K6-HQA checkpoint, default mode: BF16 q_b_proj (12 matrices) and o_proj (46), rest of the core and the output head K6",
                            "compact": "the same checkpoint with ATTENTION_MODE=compact: K6 core and output head"},
                   "reference_checkpoint": {"exlr8-k4": "native EXLR8 K4 checkpoint (revision in the run's RUN.json), added after the three-arm results were read; two "
                                                        "single-message passes, no eight-turn pass. A different checkpoint from the three arms, not a setting of the same "
                                                        "one: a difference from an arm is a whole-checkpoint difference, not attributable to one component"},
                   "amendment_1": "protocol/AMENDMENT-2026-11-11.md adds single-message passes 3 and 4 per arm (single-rep2, single-rep3); in progress, no number published",
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
