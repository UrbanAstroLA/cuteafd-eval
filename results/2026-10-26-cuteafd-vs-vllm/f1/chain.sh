#!/usr/bin/env bash
# Chain after CuteAFD Block T: F1 arms (FOLLOWUPS.md incl. amendment A1), then CuteAFD Block L with gates.
R=<run>; Q=$R/q; C=<cuteafd>; export HF_HOME=<hf-home>
KEY=<secrets>/bench-api-key
until grep -q '^exit' $R/t/C1-r1-block-t.log; do sleep 30; done
echo "T done $(date -Is): $(tail -1 $R/t/C1-r1-block-t.log)"
for a in base f1a f1b f1c f1d; do
  cfg=local/glm53-flash-exl3-k3.25-core-fp8-2rtx-score.config; [ $a = base ] || cfg=local/glm53-flash-exl3-k3.25-core-fp8-2rtx-score-$a.config
  (cd $C && ./run.sh --config $cfg --restart > local/logs/start-f1-$a.log 2>&1) || { echo "$a START FAILED (not runnable)"; tail -5 $C/local/logs/start-f1-$a.log; continue; }
  if [ $a != base ]; then
    docker exec -e CUTEAFD_API_KEY="$(cat $KEY)" cuteafd-coordinator cuteafd bench fidelity run --url http://127.0.0.1:8001 --tier full --score-path prefill --arm F1-$a --dataset-config glm5_flash-v2_20261005_bf16root --dataset-revision a7e7d1b4d82329acebe54ca88dc71d47d0d2056d --dump-dir $Q/dumps/pb-F1-$a --out $Q/dumps/pb-F1-$a-prefill.json > $R/f1/pb-F1-$a.log 2>&1
    echo "$a cli exit $? $(date -Is)"; mv $Q/dumps/pb-F1-$a-prefill.json $R/f1/ 2>/dev/null
  fi
  (cd $R/stage0/drivers && python3 block_t.py --base-url http://127.0.0.1:8001 --label F1-$a --api-key-file $KEY --out $R/f1/speed-F1-$a.json --lengths 1024 8192 --levels 1 8 --contents code prose --reps 0 1 --no-cached-cell > $R/f1/speed-F1-$a.log 2>&1)
  echo "$a speed exit $? $(date -Is)"
done
(cd $C && ./run.sh --config local/glm53-flash-exl3-k3.25-core-fp8-2rtx.config --restart > local/logs/start-serve-c1-l.log 2>&1) || { echo "SERVE START FAILED"; exit 1; }
echo "serving restored $(date -Is)"
cd $R/stage0/drivers
for st in L1 L2 L3 L3s; do
  t0=$(date -Is)
  python3 block_l.py --base-url http://127.0.0.1:8001 --label C1-r1 --out $R/l/C1-r1-$st.json --stages $st --read-timeout 14400 > $R/l/C1-r1-$st.log 2>&1; rc=$?
  echo "exit $rc" >> $R/l/C1-r1-$st.log
  bad=$(docker logs --since "$t0" cuteafd-coordinator 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -E ' ERROR |out of memory|panicked' | wc -l)
  echo "$st exit $rc log-flags $bad $(date -Is)"
  [ $rc -eq 0 ] && [ "$bad" = 0 ] || { echo "GATE STOP after $st"; break; }
done
echo "chain done $(date -Is)"
