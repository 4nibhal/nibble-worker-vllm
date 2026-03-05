# Runtime Compatibility and Guardrails

This fork keeps runtime behavior compatible across mixed vLLM versions and RunPod env handling.

## vLLM AsyncEngineArgs compatibility

- Stable vLLM `0.16.0`: `language_model_only` is not available in `AsyncEngineArgs`.
- Fork pinned nightly `0.16.1rc1.dev257+g3b23d57c9`: `language_model_only` is available for Qwen3.5 text-only startup.
- Default image path in this fork uses `VLLM_NIGHTLY=true` with `VLLM_NIGHTLY_VERSION=0.16.1rc1.dev257+g3b23d57c9`.
- Default nightly path pins `transformers` by immutable git ref via `TRANSFORMERS_REF=421c7f6248e28d24d84ee000252a1e71fbc24917`.
- Stable override remains supported via `VLLM_NIGHTLY=false` and `VLLM_VERSION=0.16.0`.
- Override mechanism: pass `--build-arg TRANSFORMERS_REF=<commit-sha>` (or set bake var `TRANSFORMERS_REF`) when validating a different transformers revision.
- Worker behavior: profile defaults are applied only when the target key exists in `AsyncEngineArgs.__dataclass_fields__`.
- Qwen3.5 guard: startup now fails fast with an actionable error if `MODEL_NAME` targets Qwen3.5 but runtime does not expose `language_model_only` or if `LANGUAGE_MODEL_ONLY` is not true.

## FlashInfer prefill reliability guard

- Root cause observed on some H100 runtime paths: FLASHINFER prefill triggers JIT compile (`ninja ... gdn_prefill_sm90`) and exits `127` when nvcc/toolchain binaries are missing.
- Long-term fork policy: FlashInfer is hard-disabled by default at image/runtime level via `ENABLE_FLASHINFER=false`.
- Build behavior with `ENABLE_FLASHINFER=false` removes `flashinfer`/`flashinfer-python` from the runtime image so FlashInfer is not active/available by default.
- Runtime behavior stays deterministic: default `DISABLE_FLASHINFER_PREFILL=true` and `ATTENTION_BACKEND=FLASH_ATTN` unless explicit safe opt-in conditions are satisfied.
- If `ATTENTION_BACKEND=FLASHINFER` is requested while `ENABLE_FLASHINFER=false` or `DISABLE_FLASHINFER_PREFILL=true`, worker overrides to `FLASH_ATTN` with a warning.
- If user explicitly opts in but toolchain probe cannot find `nvcc`, `ninja`, or a C++ compiler, worker still forces `FLASH_ATTN` and warns.
- Explicit opt-in path (advanced, toolchain-ready only):
  - Build image with `--build-arg ENABLE_FLASHINFER=true`.
  - Set endpoint env `ENABLE_FLASHINFER=true`, `FLASHINFER_TOOLCHAIN_READY=true`, `DISABLE_FLASHINFER_PREFILL=false`, and `ATTENTION_BACKEND=FLASHINFER`.

## RunPod env value handling

RunPod stores environment values as strings in hub presets and endpoint config.

For optional override keys below, this fork uses explicit `"None"` in presets to represent unset:

- `NUM_GPU_BLOCKS_OVERRIDE`
- `MAX_CPU_LORAS`
- `MAX_PARALLEL_LOADING_WORKERS`

Runtime parsing treats `"None"`, `"none"`, and `""` as unset values.

Guardrail: literal `0` for these keys is forbidden and treated as invalid/unset behavior.

## CUDA host-driver compatibility

- Default container base is CUDA 12.6 (`CUDA_IMAGE_TAG=12.6.3-base-ubuntu22.04`) with PyTorch wheels from `cu126`.
- This avoids `nvidia-container-cli: requirement error` on fleets where host drivers do not satisfy CUDA 12.8+.
- Runtime image path does not assume full CUDA build toolchain availability at startup; this is why FLASHINFER prefill JIT is guarded by default.
- For older hosts, keep CUDA runtime and wheel index aligned when building:
  - CUDA 12.4 hosts: `CUDA_IMAGE_TAG=12.4.1-base-ubuntu22.04` and `PYTORCH_CUDA_INDEX=cu124`.
  - CUDA 12.6 hosts: keep defaults (`12.6.3` and `cu126`).

## Deployment gate checklist

Run this gate before release or endpoint cutover:

1. Startup check: worker boots successfully and engine args are accepted.
2. Inference check: run one known-good prompt through the deployed endpoint and confirm a valid response.

Recommended minimum command gate in this repo:

```bash
python -m py_compile src/*.py handler.py
python -c "import json; json.load(open('.runpod/hub.json')); json.load(open('aiwf.request.json')); print('json ok')"
python scripts/config_doctor.py
```
