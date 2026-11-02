# Tool calling, CuteAFD v4.0.0 vs tpurtell's vLLM fork v0.9.2 (2026-11-02)

Goal: close the two gaps listed for cuteafd-eval: multi-turn tool calling between engines, and stability over a long
serving period. Results go to cuteafd-eval as `results/2026-11-xx-tool-soak` (measurement) once frozen and run.
Setup as the v4 run: 2x RTX PRO 6000 Max-Q (300 W), GPU only, experts local, no Sparks; thinking on.

## Discovery (zero GPU, done 2026-11-02)

| Item | Finding [V] |
|---|---|
| CuteAFD tool support | GLM XML tool calls parsed into OpenAI chunks (`cuteafd-api/src/openai/chat/glm5/parser.rs`); tpurtell vendors tool-eval-bench in v4 (`third_party/`, rev 5df1e9e0, 2026-07-31) |
| Harness | ours `<tool-eval-bench>` cf54b4b (2026-09-05; 106 commits newer than tpurtell's pin) = local-inference-evals protocol tool-eval-bench/v1. Use cf54b4b: comparable with the published v0.9.0 runs |
| Multi-turn rendering | harness returns `reasoning_content` on assistant turns with tool calls. K4's template drops past-turn reasoning unless `clear_thinking` is false; the zai template the vLLM fork uses keeps it by default (`clear_thinking` defaults false). CuteAFD renders the checkpoint's own template. K3.25-Core-FP8's template = zai (0c4099f3); K4-Core-K6's differs (2614a3c8, to check) |
| Equal inputs | send `--backend-kwargs '{"chat_template_kwargs":{"clear_thinking":false}}'` on every arm; both templates then keep reasoning in history. Gate: per-request `usage.prompt_tokens` equal across engines on the first request of each scenario, and a rendered-prompt hash check on 3 multi-turn scenarios before the frozen run |
| Prior result | vLLM fork v0.9.0, K3.25: 157/176 both repeats; ten scenarios flip between repeats at temperature 0 |

## Block TC: tool calling

- tool-eval-bench cf54b4b, all 88 scenarios, protocol v1 settings (temperature 0, thinking on, 8 in parallel, max 8
  turns, 900 s timeout, reference date 2026-09-04), plus the `clear_thinking` kwarg above.
- Arms, in this order: V-K3.25 (v1 build), C-K3.25 (Core-FP8), C-K4, C-K6, V-K4; then vLLM K3.25 serving restored.
  Three repeats per arm on one server launch, `--seed` 1001, 1002, 1003 (same seeds on every arm, recorded).
- Gate R (CPU, passed before freeze): `drivers/render_gate.py`: with the kwarg, K4, zai and K4-Core-K6 templates render
  byte-identical text on three tool conversations (without it, K4 differs on the follow-up case).
- Gate R2 (live, each arm before its repeats): the three gate conversations sent with `max_tokens` 1 and the kwarg;
  `usage.prompt_tokens` recorded. Pass: equal across all five arms per conversation (one tokenizer). A failing arm is
  run and reported with the difference stated, not dropped.
- Command per repeat: `tool-eval-bench --base-url http://127.0.0.1:8001/v1 --temperature 0 --max-turns 8 --timeout 900
  --parallel 8 --hardmode --reference-date 2026-09-04 --seed <s> --backend-kwargs '{"chat_template_kwargs":{"clear_thinking":false}}'
  --json-file tc/<arm>-r<n>.json`.
- Per row: scenario, status, points (as v1). Summary per repeat: points of 176, pass/partial/fail.
- Reading rule: descriptive. A scenario differs between engines only if its status differs in all three repeats
  pairwise (vLLM repeats are known to flip); totals reported with the per-repeat range, no significance claim.

## Block S: soak

Not run (decision 2026-11-02: tool calling only). Stated as a gap in cuteafd-eval.

## Cost and order

About 3 h: five launches and 15 runs of about 10 min; vLLM serving paused, restored at the end and on every exit path. Long jobs via
`systemd-run --user`. Protocol frozen (sha256) before the first measured request.

## Amendment 1 (2026-11-02 11:58, before any result was read)

The first start (frozen 11:42) omitted `--hardmode`; at cf54b4b the harness then runs 69 scenarios, not the 88 of
protocol v1 (the 19 Hard Mode scenarios, category P, need the flag; the published v0.9.0 runs list all 88). Stopped
after 10 minutes of the first repeat on V-K3.25; its partial outputs are kept in `aborted-69/`, unscored and unused.
Command amended to add `--hardmode`; re-frozen; restarted from the first arm.
