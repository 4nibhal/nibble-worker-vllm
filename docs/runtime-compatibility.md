# Runtime Compatibility and Guardrails

This fork keeps runtime behavior compatible across mixed vLLM versions and RunPod env handling.

## vLLM AsyncEngineArgs compatibility

- vLLM `<0.16.1rc0`: `language_model_only` is not available in `AsyncEngineArgs`.
- vLLM `>=0.16.1rc0`: `language_model_only` is supported.
- Worker behavior: profile defaults are applied only when the target key exists in `AsyncEngineArgs.__dataclass_fields__`.

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
