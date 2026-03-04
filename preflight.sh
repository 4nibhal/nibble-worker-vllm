#!/usr/bin/env bash
set -euo pipefail

WITH_BUILD=0
MODEL_ID=""

usage() {
  cat <<'EOF'
Usage: ./preflight.sh [--with-build] [--model <HF_MODEL_ID>] [--help]

Low-cost default checks (fast/local):
  - python -m py_compile src/*.py handler.py
  - lightweight runtime config contracts via scripts/config_doctor.py
  - docker buildx bake --print (writes output to /tmp)

Optional heavier checks:
  --with-build         Also run docker build (costly)
  --model <HF_MODEL_ID>
                       Run runtime-arg preflight using MODEL_NAME and
                       print selected runtime/max_model_len values

Examples:
  ./preflight.sh
  ./preflight.sh --with-build --model "HuggingFaceTB/SmolLM2-135M-Instruct"
EOF
}

run_step() {
  local step_name="$1"
  shift

  if "$@"; then
    echo "PASS: ${step_name}"
  else
    echo "FAIL: ${step_name}" >&2
    exit 1
  fi
}

check_py_compile() {
  python -m py_compile src/*.py handler.py
}

check_config_doctor() {
  python scripts/config_doctor.py
}

check_bake_print() {
  local bake_output="/tmp/nibble-worker-vllm-preflight-bake.txt"
  docker buildx bake --print >"${bake_output}"
  echo "bake plan saved to ${bake_output}"
}

check_model_engine_args() {
  MODEL_NAME="${MODEL_ID}" python - <<'PY'
import os
from src.engine_args import get_engine_args

args = get_engine_args()
print(f"MODEL_NAME={os.getenv('MODEL_NAME')}")
print(f"MODEL_PROFILE_ENV={os.getenv('MODEL_PROFILE', 'auto') or 'auto'}")
print(f"RUNTIME_PROFILE_ENV={os.getenv('RUNTIME_PROFILE', 'auto') or 'auto'}")
print(f"max_model_len={getattr(args, 'max_model_len', None)}")
print(f"max_num_batched_tokens={getattr(args, 'max_num_batched_tokens', None)}")
print(f"max_num_seqs={getattr(args, 'max_num_seqs', None)}")
print(f"gpu_memory_utilization={getattr(args, 'gpu_memory_utilization', None)}")
print(f"enable_chunked_prefill={getattr(args, 'enable_chunked_prefill', None)}")
PY
}

check_docker_build() {
  docker build --platform linux/amd64 -t nibble-worker-vllm:preflight .
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-build)
      WITH_BUILD=1
      shift
      ;;
    --model)
      if [[ $# -lt 2 ]]; then
        echo "FAIL: --model requires a value" >&2
        usage
        exit 1
      fi
      MODEL_ID="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "FAIL: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

echo "Running preflight (default low-cost checks)."
run_step "python compile" check_py_compile
run_step "config doctor" check_config_doctor
run_step "docker bake print" check_bake_print

if [[ -n "${MODEL_ID}" ]]; then
  run_step "runtime arg preflight (${MODEL_ID})" check_model_engine_args
fi

if [[ "${WITH_BUILD}" -eq 1 ]]; then
  run_step "docker build linux/amd64" check_docker_build
fi

echo "PASS: preflight complete"
