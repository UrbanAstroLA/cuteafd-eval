#!/usr/bin/env bash
# G4 (reduced; G4-PROTOCOL.md): free generation on GPQA question 12, 12 samples per arm, arms k6 (6-bit core, route b)
# and all (316 core tensors loaded from the BF16 file); seeds 51201-51212 in both arms; then analysis and vLLM K3.25
# serving restored (exit path as chain-g.sh). Helpers copied from amend-1.sh unchanged.
R=<tl-run>
LOG=$R/logs/g4.log; TEL=$R/tel; DUMPS=$R/dumps; REG=$R/traces/reg
mkdir -p $R/logs $TEL $DUMPS/staging/pa $DUMPS/staging/tr $DUMPS/staging/on $DUMPS/runs $R/g1b
PYV=<venv>/bin/python
CAP="$PYV -B $R/capture/capture.py --registry $REG --out-dir $DUMPS"
W=$R/start-v092x-swap-capture.sh
XIMG_ID=sha256:5fc05b7c1b477196db77644b0d7654c7f8d0f52c77b6d008fa2b421802f3a43c
VC=glm53-flash-exl3-b12x-vllm
CLEANENV="env -i HOME=$HOME USER=$USER LOGNAME=$USER PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8"
exec 9>"$R/.g4.lock"; flock -n 9 || { echo "chain already running"; exit 75; }
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
run(){ log "+ $*"; bash -c "$*" 9>&-; local rc=$?; log "  exit $rc"; return $rc; }
start_v_cmd(){ echo "docker rm $VC >/dev/null 2>&1; cd <vllm-stack> && bash -c \"source '<recipes>/glm53-flash-exl3-k3.25@tpurtell+v0.9.2/env.sh' && ./local-start.sh\""; }
LOGPID=""
follow_log(){ docker logs -f "$1" > "$2" 2>&1 9>&- & LOGPID=$!; }
unfollow(){ [ -n "$LOGPID" ] && kill "$LOGPID" 2>/dev/null; LOGPID=""; }
wait_vllm_ready(){ local t=0; until docker logs $VC 2>&1 | grep -q 'container is ready'; do sleep 10; t=$((t+10))
  docker ps -q -f name=$VC | grep -q . || return 2; [ $t -ge 3600 ] && return 1; done; return 0; }
stop_all(){ run "cd <vllm-stack> && ./stop.sh"; unfollow; sleep 5; }
gpu_clear(){ nvidia-smi > $TEL/nvidia-smi-before-$1.txt 2>&1
  local others; others=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | grep . | grep -v -E 'snapd-desktop-integration|/desktop-app|gnome-shell|Xwayland|xdg-desktop-portal')
  [ -z "$others" ] || { log "compute apps on the GPUs before $1: $others"; return 1; }; return 0; }
launch(){ # $1 tag, $2 ARM, $3 SWAP_SET ("" for k6), $4 expected swapped count (0 for k6)
  gpu_clear $1 || return 1
  local extra=""; [ -n "$3" ] && extra="SWAP_SET=$3"
  run "$CLEANENV ARM=$2 $extra PIN_IMAGE_ID=$XIMG_ID OUT_DIR=$DUMPS $W > $R/logs/$1.start.log 2>&1" || { log "start of $1 failed"; return 1; }
  follow_log $VC $R/logs/$1.server.log
  wait_vllm_ready || { log "$1 not ready"; return 1; }
  docker logs $VC > $R/logs/$1.at-ready.log 2>&1
  grep -q 'glm53_capture: patched PromptLogprobsWorker.compute_prompt_logprobs' $R/logs/$1.at-ready.log || { log "$1: capture plugin not armed"; return 4; }
  grep -q 'local-exl3-core-dequant: rebuilt 316 target matrices' $R/logs/$1.at-ready.log || { log "$1: loader did not rebuild 316 matrices"; return 4; }
  if [ "$4" != 0 ]; then
    grep -q "SWAP ARM: $4 of them loaded from the BF16 file" $R/logs/$1.at-ready.log || { log "$1: expected $4 swapped matrices: $(grep 'SWAP ARM' $R/logs/$1.at-ready.log | tail -1)"; return 4; }
  elif grep -q 'SWAP ARM' $R/logs/$1.at-ready.log; then log "$1: unexpected swap"; return 4; fi
  log "$1 ready ($(grep -o 'GPU KV cache size: [0-9,]* tokens' $R/logs/$1.at-ready.log | tail -1))"; return 0; }
capture_all(){ # $1 run tag
  local s rc=0
  for s in pa tr on; do
    ls $REG/$s/*.json >/dev/null 2>&1 || { log "set $s not registered; skipped"; continue; }
    run "timeout 7200 $CAP capture --set $s --run-tag $1 --verify-chosen 4 --reset-prefix-cache --timeout 3600 > $R/logs/capture-$1-$s.log 2>&1" || { log "capture $1/$s failed"; rc=1; }
  done
  return $rc; }
TPID=""
on_exit(){ local rc=$?; [ -n "$TPID" ] && kill $TPID 2>/dev/null
  stop_all; log "restoring vLLM K3.25 serving"; bash -c "$(start_v_cmd)" > $R/logs/restore.log 2>&1 9>&-
  wait_vllm_ready && log "vLLM K3.25 ready" || log "vLLM K3.25 restore NOT ready: see $R/logs/restore.log"
  log "exit $rc"; }
trap on_exit EXIT; trap 'log interrupted; exit 130' INT TERM

python3 -c "import json,hashlib,sys; f=json.load(open('$R/FROZEN-G4.json')); [sys.exit(f'changed: {p}') for p,h in f['files'].items() if hashlib.sha256(open(p,'rb').read()).hexdigest()!=h]" || exit 2
log "G4 frozen inputs verified"
mkdir -p $R/g4/k6 $R/g4/all
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,utilization.gpu,memory.used --format=csv -l 5 >> $TEL/gpu-g4.csv 2>&1 9>&- & TPID=$!
stop_all
GEN="python3 $R/drivers/gen_traces.py --docs 12 --n 12 --concurrency 6 --seed-base 50000 --budget-s 4500"
launch g4-k6 k6 "" 0 || exit 1
run "$GEN --out $R/g4/k6 > $R/logs/g4-k6.log 2>&1" || log "g4 k6 generator exited non-zero (kept)"
stop_all
launch g4-all k6swap all 316 || exit 1
run "$GEN --out $R/g4/all > $R/logs/g4-all.log 2>&1" || log "g4 all generator exited non-zero (kept)"
stop_all
run "python3 $R/analysis/analyze_g4.py --g4 $R/g4 --g1b $R/g1b --out $R/analysis/G4-RESULT.json > $R/logs/g4-analysis.log 2>&1" || log "G4 analysis failed (rerun on CPU)"
log "G4 done"
