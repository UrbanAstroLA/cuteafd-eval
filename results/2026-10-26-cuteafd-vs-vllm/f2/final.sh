#!/usr/bin/env bash
# After chain.sh: CuteAFD drift, then vLLM capture launch (F3), then vLLM normal launch (drift, F2). FOLLOWUPS.md.
R=<run>; D=$R/stage0/drivers; CAP=$R/stage0/capture-vllm; export HF_HOME=<hf-home>
PY=<venv>/bin/python
until grep -q '^chain done\|GATE STOP\|SERVE START FAILED' $R/f1/chain.log 2>/dev/null; do sleep 60; done
echo "chain finished $(date -Is): $(tail -1 $R/f1/chain.log)"
mkdir -p $R/drift
(cd $D && python3 block_t.py --base-url http://127.0.0.1:8001 --label C1-drift --out $R/drift/C1-drift.json --lengths 1024 32768 --levels 1 8 --contents code prose --reps 0 1 --no-cached-cell --nonce-salt 'C1-r1:1793079558737877023' > $R/drift/C1-drift.log 2>&1); echo "C1 drift exit $? $(date -Is)"
(cd <cuteafd> && ./stop.sh --config local/glm53-flash-exl3-k3.25-core-fp8-2rtx.config >/dev/null 2>&1); sleep 5
docker rm glm53-flash-exl3-b12x-vllm >/dev/null 2>&1
(cd $CAP && OUT_DIR=$R/vllm-v092-dumps ./start-v092-capture.sh > $R/q/cli/vllm-capture-start-2.log 2>&1); echo "capture launch $? $(date -Is)"
until docker logs glm53-flash-exl3-b12x-vllm 2>&1 | grep -q "startup warmup complete; container is ready"; do docker ps -q -f name=glm53-flash-exl3-b12x-vllm | grep -q . || { echo "capture container gone"; break; }; sleep 15; done
(cd $CAP && $PY capture.py capture --set pb --run-tag v2-r1 --verify-chosen 8 > $R/q/cli/vllm-pb-v2r1.log 2>&1); echo "F3 pb $? $(date -Is)"
(cd $CAP && $PY capture.py capture --set pa --run-tag v2-r1 > $R/q/cli/vllm-pa-v2r1.log 2>&1); echo "F3 pa $? $(date -Is)"
docker stop glm53-flash-exl3-b12x-vllm >/dev/null; docker rm glm53-flash-exl3-b12x-vllm >/dev/null 2>&1
(cd <vllm-stack> && bash -c 'source "<recipes>/glm53-flash-exl3-k3.25@tpurtell+v0.9.2/env.sh" && ./local-start.sh' > $R/q/cli/vllm-restore-start-2.log 2>&1); echo "normal launch $? $(date -Is)"
until [ "$(docker inspect -f '{{.State.Health.Status}}' glm53-flash-exl3-b12x-vllm 2>/dev/null)" = healthy ]; do sleep 15; done
curl -s 127.0.0.1:8001/metrics | grep -E '^vllm:spec_decode' > $R/drift/V1-spec-metrics-before.txt
(cd $D && python3 block_t.py --base-url http://127.0.0.1:8001 --label V1-drift --out $R/drift/V1-drift.json --lengths 1024 32768 --levels 1 8 --contents code prose --reps 0 1 --no-cached-cell --nonce-salt 'V1-r1:1793064953235561649' > $R/drift/V1-drift.log 2>&1); echo "V1 drift exit $? $(date -Is)"
curl -s 127.0.0.1:8001/metrics | grep -E '^vllm:spec_decode' > $R/drift/V1-spec-metrics-after.txt
python3 $R/f2/f2_prefix_cache.py --text <datasets>/2026-10-26-engine-compare/pg19/30312.txt --out $R/f2/f2.json > $R/f2/f2.log 2>&1; echo "F2 exit $? $(date -Is)"
docker logs glm53-flash-exl3-b12x-vllm 2>&1 | grep -iE 'prefix|mamba.cache|block_size|align' | head -40 > $R/f2/server-log-cache-lines.txt
echo "final done $(date -Is)"
