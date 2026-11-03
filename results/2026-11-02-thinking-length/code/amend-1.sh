#!/usr/bin/env bash
# Amendment 1 (AMENDMENT-1.md): second launch of the base arm (k6r2, no swap) with the same captures, after chain-g.sh
# has finished; then vLLM K3.25 serving restored (exit path as chain-g.sh). Helpers copied from chain-g.sh unchanged.
R=<tl-run>
LOG=$R/logs/amend-1.log; TEL=$R/tel; DUMPS=$R/dumps; REG=$R/traces/reg
mkdir -p $R/logs $TEL $DUMPS/staging/pa $DUMPS/staging/tr $DUMPS/staging/on $DUMPS/runs $R/g1b
PYV=<venv>/bin/python
CAP="$PYV -B $R/capture/capture.py --registry $REG --out-dir $DUMPS"
W=$R/start-v092x-swap-capture.sh
XIMG_ID=sha256:5fc05b7c1b477196db77644b0d7654c7f8d0f52c77b6d008fa2b421802f3a43c
VC=glm53-flash-exl3-b12x-vllm
CLEANENV="env -i HOME=$HOME USER=$USER LOGNAME=$USER PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8"
exec 9>"$R/.amend.lock"; flock -n 9 || { echo "chain already running"; exit 75; }
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

until ! systemctl --user is-active --quiet local-thinking-g2; do sleep 60; done
log "chain-g finished; amendment 1 starts"
python3 -c "import json,hashlib,sys; f=json.load(open('$R/FROZEN-A1.json')); [sys.exit(f'changed: {p}') for p,h in f['files'].items() if hashlib.sha256(open(p,'rb').read()).hexdigest()!=h]" || exit 2
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,utilization.gpu,memory.used --format=csv -l 5 >> $TEL/gpu-a1.csv 2>&1 9>&- & TPID=$!
stop_all
launch k6r2 k6 "" 0 || exit 1
capture_all k6r2 || log "k6r2 captures incomplete"
stop_all
run "$PYV -B $R/analysis/score_stop.py --dumps $DUMPS/runs --reg $REG --base k6 --ref all --teacher <datasets>/glm53-flash-teacher-logits --pa-meta <run>/stage0/scorers/plans/pa.meta.json --out $R/analysis/G2-SCORES-A1.json > $R/logs/score-a1.log 2>&1" || log "scoring failed (rerun on CPU)"
log "amendment 1 done"
