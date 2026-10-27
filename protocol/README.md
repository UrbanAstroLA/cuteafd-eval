# Protocol

The comparison was measured under protocol **v2 with amendments A1-A2**, frozen on 2026-10-26 at 17:32 (UTC−7) before
any Block T or L request. Later changes are dated amendments or labelled follow-ups. `PROTOCOL.md` opens with "DRAFT
v2 (not frozen)": it was frozen with that header. The two zero-GPU discovery notes it cites are not included.

| File | What it is |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | The protocol: principles, arms, blocks Q, Q2, T and L, prompt sources, cost, amendments A1 and A2 |
| [`FROZEN.json`](FROZEN.json) | The freeze record: sha256 of the protocol, the prompt manifest, drivers, scorers, scoring plans and the capture path |
| [`FOLLOWUPS.md`](FOLLOWUPS.md) | Follow-ups F1, F2 and F3 and the drift check, declared after the Block Q results were known; outside the frozen protocol |
| [`SOURCES.json`](SOURCES.json) | Provenance of every prompt source: repository, revision, licence, sha256 of each file |
| [`HASHES.json`](HASHES.json) | Each frozen hash, the corresponding file here, and whether it is byte-identical |

Files in this repository use placeholders (`<run>/`, `<datasets>/`, `<cuteafd>/` and so on) where the files as run had
local paths, so those copies differ from their frozen hashes. The drivers record their own sha256 in every receipt,
so a driver run with its placeholders filled in records a different one.

## Frozen files

| File | Frozen sha256 | In this repository | Byte-identical |
|---|---|---|---|
| `PROTOCOL-DRAFT.md` | `ea356f99a5ebed41…` | `protocol/PROTOCOL.md` | no (placeholders) |
| `stage0/prompts/MANIFEST.json` | `1622039cc2be0af8…` | `repro/stage0/prompts/MANIFEST.json` | no (placeholders) |
| `stage0/drivers/block_t.py` | `9497d75bbff4ee20…` | `repro/stage0/drivers/block_t.py` | no (placeholders) |
| `stage0/drivers/block_l.py` | `efc4754d0133b065…` | `repro/stage0/drivers/block_l.py` | no (placeholders) |
| `stage0/drivers/analyze_l.py` | `0ba724d18fe0f26b…` | `repro/stage0/drivers/analyze_l.py` | no (placeholders) |
| `stage0/scorers/score_pa.py` | `393f84482bfb5632…` | `repro/stage0/scorers/score_pa.py` | no (placeholders) |
| `stage0/scorers/score_pb.py` | `2aabc8ea04bf4983…` | `repro/stage0/scorers/score_pb.py` | no (placeholders) |
| `stage0/scorers/score_q2.py` | `94edbc2cf53cc91f…` | `repro/stage0/scorers/score_q2.py` | no (placeholders) |
| `stage0/scorers/plans/pa.cuteafd-plan.json` | `c7977da1530072ee…` | not in this repository |  |
| `stage0/scorers/plans/pb.vllm-registry.json` | `f68c31e262a38388…` | not in this repository |  |
| `stage0/scorers/plans/pa.vllm-registry.json` | `ce4ab41dcd2d6cbd…` | not in this repository |  |
| `stage0/scorers/plans/q2.cuteafd-plan.json` | `6d3ad9770a1cc524…` | not in this repository |  |
| `stage0/scorers/plans/q2.vllm-registry.json` | `bbb17874033cf902…` | not in this repository |  |
| `stage0/capture-vllm/capture.py` | `38c0448bad7939b5…` | `repro/stage0/capture-vllm/capture.py` | no (placeholders) |
| `stage0/capture-vllm/start-v092-capture.sh` | `59e5d3e796774df6…` | `repro/stage0/capture-vllm/start-v092-capture.sh` | no (placeholders) |
| `<datasets>/2026-10-26-engine-compare/SOURCES.json` | `cc81a093f75e0606…` | `protocol/SOURCES.json` | yes |

## Stage 0 prompt manifest

`repro/stage0/prompts/MANIFEST.json` lists 133 files. 67 are in this repository, 57 of them
byte-identical to the manifest. The others are the derived prompt texts (Block T contexts, Q2 windows), rebuilt from the
sources in `SOURCES.json` by `repro/stage0/prompts/build/run_build.sh`; their manifest hashes confirm a rebuild.
