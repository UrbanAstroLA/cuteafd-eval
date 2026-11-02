#!/usr/bin/env bash
# Block TC (PROTOCOL.md): tool-eval-bench on V-K3.25, C-K3.25, C-K4, C-K6, V-K4; vLLM K3.25 serving restored at the end
# and on every exit path. No `set -e`: exit codes checked explicitly. Engine helpers as in ../2026-10-30-cuteafd-v4/chain-v4.sh.
R=<runs>/2026-11-02-tool-soak; LOG=$R/logs/chain-tc.log; TEL=$R/tel; mkdir -p $R/logs $R/tc $R/gate $TEL
TEB=<tool-eval-bench>/.venv/bin/tool-eval-bench
VC=glm53-flash-exl3-b12x-vllm; CC=cuteafd-coordinator-local-v4; C4S=<stacks>/cuteafd-v4
exec 9>"$R/.chain.lock"; flock -n 9 || { echo "chain already running"; exit 75; }
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
run(){ log "+ $*"; bash -c "$*" 9>&-; local rc=$?; log "  exit $rc"; return $rc; }
vrec(){ case $1 in k325) echo glm53-flash-exl3-k3.25@tpurtell+v0.9.2;; k4) echo glm53-flash-exl3-k4@tpurtell+v0.9.2;; esac; }
cbase(){ case $1 in k325) echo glm53-flash-exl3-k3.25-core-fp8-2rtx;; k4) echo glm53-flash-exl3-k4-2rtx;; k6) echo glm53-flash-exl3-k4-core-k6-2rtx;; esac; }
start_v_cmd(){ echo "docker rm $VC >/dev/null 2>&1; cd <vllm-stack> && bash -c \"source '<recipes>/$(vrec $1)/env.sh' && ./local-start.sh\""; }
LOGPID=""
follow_log(){ docker logs -f "$1" > "$2" 2>&1 9>&- & LOGPID=$!; }
unfollow(){ [ -n "$LOGPID" ] && kill "$LOGPID" 2>/dev/null; LOGPID=""; }
wait_models(){ local t=0; until curl -sf --max-time 5 http://127.0.0.1:8001/v1/models >/dev/null 2>&1; do sleep 5; t=$((t+5)); [ $t -ge $1 ] && return 1; done; return 0; }
wait_vllm_ready(){ local t=0; until docker logs $VC 2>&1 | grep -q 'container is ready'; do sleep 10; t=$((t+10))
  docker ps -q -f name=$VC | grep -q . || return 2; [ $t -ge 3600 ] && return 1; done; return 0; }
stop_all(){ run "cd <vllm-stack> && ./stop.sh"
  run "docker ps -q -f name=^$CC\$ | grep -q . && (cd $C4S && ./stop.sh --config local/$(cbase k4).config) || true"; unfollow; sleep 5; }
gpu_clear(){ nvidia-smi > $TEL/nvidia-smi-before-$1.txt 2>&1
  local others; others=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | grep . | grep -v -E 'snapd-desktop-integration|/desktop-app|gnome-shell|Xwayland|xdg-desktop-portal')
  [ -z "$others" ] || { log "compute apps on the GPUs before $1: $others"; return 1; }; return 0; }
start_engine(){ # $1 V|C, $2 tag, $3 ck
  gpu_clear $2 || return 1; local rc=0
  case $1 in
    V) export START_CMD="$(start_v_cmd $3)"; run 'bash -c "$START_CMD"'" > $R/logs/$2.start.log 2>&1" || rc=$?
       follow_log $VC $R/logs/$2.server.log; [ $rc = 0 ] && { wait_vllm_ready; rc=$?; } ;;
    C) run "cd $C4S && ./run.sh --config local/$(cbase $3).config --restart > $R/logs/$2.start.log 2>&1" || rc=$?
       follow_log $CC $R/logs/$2.server.log; [ $rc = 0 ] && { wait_models 1200; rc=$?; } ;;
  esac
  [ $rc = 0 ] || { log "start of $2 failed (rc $rc)"; stop_all; return $rc; }; log "$2 ready"; return 0; }
TPID=""
on_exit(){ local rc=$?; [ -n "$TPID" ] && kill $TPID 2>/dev/null
  if [ "${RESTORE:-1}" = 1 ]; then stop_all; log "restoring vLLM K3.25 serving"; bash -c "$(start_v_cmd k325)" > $R/logs/restore.log 2>&1 9>&-
    wait_vllm_ready && log "vLLM K3.25 ready" || log "vLLM K3.25 restore NOT ready: see $R/logs/restore.log"; fi
  log "exit $rc"; }
trap on_exit EXIT; trap 'log interrupted; exit 130' INT TERM
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,utilization.gpu,memory.used --format=csv -l 5 >> $TEL/gpu.csv 2>&1 9>&- & TPID=$!
python3 -c "import json,hashlib,sys; f=json.load(open('$R/FROZEN.json')); [sys.exit(f'changed: {p}') for p,h in f['files'].items() if hashlib.sha256(open(p,'rb').read()).hexdigest()!=h]" || exit 2
log "frozen inputs verified"
stop_all
for spec in V:k325 C:k325 C:k4 C:k6 V:k4; do
  arm=${spec%%:*}; ck=${spec##*:}; tag=$arm-$ck
  start_engine $arm $tag $ck || exit 1
  run "python3 $R/drivers/gate_r2.py $R/gate-r-conversations.json $R/gate/$tag.json" || log "gate R2 request failed on $tag (continuing; reported)"
  for s in 1001 1002 1003; do
    n=$((s-1000))
    run "timeout 3600 $TEB --base-url http://127.0.0.1:8001/v1 --temperature 0 --max-turns 8 --timeout 900 --parallel 8 --hardmode --reference-date 2026-09-04 --seed $s --backend-kwargs '{\"chat_template_kwargs\":{\"clear_thinking\":false}}' --json-file $R/tc/$tag-r$n.json --output-dir $R/tc/reports > $R/logs/$tag-r$n.log 2>&1" || log "repeat $tag r$n exited non-zero"
  done
  curl -s --max-time 10 http://127.0.0.1:8001/metrics > $R/logs/$tag.metrics.txt 2>/dev/null
  log "$tag server log error lines: $(sed 's/\x1b\[[0-9;]*m//g' $R/logs/$tag.server.log | grep -Ec ' ERROR |out of memory|panicked|Traceback|CUDA error|NCCL error')"
  stop_all
done
log "block TC done"
