# Runtime Compatibility and Guardrails

This fork keeps runtime behavior compatible across mixed vLLM versions and RunPod env handling.

## vLLM AsyncEngineArgs compatibility

- Stable vLLM `0.17.0`: primary/default fork runtime path.
- Stable `0.17.0` is expected to expose `AsyncEngineArgs.language_model_only` for Qwen3.5 text-only startup.
- Default image path in this fork uses `VLLM_NIGHTLY=false` with `VLLM_VERSION=0.17.0`.
- Optional nightly fallback remains available with `VLLM_NIGHTLY=true` and pinned `VLLM_NIGHTLY_VERSION=0.17.0rc1.dev149+g40077ea3d`.
- Nightly path pins `transformers` by immutable commit via `TRANSFORMERS_REF=421c7f6248e28d24d84ee000252a1e71fbc24917` and installs from the corresponding GitHub archive tarball.
- Override mechanism: pass `--build-arg TRANSFORMERS_REF=<commit-sha>` (or set bake var `TRANSFORMERS_REF`) when validating a different transformers revision.
- Worker behavior: profile defaults are applied only when the target key exists in `AsyncEngineArgs.__dataclass_fields__`.
- Qwen3.5 guard: startup now fails fast with an actionable error if `MODEL_NAME` targets Qwen3.5 but runtime does not expose `language_model_only` or if `LANGUAGE_MODEL_ONLY` is not true.

## FlashInfer prefill reliability guard

- Root cause #1: Qwen3.5 runtime path imports `flashinfer` directly from `vllm/model_executor/models/qwen3_next.py`, so removing FlashInfer from image/runtime caused `ModuleNotFoundError: No module named 'flashinfer'` before engine args were applied.
- Root cause #2: when FlashInfer prefill JIT was actually reached, startup failed with `ninja ... gdn_prefill_sm90` exit `127` on images that lacked build tools (`nvcc`, `ninja`, C++ compiler).
- Fork default now keeps FlashInfer installed/available (`ENABLE_FLASHINFER=true`) and ships build tools in the runtime image (`ninja`, C++ compiler, nvcc-capable CUDA devel image path).
- Runtime guardrails remain explicit and deterministic:
  - `DISABLE_FLASHINFER_PREFILL=false` is the default posture for Qwen3.5-ready images.
  - Set `DISABLE_FLASHINFER_PREFILL=true` to force deterministic prefill fallback without changing package availability.
  - If `ATTENTION_BACKEND=FLASHINFER` is requested but required tools are missing at runtime probe, worker forces `FLASH_ATTN` and warns.
  - If `MODEL_NAME` is Qwen3.5 and FlashInfer module is missing anyway (custom image drift), startup fails fast with an actionable error.
- Qwen3.5 presets intentionally set `ENABLE_FLASHINFER=true`, `ATTENTION_BACKEND=FLASHINFER`, and `DISABLE_FLASHINFER_PREFILL=false` for coherent behavior with the toolchain-ready image.

## RunPod env value handling

RunPod stores environment values as strings in hub presets and endpoint config.

For optional override keys below, this fork uses explicit `"None"` in presets to represent unset:

- `NUM_GPU_BLOCKS_OVERRIDE`
- `MAX_CPU_LORAS`
- `MAX_PARALLEL_LOADING_WORKERS`

Runtime parsing treats `"None"`, `"none"`, and `""` as unset values.

Guardrail: literal `0` for these keys is forbidden and treated as invalid/unset behavior.

## OpenAI/OpenRouter payload compatibility

- Fork default now sets `RAW_OPENAI_OUTPUT=false` (structured JSON mode) for safer OpenAI/OpenRouter interoperability.
- Structured stream mode parses only SSE `data:` lines, ignores non-data control/comment lines, and preserves `data: [DONE]` as stream termination semantics.
- For both non-stream and structured stream responses, payload sanitation ensures stable key presence where possible without fabricating content:
  - top-level keys: `id`, `object`, `created`, `model`, `choices`
  - per-choice keys: `index`, `finish_reason`
- On malformed backend stream chunks, worker returns a structured error payload and logs full traceback details server-side.
- Raw passthrough remains opt-in via `RAW_OPENAI_OUTPUT=true`.

## CUDA host-driver compatibility

- Default container base is CUDA 12.6 devel (`CUDA_IMAGE_TAG=12.6.3-devel-ubuntu22.04`) with PyTorch wheels from `cu126`.
- This avoids `nvidia-container-cli: requirement error` on fleets where host drivers do not satisfy CUDA 12.8+.
- Devel image path preserves CUDA 12.6 runtime baseline while also exposing nvcc for FlashInfer JIT compatibility.
- For older hosts, keep CUDA runtime and wheel index aligned when building:
  - CUDA 12.4 hosts: `CUDA_IMAGE_TAG=12.4.1-devel-ubuntu22.04` and `PYTORCH_CUDA_INDEX=cu124`.
  - CUDA 12.6 hosts: keep defaults (`12.6.3-devel` and `cu126`).

## Deployment gate checklist

- Release safety note (nightly fallback only): nightly wheel artifacts can churn/disappear from `wheels.vllm.ai/nightly`; before creating a release tag that enables nightly, run `docker buildx bake --print` and confirm the pinned `VLLM_NIGHTLY_VERSION` still resolves in the nightly index.

Run this gate before release or endpoint cutover:

1. Startup check: worker boots successfully and engine args are accepted.
2. Inference check: run one known-good prompt through the deployed endpoint and confirm a valid response.

Recommended minimum command gate in this repo:

```bash
python -m py_compile src/*.py handler.py
python -c "import json; json.load(open('.runpod/hub.json')); json.load(open('aiwf.request.json')); print('json ok')"
python scripts/config_doctor.py
```
