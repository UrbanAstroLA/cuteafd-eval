#!/usr/bin/env bash
# Thinking-length experiment, GPU session (PLAN.md): G1b (on-policy traces on the knife-edge questions) then G2 (screen:
# K4-Core-K6 core as rebuilt, all-BF16 core, and 9 groups swapped to BF16 one at a time; reduced captures of P-A, the
# looping-probe traces and the G1b traces on every arm). vLLM K3.25 serving restored at the end and on every exit path.
# No `set -e`: every exit code checked. Engine starts only through start-v092x-swap-capture.sh (frozen in FROZEN.json).
#   ./chain-g.sh            run   (inside: systemd-run --user --unit=local-thinking-g2 ...)
R=<tl-run>
LOG=$R/logs/chain-g.log; TEL=$R/tel; DUMPS=$R/dumps; REG=$R/traces/reg
mkdir -p $R/logs $TEL $DUMPS/staging/pa $DUMPS/staging/tr $DUMPS/staging/on $DUMPS/runs $R/g1b
PYV=<venv>/bin/python
CAP="$PYV -B $R/capture/capture.py --registry $REG --out-dir $DUMPS"
W=$R/start-v092x-swap-capture.sh
XIMG_ID=sha256:5fc05b7c1b477196db77644b0d7654c7f8d0f52c77b6d008fa2b421802f3a43c
VC=glm53-flash-exl3-b12x-vllm
CLEANENV="env -i HOME=$HOME USER=$USER LOGNAME=$USER PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8"
exec 9>"$R/.chain.lock"; flock -n 9 || { echo "chain already running"; exit 75; }
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

python3 -c "import json,hashlib,sys; f=json.load(open('$R/FROZEN.json')); [sys.exit(f'changed: {p}') for p,h in f['files'].items() if hashlib.sha256(open(p,'rb').read()).hexdigest()!=h]" || exit 2
log "frozen inputs verified"
nvidia-smi --query-gpu=timestamp,index,power.draw,temperature.gpu,utilization.gpu,memory.used --format=csv -l 5 >> $TEL/gpu.csv 2>&1 9>&- & TPID=$!
stop_all

# ---- arm k6 (K4-Core-K6 core rebuilt by route b, no swap): G1b generation, on-policy set, captures
launch k6 k6 "" 0 || exit 1
run "python3 $R/drivers/gen_traces.py --out $R/g1b --budget-s 9000 > $R/logs/g1b.log 2>&1" || log "G1b generator exited non-zero (kept)"
run "$R/traces/run_build.sh -v $R/g1b:/g1b:ro -e SET=on -e SRC_GLOB='/g1b/doc*_rep*.json' -e CK_ALL=K4-Core-K6 -e DOCS=186,12,81,120,86,74,13 -e FIN_PER_DOC=6 -e NON_PER_DOC=2 > $R/logs/build-on.log 2>&1" || log "on-policy set not built (G2 continues with pa and tr)"
capture_all k6 || log "k6 captures incomplete"
stop_all

# ---- swap arms: tag, swap set, expected swapped matrices
for spec in "all:all:316" "kda_qkv:kda_q,kda_k,kda_v:102" "kda_o:kda_o:34" "mla_a:mla_q_a,mla_kv_a:22" "mla_q_b:mla_q_b:11" \
            "mla_o:mla_o:11" "dense:dense_gate_up,dense_down:9" "shared_gu:shared_gate_up:84" "shared_down:shared_down:42" \
            "lm_head:lm_head:1"; do
  IFS=: read -r tag set n <<< "$spec"
  launch $tag k6swap "$set" $n || { log "arm $tag skipped (launch)"; stop_all; continue; }
  capture_all $tag || log "$tag captures incomplete"
  stop_all
done

run "$PYV -B $R/analysis/score_stop.py --dumps $DUMPS/runs --reg $REG --base k6 --ref all --teacher <datasets>/glm53-flash-teacher-logits --pa-meta <run>/stage0/scorers/plans/pa.meta.json --out $R/analysis/G2-SCORES.json > $R/logs/score.log 2>&1" || log "scoring failed (rerun on CPU)"
log "G1b + G2 done"
