#!/usr/bin/env bash
# "vLLM fork v0.9.2-experimental": sources this stack's pinned environment, then runs tpurtell's v0.9.0
# launcher (start.sh in <vllm-stack>) unmodified. Source a recipe's env.sh first.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./local-env.sh
exec <vllm-stack>/start.sh "$@"
