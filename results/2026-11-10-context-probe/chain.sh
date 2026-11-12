#!/usr/bin/env bash
# Context probe chain (PROTOCOL.md sections 6-7, 13). One engine at a time on 127.0.0.1:8001.
#   chain.sh up <arm> <score|turn|serve>     start one CuteAFD v5 arm (stops vLLM first; makes the bench key if needed)
#   chain.sh down                            stop CuteAFD v5, shred the bench key
#   chain.sh restore                         down, then start the vLLM recipe again and check it by request
#   chain.sh layer1 [arms...]                step A: per arm, launch, capture r0 and r1 on both paths, stop; then restore
#   chain.sh turncheck [arms...]             step B: per arm, launch, conversations (turncheck-plan.sh), stop; restore
#   chain.sh ab                              steps A and B back to back, one restore at the end
#   chain.sh ab2                             the same with assistant-frame texts: a0 all arms, a1 anchor+hqa, turn check
#   chain.sh pilot                           step P (exploratory): hqa single x2 + turns p8 on the pilot items, then anchor at 128k only
#   chain.sh tasks [arms...]                 steps C and D (measured, needs FROZEN.json): single rep 0, single rep 1, turns p8, each across the arms
#   chain.sh reference [arms...]             reference checkpoints added after the results were read: single rep 0 and rep 1 only (default exlr8-k4)
#   chain.sh extend [arms...]                amendment 1 (AMENDMENT-2026-11-11.md): single rep 2 and rep 3, each across anchor hqa compact exlr8-k4
#   chain.sh capext [arms...]                assistant-frame capture a0 on exlr8-k4 (exploratory), then extend; one restore at the end
# Long stages run under systemd-run --user. No `set -e`: exit codes are checked explicitly. Every exit path of a
# stage shreds the key and restores vLLM.
R=<runs>/2026-11-10-context-probe; D=$R/drivers; S=<stacks>/cuteafd-v5
PY=<runs>/2026-10-27-long-context-pilot2/.venv/bin/python
KEY=<secrets>/bench-api-key
CC=cuteafd-coordinator-local-v5; VC=glm53-flash-exl3-b12x-vllm; VS=<vllm-stack>
VRECIPE="<serving-recipe>"
LOG=$R/logs/chain.log
export HF_HOME=<hf-home> PYTHONDONTWRITEBYTECODE=1
log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }

arm_cfg(){ # sets CFG (config base name) and SETS (launcher --set arguments) for an arm
  SETS=(); NSROOT=
  case $1 in
    hqa)      CFG=glm53-flash-exl3-k4-core-k6-hqa-2rtx ;;
    hqa-bf16pre) CFG=glm53-flash-exl3-k4-core-k6-hqa-2rtx; SETS=(--set GLM5_FLASH_FP8_PREFILL=off) ;;
    compact)  CFG=glm53-flash-exl3-k4-core-k6-hqa-2rtx; SETS=(--set ATTENTION_MODE=compact) ;;
    fp8c)     CFG=glm53-flash-exl3-k4-core-k6-hqa-2rtx; SETS=(--set ATTENTION_MODE=fp8-compact) ;;
    core-fp8) CFG=glm53-flash-exl3-k4-core-k6-bf16core-2rtx ;;
    anchor)   CFG=glm53-flash-exl3-k4-core-k6-bf16core-2rtx
              SETS=(--set GLM5_FLASH_KDA_FP8=off --set GLM5_FLASH_FP8_HEAD=off --set GLM5_FLASH_FP8_PREFILL=off) ;;
    # reference checkpoint added 2026-11-11 (see `reference` below). The engine loads native EXLR8 experts only
    # from a SparkNest store, so this arm alone reads its snapshot through the one-host store's mount.
    exlr8-k4) CFG=glm53-flash-exlr8-k4-2rtx; NSROOT=<stacks>/sparknest/mnt ;;
    # fifth configuration added 2026-11-12 (AMENDMENT-2026-11-12.md, stage script amend2.sh): the engine's
    # release-default checkpoint for this model, EXL3 K3.25 routed experts with the official FP8 core blocks.
    k325-fp8) CFG=glm53-flash-exl3-k3.25-core-fp8-2rtx ;;
    *) log "unknown arm $1"; return 1 ;;
  esac; }
make_key(){ ( umask 077; mkdir -p "$(dirname $KEY)" && head -c 32 /dev/urandom | base64 | tr -d '/+=\n' > $KEY ); }
shred_key(){ [ -f $KEY ] && { shred -u $KEY 2>/dev/null || rm -f $KEY; log "bench key shredded"; }; return 0; }
stop_cute(){ docker ps -q -f "name=^$CC\$" | grep -q . && { (cd $S && ./stop.sh --config local/glm53-flash-exl3-k4-core-k6-hqa-2rtx.config) >> "$LOG" 2>&1
    docker ps -q -f "name=^$CC\$" | grep -q . && docker stop $CC >> "$LOG" 2>&1; }
  # an engine that exited during initialization keeps its name and blocks the next launch
  docker ps -aq -f "name=^$CC\$" -f status=exited | grep -q . && docker rm $CC >> "$LOG" 2>&1; return 0; }
stop_vllm(){ docker ps -q -f "name=^$VC\$" | grep -q . && { (cd $VS && ./stop.sh) >> "$LOG" 2>&1; sleep 5; }; return 0; }
gpu_clear(){ # compute apps other than desktop clients must be gone; the full listing (graphics clients too) is kept
  nvidia-smi > "$R/logs/nvidia-smi-before-$1.txt" 2>&1
  local others
  others=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | grep . |
           grep -v -E 'snapd-desktop-integration|desktop-app|gnome-shell|Xwayland|xdg-desktop-portal')
  [ -z "$others" ] || { log "compute apps still on the GPUs, refusing to start $1: $(echo "$others" | tr '\n' ';')"; return 1; }
  log "GPUs before $1: $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ';')"; return 0; }
wait_models(){ # $1 timeout s, $2 use key (1/0)
  local t=0 h=(); [ "$2" = 1 ] && h=(-H "Authorization: Bearer $(cat $KEY)")
  until curl -sf --max-time 5 "${h[@]}" http://127.0.0.1:8001/v1/models > /dev/null 2>&1; do
    sleep 5; t=$((t+5)); docker ps -q -f "name=^$CC\$" | grep -q . || [ $t -lt 60 ] || return 2; [ $t -ge "$1" ] && return 1; done; return 0; }
up(){ # $1 arm, $2 form
  local arm=$1 form=$2 tag="$1-$2-$(date +%H%M%S)" extra=() cfg usekey=1
  arm_cfg "$arm" || return 1
  stop_vllm; stop_cute; gpu_clear "$tag" || return 1
  case $form in
    score) cfg=$CFG-score; mkdir -p $R/depth/dumps; extra=(--set PROBE_DUMP_ROOT=$R/depth/dumps) ;;
    turn)  cfg=$CFG; mkdir -p $R/turncheck/dumps
           extra=(--set ENABLE_BENCH=on --set API_KEY_FILE=$KEY --set PROBE_DUMP_ROOT=$R/turncheck/dumps) ;;
    serve) cfg=$CFG; usekey=0 ;;
    *) log "unknown form $form"; return 1 ;;
  esac
  [ $usekey = 1 ] && { [ -f $KEY ] || make_key; }
  log "starting $arm ($form): $cfg ${SETS[*]} ${extra[*]}"
  if [ -n "$NSROOT" ]; then
    mountpoint -q "$NSROOT" || { log "store not mounted at $NSROOT"; return 1; }
    (cd $S && CUTEAFD_NAMESPACE_ROOT=$NSROOT ./run.sh --config local/$cfg.config "${SETS[@]}" "${extra[@]}") > "$R/logs/$tag.start.log" 2>&1
  else
    (cd $S && ./run.sh --config local/$cfg.config "${SETS[@]}" "${extra[@]}") > "$R/logs/$tag.start.log" 2>&1
  fi
  local rc=$?; [ $rc = 0 ] || { log "launcher exit $rc: see logs/$tag.start.log"; return $rc; }
  ( docker logs -f $CC > "$R/logs/$tag.server.log" 2>&1 & )
  wait_models 1800 $usekey; rc=$?
  [ $rc = 0 ] || { log "$arm ($form) not ready (rc $rc): see logs/$tag.server.log"; return $rc; }
  echo "$tag" > $R/logs/CURRENT; log "$arm ($form) ready, tag $tag"; return 0; }
down(){ stop_cute; shred_key; }
restore(){ down; docker ps -q -f "name=^$VC\$" | grep -q . && { log "vLLM already up"; return 0; }
  log "restoring vLLM recipe"; bash -c "source '$VRECIPE/env.sh' && cd $VS && ./local-start.sh" > "$R/logs/restore-$(date +%H%M%S).log" 2>&1
  local t=0; until docker logs $VC 2>&1 | grep -q 'container is ready'; do sleep 10; t=$((t+10))
    [ $t -ge 3600 ] && { log "vLLM restore NOT ready after 1 h"; return 1; }; done
  local m; m=$(curl -s --max-time 10 http://127.0.0.1:8001/v1/models | $PY -c "import json,sys;print(json.load(sys.stdin)['data'][0]['id'])")
  local out; out=$(curl -s --max-time 120 http://127.0.0.1:8001/v1/chat/completions -H 'Content-Type: application/json' \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: ready\"}],\"max_tokens\":32}" |
    $PY -c "import json,sys;print(repr(json.load(sys.stdin)['choices'][0]['message']['content'])[:80])")
  log "vLLM restored: model $m, reply $out"; }

stage_exit(){ local rc=$?; log "stage exit $rc"; restore; }

layer1(){ # captures; comparisons are run separately (CPU only). r1 is a separate launch of each arm, so r0 vs r1
  # is a launch-to-launch floor (within one launch the decode path and cold prefill are already bit-identical).
  local arms=("$@"); [ ${#arms[@]} = 0 ] && arms=(anchor core-fp8 hqa hqa-bf16pre compact fp8c)
  for tag in ${TAGS:-r0 r1}; do for arm in "${arms[@]}"; do
    up "$arm" score || { log "layer1: $arm did not start; continuing with the next arm"; down; continue; }
    for path in prefill decode; do
      $PY -B $D/depth_profile.py capture --arm "$arm" --run-tag $tag --path $path --frame ${FRAME:-user} --dump-root $R/depth/dumps >> "$R/logs/layer1-$arm.log" 2>&1
      rc=$?; log "layer1 $arm $tag $path: exit $rc"
    done
    down
  done; done; }

turncheck(){
  local arms=("$@"); [ ${#arms[@]} = 0 ] && arms=(hqa hqa-bf16pre compact fp8c)
  for arm in "${arms[@]}"; do
    up "$arm" turn || { log "turncheck: $arm did not start; continuing"; down; continue; }
    bash $R/turncheck-plan.sh "$arm" >> "$R/logs/turncheck-$arm.log" 2>&1; log "turncheck $arm: exit $?"
    down
  done; }

ab(){ layer1; turncheck; }   # steps A and B back to back, one restore at the end
# assistant-frame texts: one capture of all six arms (a0), a second launch of two (a1), then the turn check
ab2(){ FRAME=asst TAGS=a0 layer1; FRAME=asst TAGS=a1 layer1 anchor hqa; turncheck; }

tasks_run(){ # $1 arm (already up in serve form), rest: run_tasks.py arguments
  local arm=$1; shift
  $PY -B $D/run_tasks.py --arm "$arm" "$@" >> "$R/logs/tasks-$arm.log" 2>&1; log "tasks $arm $*: exit $?"; }
# Step P, exploratory, pilot items. Cap 32,768 so the reply-length distribution is seen before a cap is chosen.
# hqa: two single repeats (a first flip floor) and one 8-part run. anchor has the smallest KV pool (1.32M tokens),
# so the 128k items alone are run on it at the same concurrency: does that concurrency fit the tightest arm?
pilot(){
  local c=${PILOT_CONCURRENCY:-8} common=(--run-tag p0 --set pilot --max-tokens 32768 --exploratory)
  if up hqa serve; then
    tasks_run hqa "${common[@]}" --concurrency $c --mode single --rep 0
    tasks_run hqa "${common[@]}" --concurrency $c --mode single --rep 1
    tasks_run hqa "${common[@]}" --concurrency $c --mode turns --parts 8 --rep 0
  fi; down
  if up anchor serve; then
    tasks_run anchor "${common[@]}" --concurrency $c --mode single --rep 0 --lengths 128k
    tasks_run anchor "${common[@]}" --concurrency $c --mode turns --parts 8 --rep 0 --lengths 128k
  fi; down; }

tasks(){ # measured set under the frozen protocol (section 13): by pass across the arms; reruns resume finished units
  local arms=("$@") common=(--run-tag m0 --set measured --max-tokens 32768 --concurrency 8) pass arm
  [ ${#arms[@]} -eq 0 ] && arms=(anchor hqa compact)
  for pass in "single 0" "single 1" "turns 0"; do
    set -- $pass
    for arm in "${arms[@]}"; do
      if up "$arm" serve; then
        if [ "$1" = turns ]; then tasks_run "$arm" "${common[@]}" --mode turns --parts 8 --rep "$2"
        else tasks_run "$arm" "${common[@]}" --mode single --rep "$2"; fi
      fi; down
    done
  done; }
# Reference checkpoints, added 2026-11-11 after the measured results were read (not part of the frozen comparison):
# the two single-message passes only, same items, seeds, cap and concurrency, one launch per pass.
reference(){
  local arms=("$@") common=(--run-tag m0 --set measured --max-tokens 32768 --concurrency 8) rep arm
  [ ${#arms[@]} -eq 0 ] && arms=(exlr8-k4)
  for rep in 0 1; do for arm in "${arms[@]}"; do
    if up "$arm" serve; then tasks_run "$arm" "${common[@]}" --mode single --rep $rep; fi; down
  done; done; }
# Amendment 1 (AMENDMENT-2026-11-11.md), decided after the two-pass results were read: the total is fixed at four
# single-message passes per arm. Same items, cap and concurrency; rep 2 and rep 3 are new seed blocks.
extend(){
  local arms=("$@") common=(--run-tag m0 --set measured --max-tokens 32768 --concurrency 8) rep arm
  [ ${#arms[@]} -eq 0 ] && arms=(anchor hqa compact exlr8-k4)
  [ -f $R/AMENDMENT-2026-11-11.md ] || { log "extend: amendment file missing, not starting"; return 1; }
  for rep in ${REPS:-2 3}; do for arm in "${arms[@]}"; do
    if up "$arm" serve; then tasks_run "$arm" "${common[@]}" --mode single --rep $rep
    else log "extend: $arm did not start for rep $rep"; fi; down
  done; done; }
capext(){ FRAME=asst TAGS=a0 layer1 exlr8-k4; extend "$@"; }
cmd=$1; shift
case $cmd in
  up|down|restore) $cmd "$@" ;;
  layer1|turncheck|ab|ab2|pilot|tasks|reference|extend|capext) trap stage_exit EXIT; trap 'log interrupted; exit 130' INT TERM; $cmd "$@" ;; *) sed -n 2,14p "$0"; exit 2 ;; esac
