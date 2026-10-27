# Stage 0 prompt set: Blocks Q2, T and L (CuteAFD v3.0.1 vs vLLM v0.9.2)

Built 2026-10-26, CPU only. No GPU was used, no request reached either engine, and no container was started or
stopped other than throwaway `--network none` tool containers. Nothing was downloaded. Every choice below is a
fixed rule with a fixed seed: the full rule text is in `RULES.json`, and all hashes are in `MANIFEST.json`.
The drivers that use these prompts are in `../drivers/`.

## Layout

```
RULES.json            every rule, seed and constant; source hashes; what was selected
MANIFEST.json         SHA256 of every file here and in ../drivers, plus rules and seeds (frozen with the protocol)
nonce_groups.json     the 177 three-digit strings that are one token each (nonce alphabet)
authored/             wrappers.json (prompt wrappers, nonce rule), json_task.json (schema, variants)
q2/                   18 windows + index.json
T/<content>/<len>/pN.json   48 Block T prompts + T/index.json
L/<content>/pN.json   16 Block L prompts + L/index.json
L/code/<project>/     SPEC.md (in the prompt), tests/ (hidden suite), reference/ (proves the suite passes)
checkers/             math_check.py, json_check.py, code_check.py, selftest.py
selftest/             checkers_selftest.json
build/                build_prompts.py, run_build.sh, make_manifest.py
```

## How it was built

```bash
cd <run>/stage0
./prompts/build/run_build.sh <scratch dir>     # about 11 minutes, CPU only
python3 prompts/checkers/selftest.py            # checker self-test (docker pytest sandbox)
python3 prompts/build/make_manifest.py          # MANIFEST.json
```

`run_build.sh` does two things:
- It copies `vllm/**/*.py` out of the vLLM image `ea0430aa`, using `tar` in a `--network none` container.
- It runs `build_prompts.py` in the CuteAFD image `392db7c0`, with no network and no GPU. That image has
  `tokenizers` 0.22.2, `pyarrow` and `jinja2`; the host has none of them.

Inputs are mounted read-only. Each dataset file is checked against `SOURCES.json` before use. The build is
deterministic: re-running it gives the same files.

**Tokenizer.** K3.25-v1 `tokenizer.json` (snapshot `0490d2f7`), with `add_special_tokens=False`.

**Chat template.**
- The checkpoint's `chat_template.jinja` is byte-identical to the vLLM image's
  `glm53-zai-a5b45eb.jinja`.
- For one user message it renders `[gMASK]<sop><|system|>Reasoning Effort: Max<|user|>` + content +
  `<|assistant|><think>`. The build checks this with jinja2.
- Recorded `prompt_tokens` count that text, including the nonce line.
- CuteAFD adds one `</think>` token when thinking is off (see the section below).

## Q2 windows (`q2/`)

Each file is `{window_id, kind, length, tokens, rows, source, tokenization}`.

**Shape of a window.**
- Raw text, no chat template, no BOS.
- `tokens` = the first L ids of the document's tokenization, so a document's 32K window is a prefix of its
  64K window, which is a prefix of its 128K window.
- `rows` = the last 4,096 row indices L−4,096 … L−1. Row p is scored on predicting token p, having seen
  tokens 0 … p−1, which is the P-B convention.

**Prose.**
- The first 3 books in `pg19/SELECTION.json` order.
- CRLF is converted to LF.
- Front matter is skipped: drop the first 16,384 characters, then up to the next blank line.

**Code.**
- Eligible files: `.py` files under `vllm/` in image `ea0430aa` that have an
  `SPDX-License-Identifier: Apache-2.0` line in their first 5 lines and are at least 2,048 bytes. There are
  1,773 such files.
- Their sorted list is shuffled with `random.Random(261001)`.
- Files are consumed in order without reuse. Each one is concatenated as
  `# ===== file: <path> =====` + the file verbatim, keeping its own license header.
- No front-matter skip.
- Every file's SHA256 is in the window's `source.files`.

| Window document | Kind | Token count per window | Rows scored (last 4,096) | Document tokens |
|---|---|---|---|---|
| pg28988 (Dreiser, *Jennie Gerhardt*) | prose | 32,768 / 65,536 / 131,072 | 28,672–32,767 / 61,440–65,535 / 126,976–131,071 | 169,490 |
| pg7412 (Disraeli, *Coningsby*) | prose | 32,768 / 65,536 / 131,072 | same | 215,961 |
| pg30754 (Ruskin, *Complete Works* vol. I) | prose | 32,768 / 65,536 / 131,072 | same | 212,048 |
| c0 (33 vLLM files) | code | 32,768 / 65,536 / 131,072 | same | 147,015 |
| c1 (40 files) | code | 32,768 / 65,536 / 131,072 | same | 132,088 |
| c2 (36 files) | code | 32,768 / 65,536 / 131,072 | same | 156,315 |

That is 18 windows, all exact. The protocol's within-engine floor ("one document per length twice") is
chosen in the scoring plan, not here.

## Block T prompts (`T/`)

There are 48 prompt files. Each has
`{id, content, input_length, prompt_index, thinking, messages, nonce, prompt_tokens, context, item}`.

**Prompt shape.** user = nonce line + `\n` + background-material frame (context prefix) + task. The context
comes first and the task last.

**Context per content type.**

| Content | Context |
|---|---|
| prose | PG-19 book 4 (`30312`) |
| code | vLLM code document c3 |
| reasoning | PG-19 book 5 (`6941`) |
| json | vLLM code document c4 |

Each content type has one fixed context. The cut is searched so that the templated prompt with nonce is
exactly 1,024, 8,192, 32,768 or 131,072 tokens.

**Exactness.** 43 of 48 cells are exact. 5 are 1–2 tokens short, because the count jumps over the target at
every cut nearby; each deviation is recorded in the cell and in `T/index.json`:
- `T-prose-008k-p2` −1
- `T-prose-008k-p3` −1
- `T-code-001k-p0` −2
- `T-code-001k-p3` −1
- `T-code-128k-p1` −1

The engines' own templates already differ by 1 token, and each request's real `usage.prompt_tokens` is
recorded by the driver.

**Items selected, by seeded rule.**

| Content | Items | Rule |
|---|---|---|
| prose (thinking off) | LongBench-Write #47, #46, #31, #55 | length ≥ 1,000 words, excluding the 4 L items, seed 261002 |
| code (thinking off) | HumanEval/129, HumanEval/49, MBPP+ 600, MBPP+ 119 | seeds 261003 / 261004; wrapper asks for the solution, a ≥15-case pytest module and an explanation, so replies run past 1,024 tokens |
| reasoning (thinking on) | MATH-500 L5 `number_theory/1128`, `intermediate_algebra/1508`, `algebra/509`, `intermediate_algebra/960` | seed 261005, the first 4 that pass the checker self-check |
| json (thinking off) | authored catalogue task, 4 themes, n = 40 each | `authored/json_task.json` |

**Lengths.** Prose and code have 1K, 8K, 32K and 128K. Reasoning and JSON have 1K and 8K only, as the
protocol says.

**Nonce.**
- 4 groups of 3 digits, drawn from `nonce_groups.json`: `NONCE_GROUPS[sha256(salt:seed:k) mod 177]`, where
  the salt is the run label plus its start time.
- The nonce's token count is constant. The build verified this on 500 random nonces per content type.
- About 9.8e8 combinations.
- The driver inserts it. Stored messages carry no nonce.

## Block L prompts (`L/`)

There are 16 prompt files. Each has
`{id, content, prompt_index, thinking, messages, nonce, prompt_tokens, checker, item}`. The user message is
the nonce line plus the task, with no context.

| Content | p0 | p1 | p2 | p3 | Rule |
|---|---|---|---|---|---|
| prose (off) | LongBench-Write #59 (12,000 words) | #56 (10,000) | #57 (10,000) | #58 (10,000) | largest required length, ties by index |
| code (off) | minicalc (29 tests) | kvstore (23) | graphkit (23) | csvreport (34) | 4 authored multi-file projects |
| reasoning (on) | MATH-500 L5 `counting_and_probability/1009` | `prealgebra/1297` | `algebra/2043` | `number_theory/838` | next 4 after the T items, same seeded walk |
| json (off) | n = 50 (≈5.4K tokens) | n = 180 (≈19K) | n = 610 (≈66K) | n = 1,030 (≈111K) | n from 0.6×8K, 0.6×32K, 0.5×128K and 0.85×128K at 108 tokens per record |

**Code projects** (`L/code/`). Each is a 4–6 module package specified exactly in `SPEC.md`:
- an expression language with lexer, parser, AST and evaluator;
- a TTL key-value store with nested transactions, persistence and a command interpreter;
- a weighted digraph with Kahn, Dijkstra, iterative Tarjan and an edge-list format;
- typed CSV with group-by and fixed-width tables.

The model writes every file as `### FILE: <path>` + a fenced block. The tests are hidden. `reference/` is my
implementation, and it passes 100% of each suite in the sandbox. That proves the suites can be passed, and it
is never shown to a model.

## Checkers (`checkers/`)

All three checkers score only the text after the last `</think>` in the content (see the section below).
Rules are in each module's docstring.

**`math_check.py`.**
- Takes the last `\boxed{}` in the final text, with brace matching.
- Applies the Hendrycks MATH normalization, plus text unwrapping, thin spaces, trailing periods and
  thousands separators.
- Compares by normalized-string equality or exact rational equality. There is no symbolic algebra.
- No boxed answer gives `no_answer`.

**`json_check.py`.**
- Unwraps a single fenced block if present, and records that it did. Nothing else is repaired.
- Then `json.loads`; the top level must be an array of exactly N.
- Each record is checked against the Draft 2020-12 schema; ids must run 1…N in order; skus must be unique.

**`code_check.py`.**
- Extracts the files; only `.py` files under the package directory are kept, and other paths are ignored and
  listed.
- Runs pytest:
  ```
  docker run --rm --network none --cpus 2 --memory 2g --pids-limit 256 --user UID:GID
    -v SRC:/work:ro -v OUT:/out -w /work --entrypoint python3 392db7c0… -m pytest -q -p no:cacheprovider --junitxml=/out/junit.xml tests
  ```
  The image is CuteAFD's own (Python 3.12, pytest 9.1.1). No local plain Python image exists; `docker images`
  has only `ubuntu:24.04` without Python. There is a 300 s kill.
- The score is passed / tests from the junit report. `all_pass` requires every test to pass.

**Self-test** (`selftest/checkers_selftest.json`): PASS.
- **Math:** all 500 MATH-500 reference solutions match their answers, plus 12 equivalent and 5
  non-equivalent cases.
- **JSON:** 11 valid and invalid cases.
- **Code:**
  - Every reference passes all tests, both in plain form and in the vLLM-style form (reasoning, then
    `</think>`, with bold headers).
  - A reply missing a file fails.
  - "No files" is detected, and `../` or absolute paths are ignored.

## Thinking-off is not the same on the two engines

Found while building, from source, not measured. Details are in `../drivers/README.md`.

- **The template.** It has no off switch: it always ends with `<think>`.
- **CuteAFD** renders off as an empty `<think></think>`, which is +1 prompt token.
- **vLLM** renders the same prompt for on and off. Its glm47 parser then streams the model's reasoning as
  `content`, followed by `</think>` and the answer.

**Effect.** The prose, code and JSON cells of T and L very likely generate reasoning on vLLM and not on
CuteAFD. The drivers record `content_has_think_close`, and the checkers score only the text after the last
`</think>`. Which way to resolve it is a protocol decision to make before freezing.

## Open items for the maintainer before freezing

1. The thinking-off difference above.
2. **Sampling.** The drivers default to temperature 1.0 and top_p 0.95, from the author's
   `generation_config.json`. The protocol does not say.
3. **Block T size.** 16.2M prompt tokens per engine run, about 6.3M of them in the 32K cells. Check this
   against the protocol's 2 h T budget once prefill rates are known.
4. **Block L JSON p3.** n = 1,030 is sized near the L3 cap. At L1 and L2 it is expected to hit the cap. That
   is intended, because stop-vs-cap is the measurement.
5. **The vLLM source in the image.** It is a development build (`0.1.dev20051+g487ecf187`). The SPDX rule
   includes any file carrying the Apache header, whether upstream or added in that image.
