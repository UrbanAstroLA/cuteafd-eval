#!/usr/bin/env bash
# Attention arm (exploratory, NOTE.md): CuteAFD v4 scoring launch of C-K6a (K4-Core-K6 with BF16 attention, FP8 at load)
# on the 93 fixed traces, then a C-K6 recheck on the 10 longest traces (bit-identity against the stored core-swap
# dumps, so the stored C-K6 and C-K6x dumps can serve as the other arms); vLLM K3.25 serving restored on every exit path.
#
#   systemd-run --user --unit=local-attn --collect <ap-run>/chain-attn.sh
#   ./chain-attn.sh --dry-run
#
# Helpers copied from the core-swap's chain-cs.sh (logging, run, stop_all, gpu_clear, bench key made with umask 077 and
# shredded on every exit path, vLLM restore). No set -e: exit codes are checked.
R=<ap-run>; CS=<cs-run>; D=$CS/drivers; LOG=$R/logs/chain-attn.log
mkdir -p $R/logs $R/s2/runs
TL=<tl-run>; REG=$TL/traces/reg; PYV=<venv>/bin/python
VC=glm53-flash-exl3-b12x-vllm; CC=cuteafd-coordinator-local-v4; C4S=<stacks>/cuteafd-v4
KEY=<secrets>/bench-api-key; BASE=http://127.0.0.1:8001
CHECK=tr029-d127-fin,tr028-d127-fin,tr027-d127-fin,on005-d186-fin,tr026-d127-fin,tr040-d88-fin,tr025-d127-fin,tr039-d88-fin,tr038-d88-fin,tr024-d127-fin
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
[ $DRY = 1 ] && { mkdir -p $R/dryrun; LOG=$R/dryrun/chain-attn.dry.log; : > $LOG; }
export PYTHONDONTWRITEBYTECODE=1
exec 9>"$R/.chain.lock"; flock -n 9 || { echo "chain already running"; exit 75; }
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
run(){ if [ $DRY = 1 ]; then echo "DRY: $*" | tee -a "$LOG"; return 0; fi
  log "+ $*"; bash -c "$*" 9>&-; local rc=$?; log "  exit $rc"; return $rc; }
cfg(){ # $1 arm, $2 serve|score
  local s=""; [ "$2" = score ] && s="-score"
  case $1 in C-K6) echo "local/glm53-flash-exl3-k4-core-k6-2rtx$s.config";;
             C-K6a) echo "local/glm53-flash-exl3-k4-core-k6-bf16attn-2rtx$s.config";;
             C-K4) echo "local/glm53-flash-exl3-k4-2rtx$s.config";; esac; }
start_v_cmd(){ echo "docker rm $VC >/dev/null 2>&1; cd <vllm-stack> && bash -c \"source '<recipes>/glm53-flash-exl3-k3.25@tpurtell+v0.9.2/env.sh' && ./local-start.sh\""; }
wait_models(){ [ $DRY = 1 ] && return 0; local t=0 h=()   # $1 timeout s, $2 optional key file
  [ -n "${2:-}" ] && h=(-H "Authorization: Bearer $(cat "$2")")
  until curl -sf --max-time 5 "${h[@]}" $BASE/v1/models >/dev/null 2>&1; do sleep 5; t=$((t+5))
    docker ps -q -f name=^$CC\$ | grep -q . || return 2; [ $t -ge $1 ] && return 1; done; return 0; }
wait_vllm_ready(){ [ $DRY = 1 ] && return 0; local t=0; until docker logs $VC 2>&1 | grep -q 'container is ready'; do sleep 10; t=$((t+10))
  docker ps -q -f name=$VC | grep -q . || return 2; [ $t -ge 3600 ] && return 1; done; return 0; }
LOGPID=""
follow_log(){ [ $DRY = 1 ] && return; docker logs -f "$1" > "$2" 2>&1 9>&- & LOGPID=$!; }
unfollow(){ [ -n "$LOGPID" ] && kill "$LOGPID" 2>/dev/null; LOGPID=""; }
stop_all(){ run "cd <vllm-stack> && ./stop.sh"
  run "docker ps -q -f name=^$CC\$ | grep -q . && (cd $C4S && ./stop.sh --config $(cfg C-K4 serve)) || true"; unfollow; [ $DRY = 1 ] || sleep 5; }
gpu_clear(){ [ $DRY = 1 ] && return 0
  nvidia-smi > $R/logs/nvidia-smi-before-$1.txt 2>&1
  local others; others=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | grep . | grep -v -E 'snapd-desktop-integration|/desktop-app|gnome-shell|Xwayland|xdg-desktop-portal')
  [ -z "$others" ] || { log "compute apps on the GPUs before $1: $others"; return 1; }; return 0; }
make_key(){ run "umask 077; mkdir -p <secrets> && head -c 32 /dev/urandom | base64 | tr -d '/+=\n' > $KEY"; }
shred_key(){ [ -f $KEY ] && { shred -u $KEY 2>/dev/null || rm -f $KEY; log "bench key shredded"; }; }
GPID=""
RESTORE=0
on_exit(){ local rc=$?; [ -n "$GPID" ] && kill $GPID 2>/dev/null; shred_key
  if [ "$RESTORE" = 1 ]; then RESTORE=0; stop_all; log "restoring vLLM K3.25 serving"
    if [ $DRY = 1 ]; then echo "DRY: $(start_v_cmd)" | tee -a "$LOG"
    else bash -c "$(start_v_cmd)" > $R/logs/restore.log 2>&1 9>&-
      wait_vllm_ready && log "vLLM K3.25 ready" || log "vLLM K3.25 restore NOT ready: see $R/logs/restore.log"; fi; fi
  log "exit $rc"; }
trap on_exit EXIT; trap 'log interrupted; exit 130' INT TERM

# ---------- pre-flight ----------
if [ $DRY = 0 ]; then
  [ -n "${INVOCATION_ID:-}" ] || { echo "run under systemd-run --user (long job)"; exit 2; }
  [ -f $R/prep/derived-manifest.json ] || { log "derived checkpoint not built"; exit 2; }
  others=$(systemctl --user list-units --type=service --state=active --no-legend 'local-*' | awk '{print $1}' | grep -v -E '^local-(status|daily|attn)\.service$')
  [ -z "$others" ] || { log "other local units active: $others"; exit 2; }
fi
log "chain start"
[ $DRY = 1 ] || { nvidia-smi --query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw,temperature.gpu --format=csv -l 30 > $R/logs/gpu.csv 2>&1 9>&- & GPID=$!; }
RESTORE=1; stop_all

start_c(){ # $1 arm, $2 serve|score, $3 log tag
  gpu_clear "$3" || return 1
  local k=""; [ "$2" = score ] && { make_key; k=$KEY; }
  run "cd $C4S && HF_HOME=<hf-home> ./run.sh --config $(cfg $1 $2) --restart > $R/logs/start-$3.log 2>&1" || return 1
  follow_log $CC $R/logs/server-$3.log
  wait_models 1500 "$k" || { log "$3: CuteAFD not ready"; return 1; }
  log "$3 ready ($(cfg $1 $2))"; return 0; }

if start_c C-K6a score s2-C-K6a; then
  run "$PYV -B $D/probe_traces.py --reg $REG --out $R/s2/runs/C-K6a --api-key-file $KEY > $R/logs/s2-C-K6a.log 2>&1" || log "s2 C-K6a: probe run stopped (see log)"
else log "s2 C-K6a not run"; fi
stop_all; shred_key
if start_c C-K6 score s2-C-K6check; then
  run "$PYV -B $D/probe_traces.py --reg $REG --out $R/s2/runs/C-K6-check --only $CHECK --api-key-file $KEY > $R/logs/s2-C-K6check.log 2>&1" || log "s2 C-K6 check: probe run stopped (see log)"
else log "s2 C-K6 check not run"; fi
RESTORE=0; stop_all; shred_key; log "restoring vLLM K3.25 serving"
if [ $DRY = 1 ]; then echo "DRY: $(start_v_cmd)" | tee -a "$LOG"; else
  bash -c "$(start_v_cmd)" > $R/logs/restore.log 2>&1 9>&-
  wait_vllm_ready && log "vLLM K3.25 ready" || log "vLLM K3.25 restore NOT ready: see $R/logs/restore.log"; fi
run "$PYV -B $D/s2_identity.py $R/s2/runs/C-K6-check $CS/s2/runs/C-K6 > $R/analysis/S2-IDENTITY-CHECK.json" || log "identity check failed"
log "chain done"
