#!/usr/bin/env bash
# vLLM arm of the code-thinking study (PROTOCOL.md): the CuteAFD study's 16 code prompts x 4 seeds (same seeds) on the
# vLLM fork v0.9.2-experimental with the route-b loader, arms V-BF16 (whole core native BF16, SWAP_SET=all, 316 matrices)
# then V-K6 (6-bit core dequantized to BF16 at load); the Block L analyzer (the CuteAFD study's copy, unchanged) on both
# receipts, then analyze_vct.py (CPU). vLLM K3.25 serving restored at the end and on every exit path.
# Helpers from the new-question chain-nq.sh (launch checks loader counts; the capture plugin is armed but unused).
#   systemd-run --user --unit=local-vct --collect <vct-run>/chain-vct.sh
R=<tl-run>; N=<vct-run>
LOG=$N/logs/chain-vct.log; TEL=$N/tel; DUMPS=$N/dumps
mkdir -p $N/logs $TEL $DUMPS/staging
[ -n "${INVOCATION_ID:-}" ] || { echo "run under systemd-run --user (long job)"; exit 2; }
while systemctl --user is-active -q local-nq; do sleep 60; done
others=$(systemctl --user list-units --type=service --state=active --no-legend 'local-*' | awk '{print $1}' | grep -v -E '^local-(status|daily|vct)\.service$')
[ -z "$others" ] || { echo "$(date -Is) other local units active: $others" >> $LOG; exit 2; }
PYV=<venv>/bin/python
W=$R/start-v092x-swap-capture.sh
XIMG_ID=sha256:5fc05b7c1b477196db77644b0d7654c7f8d0f52c77b6d008fa2b421802f3a43c
VC=glm53-flash-exl3-b12x-vllm
CC=cuteafd-coordinator-local-v4; C4S=<stacks>/cuteafd-v4
KEY=<secrets>/bench-api-key; BASE=http://127.0.0.1:8001
SAMPLES="<runs>/gpqa/glm53-flash-exl3-k3.25@tpurtell__pass1/wrldsuksgo2mars__GLM-5.3-Flash-EXL3-K3.25-v1/samples_gpqa_diamond_thinking_2026-09-29T10-34-37.597068.jsonl"
TOKJ=<hf-hub>/models--wrldsuksgo2mars--GLM-5.3-Flash-EXL3-K4-Core-K6/snapshots/5d3fffe1df9c4a109bbbdafb60dc19df9fac019d/tokenizer.json
CLEANENV="env -i HOME=$HOME USER=$USER LOGNAME=$USER PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8"
exec 9>"$N/.chain-vct.lock"; flock -n 9 || { echo "chain already running"; exit 75; }
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
run(){ log "+ $*"; bash -c "$*" 9>&-; local rc=$?; log "  exit $rc"; return $rc; }
start_v_cmd(){ echo "docker rm $VC >/dev/null 2>&1; cd <vllm-stack> && bash -c \"source '<recipes>/glm53-flash-exl3-k3.25@tpurtell+v0.9.2/env.sh' && ./local-start.sh\""; }
LOGPID=""
follow_log(){ docker logs -f "$1" > "$2" 2>&1 9>&- & LOGPID=$!; }
unfollow(){ [ -n "$LOGPID" ] && kill "$LOGPID" 2>/dev/null; LOGPID=""; }
wait_vllm_ready(){ local t=0; until docker logs $VC 2>&1 | grep -q 'container is ready'; do sleep 10; t=$((t+10))
  docker ps -q -f name=$VC | grep -q . || return 2; [ $t -ge 3600 ] && return 1; done; return 0; }
wait_models(){ local t=0 h=(-H "Authorization: Bearer $(cat "$1")")
  until curl -sf --max-time 5 "${h[@]}" $BASE/v1/models >/dev/null 2>&1; do sleep 5; t=$((t+5))
    docker ps -q -f name=^$CC\$ | grep -q . || return 2; [ $t -ge 1500 ] && return 1; done; return 0; }
cfg(){ case $1 in C-K6) echo "local/glm53-flash-exl3-k4-core-k6-2rtx-score.config";;
                  C-K6x) echo "local/glm53-flash-exl3-k4-core-k6-bf16core-2rtx-score.config";; esac; }
stop_all(){ run "cd <vllm-stack> && ./stop.sh"
  run "docker ps -q -f name=^$CC\$ | grep -q . && (cd $C4S && ./stop.sh --config $(cfg C-K6)) || true"; unfollow; sleep 5; }
gpu_clear(){ nvidia-smi > $TEL/nvidia-smi-before-$1.txt 2>&1
  local others; others=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | grep . | grep -v -E 'snapd-desktop-integration|/desktop-app|gnome-shell|Xwayland|xdg-desktop-portal')
  [ -z "$others" ] || { log "compute apps on the GPUs before $1: $others"; return 1; }; return 0; }
launch(){ # $1 tag, $2 ARM, $3 SWAP_SET ("" for k6), $4 expected swapped count (0 for k6), $5 registry dir
  gpu_clear $1 || return 1
  local extra=""; [ -n "$3" ] && extra="SWAP_SET=$3"
  run "$CLEANENV ARM=$2 $extra REGISTRY_DIR=$5 PIN_IMAGE_ID=$XIMG_ID OUT_DIR=$DUMPS $W > $N/logs/$1.start.log 2>&1" || { log "start of $1 failed"; return 1; }
  follow_log $VC $N/logs/$1.server.log
  wait_vllm_ready || { log "$1 not ready"; return 1; }
  docker logs $VC > $N/logs/$1.at-ready.log 2>&1
  grep -q 'glm53_capture: patched PromptLogprobsWorker.compute_prompt_logprobs' $N/logs/$1.at-ready.log || { log "$1: capture plugin not armed"; return 4; }
  grep -q 'local-exl3-core-dequant: rebuilt 316 target matrices' $N/logs/$1.at-ready.log || { log "$1: loader did not rebuild 316 matrices"; return 4; }
  if [ "$4" != 0 ]; then
    grep -q "SWAP ARM: $4 of them loaded from the BF16 file" $N/logs/$1.at-ready.log || { log "$1: expected $4 swapped matrices: $(grep 'SWAP ARM' $N/logs/$1.at-ready.log | tail -1)"; return 4; }
  elif grep -q 'SWAP ARM' $N/logs/$1.at-ready.log; then log "$1: unexpected swap"; return 4; fi
  log "$1 ready ($(grep -o 'GPU KV cache size: [0-9,]* tokens' $N/logs/$1.at-ready.log | tail -1))"; return 0; }
make_key(){ run "umask 077; mkdir -p <secrets> && head -c 32 /dev/urandom | base64 | tr -d '/+=\n' > $KEY"; }
shred_key(){ [ -f $KEY ] && { shred -u $KEY 2>/dev/null || rm -f $KEY; log "bench key shredded"; }; }
TPID=""
on_exit(){ local rc=$?; [ -n "$TPID" ] && kill $TPID 2>/dev/null; shred_key
  stop_all; log "restoring vLLM K3.25 serving"; bash -c "$(start_v_cmd)" > $N/logs/restore.log 2>&1 9>&-
  wait_vllm_ready && log "vLLM K3.25 ready" || log "vLLM K3.25 restore NOT ready: see $N/logs/restore.log"
  log "exit $rc"; }
trap on_exit EXIT; trap 'log interrupted; exit 130' INT TERM

python3 -c "import json,hashlib,sys; f=json.load(open('$N/FROZEN.json')); [sys.exit(f'changed: {p}') for p,h in f['files'].items() if hashlib.sha256(open(p,'rb').read()).hexdigest()!=h]" || { log "a frozen file changed"; exit 2; }
log "frozen inputs verified"
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,utilization.gpu,memory.used --format=csv -l 30 >> $TEL/gpu.csv 2>&1 9>&- & TPID=$!
stop_all
for spec in "V-BF16:k6swap:all:316" "V-K6:k6::0"; do
  IFS=: read -r label arm set n <<< "$spec"
  if launch $label $arm "$set" $n $R/traces/reg; then
    run "python3 -B $N/drivers/code_thinking_v.py --arm Vb --label $label --stages L3 --out $N/l/$label-L3.json > $N/logs/$label.log 2>&1" || log "$label: stage stopped (see log)"
  else log "$label not run"; fi
  stop_all
done
rs=$(ls $N/l/*-L3.json 2>/dev/null | tr '\n' ' ')
run "nice -n 10 python3 <ct-run>/stage0/drivers/analyze_l.py $rs --out $N/l/L-analysis.json > $N/logs/analyze-l.log 2>&1" || log "Block L analyzer failed"
run "python3 -B $N/analysis/analyze_vct.py --l $N/l --cuteafd <ct-run>/l --out $N/analysis/VCT-RESULT.json > $N/logs/vct-analysis.log 2>&1" || log "vct analysis failed"
log "vct chain done"
