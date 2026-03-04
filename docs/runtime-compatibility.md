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
