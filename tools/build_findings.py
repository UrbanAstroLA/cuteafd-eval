#!/usr/bin/env python3
"""Machine-readable entry points for agents and scripts: docs/findings.json and docs/llms.txt.

findings.json lists the claims of the Thinking length investigation, one entry per claim: the question, the answer as
the page states it, its status (frozen measurement, post hoc, exploratory, source reading, in progress), the value with
its interval, and where it comes from: a file and a JSON pointer (RFC 6901) into it, plus the per-reply data and the
script that recompute it. Every value is read from the results at build time, never typed here. tools/verify.py
re-resolves every pointer and recomputes the code-study ratios from the published per-reply tables.

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
        "No measurable change in replies passing all hidden tests on either engine.", "measurement: descriptive",
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
        "with FP8 KDA and clears for the native core.", "source reading",
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
    return out


STATUS = {"measurement: frozen rule": "protocol and decision rule frozen (hashes in the run's protocol/FROZEN.json) before the first request",
          "measurement: post hoc": "computed from frozen-run data after the run; not part of any decision rule",
          "measurement: descriptive": "counted from frozen-run data; not part of any decision rule",
          "exploratory": "run kind exploratory: useful evidence, not a frozen comparison",
          "source reading": "read in source code and logs, no measurement",
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
        f"- {SITE_URL}/findings.json: the Thinking length investigation's claims, one entry per claim, with status, value,",
        "  95% interval, a JSON pointer into the source file, and the per-reply data and script that recompute it.",
        f"- {REPO_URL}/tree/main/results: one folder per run. In each: RUN.json (id, kind, title, protocol, engine,",
        "  checkpoints), SUMMARY.json (every number its page shows), MANIFEST.json (sha256 of every file), README.md.",
        "- results/*/analysis/samples.csv: one row per reply (arm, prompt, seed, finish, reasoning tokens, decode speed, tests).",
        f"- {REPO_URL}/blob/main/protocol/README.md: the frozen protocol; protocol/HASHES.json binds published files to it.",
        "",
        "## How to read the results",
        "- Run kinds: measurement (protocol frozen before the first request), exploratory (evidence, not a frozen comparison),",
        "  check. A finding's status says which; post hoc numbers are labelled post hoc.",
        "- Intervals are 95% bootstrap intervals over the unit named (prompts, questions, windows); \"detected\" means the interval",
        "  excludes the null (1 for ratios, 0 for differences). Bootstrap seeds differ per run: see each run's protocol, or",
        "  recompute.bootstrap in findings.json.",
        "- \"Finished\" = finish_reason stop and not capped. Medians are over finished replies. findings.json has a definitions block",
        "  with every estimator used.",
        "- findings.json pointers are RFC 6901: unescape ~1 to / and ~0 to ~ after splitting (some keys contain a slash).",
        "- Thinking-length ratios put K4-Core-K6, or the part under test, first: above 1 = it thought longer. Each finding states",
        "  its own direction.",
        "- Numbers from different model families or tokenizers are not comparable; NLL is per tokenizer.",
        "- \"BF16 core\" means different things on the two engines: BF16 matrices on the vLLM fork, BF16 converted to FP8 at load on",
        "  CuteAFD v4.0.0. The vLLM fork runs with a local loader modification, not a tpurtell release; derived checkpoints are",
        "  local builds, not producer releases.",
        "",
        "## Validate",
        "- `python3 tools/verify.py` checks every manifest hash, every site link and anchor, every findings.json pointer, and",
        "  recomputes the code-study ratios and test counts from the per-reply tables.",
        "- Each run folder's code/ and analysis/ hold the scripts that produced its numbers; repro/REPRODUCE.md covers re-running.",
        "",
        "## Status vocabulary in findings.json",
    ] + [f"- {k}: {v}" for k, v in STATUS.items()] + [
        "",
        "## Thinking length findings (summary)",
    ] + [f"- {f['id']} [{f['status']}]: {f['question']} {f['answer']}" for f in fs] + [
        "",
        "## Pages",
    ]
    pages = [("index.html", "overview"), ("checkpoints.html", "K3.25, K4 and K4-Core-K6 against each other"),
             ("thinking.html", "thinking length and the 6-bit core (the investigation findings.json covers)"),
             ("precision.html", "closeness to the BF16 model by context"), ("speed.html", "decode and prefill speed"),
             ("v4.html", "CuteAFD v4.0.0 rerun"), ("tools.html", "multi-turn tool calling"), ("method.html", "method"),
             ("reproduce.html", "how to reproduce"), ("audit.html", "independent audit"), ("ledger.html", "every run")]
    lines += [f"- {SITE_URL}/{p}: {d}" for p, d in pages if (ROOT / "docs" / p).exists()]
    lines += ["", "## Runs (results/<id>/RUN.json)"] + [f"- {i} ({k}): {t}" for i, k, t in runs()]
    lines += ["", "## Not published", "Model output text (replies, reasoning), benchmark question text, and raw dumps.", ""]
    return "\n".join(lines)


def main():
    fs = findings()
    doc = {"about": "Claims of the Thinking length investigation, generated from the results by tools/build_findings.py. Each evidence "
                    "entry names a repository file and an RFC 6901 JSON pointer; 'value' is what the pointer resolved to at build time. "
                    "tools/verify.py re-resolves every pointer and recomputes entries that carry 'recompute' from the per-reply tables.",
           "repository": REPO_URL, "site": SITE_URL, "status_vocabulary": STATUS,
           "conventions": {"interval": "95% bootstrap over the unit in ci_over (percentile), 4,000 draws; each run's seed is in its protocol and in recompute.bootstrap",
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
               "engine_comparison": "vLLM ratio / CuteAFD ratio = exp(mean over prompts of [vLLM prompt log ratio - CuteAFD prompt log ratio])",
               "median_reasoning_tokens": "median over finished replies",
               "arms": {"C-K6": "CuteAFD, native 6-bit core", "C-K6x": "CuteAFD, BF16 core converted to FP8 at load (with FP8 KDA projections, head, prefill activations)",
                        "V-K6": "vLLM fork, 6-bit core rebuilt to BF16 at load", "V-BF16": "vLLM fork, original BF16 core"}},
           "findings": fs}
    (ROOT / "docs" / "findings.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "docs" / "llms.txt").write_text(llms_txt(fs))
    print(f"wrote docs/findings.json ({len(fs)} findings), docs/llms.txt")


if __name__ == "__main__":
    main()
