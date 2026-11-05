#!/usr/bin/env bash
# CuteAFD core-swap chain (PROTOCOL.md): step 2 (fixed traces, scoring launches C-K6, C-K6x, C-K4, C-K6 again), then
# step 1 (Block L stage L3, code and prose, two seed sets per arm: C-K6x, C-K6, C-K4); analysis (CPU); vLLM K3.25
# serving restored at the end and on every exit path.
#
#   systemd-run --user --unit=local-coreswap --collect <cs-run>/chain-cs.sh
#   ./chain-cs.sh --dry-run      print every engine/docker command instead of running it (nothing starts)
#
# Helpers (logging, run, stop_all, gpu_clear, the vLLM restore, the bench key made with umask 077 and shredded on every
# exit path) follow chain-endurance.sh and chain-v4.sh. Waits for the endurance unit to finish first. Refuses unless
# under systemd, FROZEN.json matches, and no other local-* run unit is active. No `set -e`: exit codes are checked.
R=<cs-run>; D=$R/drivers; LOG=$R/logs/chain-cs.log; mkdir -p $R/logs
TL=<tl-run>; REG=$TL/traces/reg; PYV=<venv>/bin/python
VC=glm53-flash-exl3-b12x-vllm; CC=cuteafd-coordinator-local-v4; C4S=<stacks>/cuteafd-v4
KEY=<secrets>/bench-api-key; BASE=http://127.0.0.1:8001
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
[ $DRY = 1 ] && { LOG=$R/dryrun/chain-cs.dry.log; : > $LOG; }
export PYTHONDONTWRITEBYTECODE=1
exec 9>"$R/.chain.lock"; flock -n 9 || { echo "chain already running"; exit 75; }
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
run(){ if [ $DRY = 1 ]; then echo "DRY: $*" | tee -a "$LOG"; return 0; fi
  log "+ $*"; bash -c "$*" 9>&-; local rc=$?; log "  exit $rc"; return $rc; }
cfg(){ # $1 arm, $2 serve|score
  local s=""; [ "$2" = score ] && s="-score"
  case $1 in C-K6|C-K6r2) echo "local/glm53-flash-exl3-k4-core-k6-2rtx$s.config";;
             C-K6x) echo "local/glm53-flash-exl3-k4-core-k6-bf16core-2rtx$s.config";;
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
  [ -f $R/FROZEN.json ] || { log "FROZEN.json missing: not frozen"; exit 2; }
  python3 - "$R/FROZEN.json" <<'EOF' || { log "a frozen file changed"; exit 2; }
import hashlib, json, sys
fz = json.load(open(sys.argv[1]))
bad = [p for p, h in fz["sha256"].items() if hashlib.sha256(open(p, "rb").read()).hexdigest() != h]
print("frozen files changed:", bad) if bad else None
sys.exit(1 if bad else 0)
EOF
  log "waiting for the endurance unit to finish"
  while systemctl --user is-active -q local-endurance; do sleep 60; done
  others=$(systemctl --user list-units --type=service --state=active --no-legend 'local-*' | awk '{print $1}' | grep -v -E '^local-(status|daily|coreswap)\.service$')
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

# ---------- step 2: fixed traces, deterministic scoring ----------
for arm in C-K6 C-K6x C-K4 C-K6r2; do
  if start_c $arm score s2-$arm; then
    run "$PYV -B $D/probe_traces.py --reg $REG --out $R/s2/runs/$arm --api-key-file $KEY > $R/logs/s2-$arm.log 2>&1" || log "s2 $arm: probe run stopped (see log)"
  else log "s2 $arm not run"; fi
  stop_all; shred_key
done
for b in "C-K6 C-K6x" "C-K6x C-K4"; do set -- $b
  run "$PYV -B $TL/analysis/score_stop.py --dumps $R/s2/runs --reg $REG --base $1 --ref $2 --out $R/analysis/S2-SCORES-base-$1.json > $R/logs/s2-score-$1.log 2>&1" || log "s2 scoring (base $1) failed"
done
run "$PYV -B $D/s2_identity.py $R/s2/runs/C-K6 $R/s2/runs/C-K6r2 > $R/analysis/S2-IDENTITY.json" || log "s2 identity check failed"

# ---------- step 1: free generation, Block L L3 code + prose ----------
for arm in C-K6x C-K6 C-K4; do
  if start_c $arm serve s1-$arm; then
    for off in 20 30; do
      run "CS_OFFSET=$off python3 -B $D/block_l3_cs.py --arm C --label $arm-o$off --stages L3 --out $R/l/$arm-o$off-L3.json > $R/logs/s1-$arm-o$off.log 2>&1" || log "s1 $arm offset $off: stage stopped (see log)"
    done
  else log "s1 $arm not run"; fi
  stop_all
done
RESTORE=0; stop_all; log "restoring vLLM K3.25 serving"
if [ $DRY = 1 ]; then echo "DRY: $(start_v_cmd)" | tee -a "$LOG"; else
  bash -c "$(start_v_cmd)" > $R/logs/restore.log 2>&1 9>&-
  wait_vllm_ready && log "vLLM K3.25 ready" || log "vLLM K3.25 restore NOT ready: see $R/logs/restore.log"; fi
# reasoning tokens by re-tokenization: the frozen K3.25 Block L analyzer, CPU-only no-network containers (as the v4 run)
rs=$(ls $R/l/*-L3.json 2>/dev/null | tr '\n' ' ')
run "nice -n 10 python3 <run>/stage0/drivers/analyze_l.py $rs --out $R/l/L-analysis.json > $R/logs/s1-analyze-l.log 2>&1" || log "Block L analyzer failed"
run "python3 -B $R/analysis/analyze_s1.py --l $R/l --out $R/analysis/S1-RESULT.json > $R/logs/s1-analysis.log 2>&1" || log "s1 analysis failed"
log "chain done"
