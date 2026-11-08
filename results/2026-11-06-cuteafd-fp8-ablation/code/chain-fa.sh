#!/usr/bin/env bash
# FP8 ablation run (PROTOCOL.md): the BF16-core checkpoint on CuteAFD v4.0.0 (serving config of the code study's C-K6x) with
# the launcher's FP8 settings switched off cumulatively: F-kda (GLM5_FLASH_KDA_FP8=off), F-head (+ GLM5_FLASH_FP8_HEAD=off),
# F-pre (+ GLM5_FLASH_FP8_PREFILL=off); each 16 code prompts x 4 replies, the code study's seeds. First a one-request
# replay of C-K6x (descriptive). Each launch is checked against its server log (KDA, head and prefill precision) before any
# request. Then the code study's Block L analyzer (unchanged) and analyze_fa.py (CPU). vLLM K3.25 restored at the end and on
# every exit path.
#
#   systemd-run --user --unit=local-fp8abl --collect <runs>/2026-11-06-cuteafd-fp8-ablation/chain-fa.sh
#   ./chain-fa.sh --dry-run
#
# Helpers copied from the code study's chain-ct.sh. Refuses unless under systemd, FROZEN.json matches, and no other
# local-* run unit is active. No set -e: exit codes are checked.
R=<runs>/2026-11-06-cuteafd-fp8-ablation; LOG=$R/logs/chain-fa.log; mkdir -p $R/logs $R/l
CT=<ct-run>; PYV=<venv>/bin/python
VC=glm53-flash-exl3-b12x-vllm; CC=cuteafd-coordinator-local-v4; C4S=<stacks>/cuteafd-v4
KEY=<secrets>/bench-api-key; BASE=http://127.0.0.1:8001
CFG=local/glm53-flash-exl3-k4-core-k6-bf16core-2rtx.config
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
[ $DRY = 1 ] && { mkdir -p $R/dryrun; LOG=$R/dryrun/chain-fa.dry.log; : > $LOG; }
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
  run "docker ps -q -f name=^$CC\$ | grep -q . && (cd $C4S && ./stop.sh --config $CFG) || true"; unfollow; [ $DRY = 1 ] || sleep 5; }
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
  python3 - "$R/FROZEN.json" <<'PYEOF' || { log "a frozen file changed"; exit 2; }
import hashlib, json, sys
fz = json.load(open(sys.argv[1]))
bad = [p for p, h in fz["sha256"].items() if hashlib.sha256(open(p, "rb").read()).hexdigest() != h]
print("frozen files changed:", bad) if bad else None
sys.exit(1 if bad else 0)
PYEOF
  others=$(systemctl --user list-units --type=service --state=active --no-legend 'local-*' | awk '{print $1}' | grep -v -E '^local-(status|daily|fp8abl)\.service$')
  [ -z "$others" ] || { log "other local units active: $others"; exit 2; }
fi
log "chain start"
[ $DRY = 1 ] || { nvidia-smi --query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw,temperature.gpu --format=csv -l 30 > $R/logs/gpu.csv 2>&1 9>&- & GPID=$!; }
RESTORE=1; stop_all

sets(){ case $1 in
  F-ctrl) echo "";;
  F-kda)  echo "--set GLM5_FLASH_KDA_FP8=off";;
  F-head) echo "--set GLM5_FLASH_KDA_FP8=off --set GLM5_FLASH_FP8_HEAD=off";;
  F-pre)  echo "--set GLM5_FLASH_KDA_FP8=off --set GLM5_FLASH_FP8_HEAD=off --set GLM5_FLASH_FP8_PREFILL=off";; esac; }
expect(){ # $1 arm -> required KDA / head / prefill fields in the server log
  case $1 in F-ctrl) echo "kda_fp8=Row128 fp8_head=true MLA";; F-kda) echo "kda_fp8=Off fp8_head=true MLA";;
             F-head) echo "kda_fp8=Off fp8_head=false MLA";; F-pre) echo "kda_fp8=Off fp8_head=false NONE";; esac; }
check_precision(){ # verify the launch, not the settings: read what the daemon resolved
  [ $DRY = 1 ] && return 0
  local f=$R/logs/server-$1.log t=0; until grep -a -q 'fp8_head' $f 2>/dev/null; do sleep 2; t=$((t+2)); [ $t -ge 60 ] && break; done
  local clean; clean=$(sed 's/\x1b\[[0-9;]*m//g' $f)
  local k h p; k=$(echo "$clean" | grep -o -m1 'kda_fp8=[A-Za-z0-9]*'); h=$(echo "$clean" | grep -o -m1 'fp8_head=[a-z]*')
  p=$(echo "$clean" | grep -o -m1 'fp8_prefill=\[[^]]*\]')
  local got="$k $h $( [[ "$p" == *Mla* ]] && echo MLA || echo NONE )"
  log "$1 resolved: $k $h $p"
  [ "$got" = "$(expect $1)" ] || { log "$1: precision mismatch (want $(expect $1), got $got)"; return 1; }; return 0; }
start_f(){ # $1 arm
  gpu_clear "$1" || return 1
  run "cd $C4S && HF_HOME=<hf-home> ./run.sh --config $CFG $(sets $1) --restart > $R/logs/start-$1.log 2>&1" || return 1
  follow_log $CC $R/logs/server-$1.log
  wait_models 1500 || { log "$1: CuteAFD not ready"; return 1; }
  check_precision $1 || return 1
  log "$1 ready ($CFG $(sets $1))"; return 0; }

for arm in F-ctrl F-kda F-head F-pre; do
  ctl=""; [ $arm = F-ctrl ] && ctl="--control"
  if start_f $arm; then
    run "python3 -B $R/drivers/fp8_ablation.py --arm C --label $arm --stages L3 --out $R/l/$arm-L3.json $ctl > $R/logs/$arm.log 2>&1" || log "$arm: stage stopped (see log)"
  else log "$arm not run"; fi
  stop_all
done
RESTORE=0; stop_all; log "restoring vLLM K3.25 serving"
if [ $DRY = 1 ]; then echo "DRY: $(start_v_cmd)" | tee -a "$LOG"; else
  bash -c "$(start_v_cmd)" > $R/logs/restore.log 2>&1 9>&-
  wait_vllm_ready && log "vLLM K3.25 ready" || log "vLLM K3.25 restore NOT ready: see $R/logs/restore.log"; fi
rs=$(ls $R/l/F-*-L3.json 2>/dev/null | tr '\n' ' ')
run "nice -n 10 python3 $CT/stage0/drivers/analyze_l.py $rs --out $R/l/L-analysis.json > $R/logs/analyze-l.log 2>&1" || log "Block L analyzer failed"
run "python3 -B $R/analysis/analyze_fa.py --l $R/l --ct $CT/l --out $R/analysis/FA-RESULT.json > $R/logs/fa-analysis.log 2>&1" || log "fa analysis failed"
log "chain done"
