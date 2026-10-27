#!/usr/bin/env bash
# Two vLLM v0.9.2 starts with the JIT caches persisted (local-env.sh DEBUG_ENV); phase timings from the log.
R=<runs>/2026-10-27-vllm-startup-cache; C=glm53-flash-exl3-b12x-vllm
phase() { # $1 = label
  local L=$R/$1-docker.log; docker logs -t $C > $L 2>&1
  local s=$(docker inspect -f '{{.State.StartedAt}}' $C)
  python3 - "$L" "$s" "$1" <<'PY' >> $R/RESULTS.txt
import sys,re,datetime as dt
L,start,label=sys.argv[1:]
def t(x): return dt.datetime.fromisoformat(x[:26].replace('Z',''))
t0=t(start); lines=open(L,errors='replace').read().splitlines()
def first(p):
    for l in lines:
        if re.search(p,l): return (t(l.split()[0])-t0).total_seconds(), l
    return None,None
def last(p):
    r=None
    for l in lines:
        if re.search(p,l): r=(t(l.split()[0])-t0).total_seconds()
    return r
w=re.search(r'Loading weights took ([\d.]+)', open(L,errors='replace').read())
tl=sum(1 for l in lines if 'TileLang begins to compile' in l)
g=re.search(r'Graph capturing finished in (\d+) secs', open(L,errors='replace').read())
ready,_=first('startup warmup complete')
print(f"{label}: ready {ready:.0f}s after container start; weights {w.group(1) if w else '?'}s; TileLang compiles {tl} "
      f"(first {first('TileLang begins')[0]}, last {last('TileLang completes')}); graph capture {g.group(1) if g else '?'}s")
PY
}
: > $R/RESULTS.txt
phase run0-baseline-uncached
for run in run1-populate run2-warm; do
  docker stop $C >/dev/null 2>&1; docker rm $C >/dev/null 2>&1
  (cd <vllm-stack> && bash -c 'source "<recipes>/glm53-flash-exl3-k3.25@tpurtell+v0.9.2/env.sh" && ./local-start.sh' > $R/$run-start.log 2>&1) || { echo "$run start failed" >> $R/RESULTS.txt; exit 1; }
  until docker logs $C 2>&1 | grep -q 'startup warmup complete; container is ready'; do docker ps -q -f name=^$C$ | grep -q . || { echo "$run container exited" >> $R/RESULTS.txt; exit 1; }; sleep 10; done
  phase $run
  docker exec $C sh -c 'env | grep -E "TILELANG_CACHE_DIR|TRITON_CACHE_DIR|TORCHINDUCTOR_CACHE_DIR|CUDA_CACHE_PATH"' >> $R/RESULTS.txt
  du -sh <cache>/vllm-v090/* >> $R/RESULTS.txt 2>&1
done
echo "done $(date -Is)" >> $R/RESULTS.txt
