---
scope: "/"
type: "rules"
role: "Repository Governance"
priority: critical
metadata:
  system: "opencode"
  repo_intent: "consumer"
---

# Repository Rules

## Core Policy
- [Task affects upstream runpod-workers/worker-vllm directly] -> [FORBIDDEN; implement and validate in this fork only]
- [Request mentions upstream sync/rebase/merge/cherry-pick/fetch/pull against runpod-workers/worker-vllm] -> [OUT OF SCOPE and FORBIDDEN; do not interact with upstream from this repository]
- [Change/release flow targets remotes] -> [Use fork remote (origin) only for write operations and releases; upstream is manual read-only reference]
- [Publishing build/release artifacts] -> [REQUIRED: push/tag/release only on origin; never publish from or to upstream]
- [Change not required for objective] -> [DO NOT modify]

## Canonical References (Source Of Truth)
- RunPod Serverless overview: https://docs.runpod.io/serverless/overview
- RunPod vLLM overview: https://docs.runpod.io/serverless/vllm/overview
- RunPod vLLM environment variables: https://docs.runpod.io/serverless/vllm/environment-variables
- vLLM docs: https://docs.vllm.ai/
- vLLM repository/tags: https://github.com/vllm-project/vllm
- Qwen3.5-27B model card: https://huggingface.co/Qwen/Qwen3.5-27B

## Scope Boundaries
- [Path starts with ai-workflow/] -> [Treat as framework source; do not modify unless explicitly requested]
- [Request targets root runtime artifacts] -> [Prefer AGENTS.md, aiwf.config.json, aiwf.request.json, .aiwf/session/*]
- [Secrets or credentials appear in task] -> [Refuse persistence; require redaction or env injection]

## CI And Container Boundaries
- [Change touches .github/workflows/*] -> [Allowed only for this fork's CI behavior; do not mirror upstream assumptions automatically]
- [Change touches Dockerfile, docker-bake.hcl, builder/*] -> [Require explicit compatibility checks for RunPod + vLLM runtime]
- [Critical runtime change is present and no new release tag is planned] -> [Block deploy/release until a new release tag is defined]
- [Preparing release candidate] -> [Run validation gate: py_compile, basic JSON schema/validation, docker buildx bake --print]
- [Container/CI change lacks rollback note in request contract] -> [Block completion until rollback plan is defined]

## Runtime Guardrails
- [Setting optional vLLM env NUM_GPU_BLOCKS_OVERRIDE, MAX_CPU_LORAS, or MAX_PARALLEL_LOADING_WORKERS to 0] -> [FORBIDDEN; use empty/unset value instead]
- [Using pre-release/nightly dependency] -> [Pin exact nightly/pre-release version; do not use floating ranges]
- [Runtime/container/versioning decision is made] -> [Validate against Canonical References and record exact versions in docs/runtime-compatibility.md]
- [Claim about package/version support is uncertain] -> [Treat as unverified; check source docs/release metadata before changing defaults]
- [Model size is >=14B or unknown and RUNTIME_PROFILE is not explicit] -> [Default RUNTIME_PROFILE=safe]
- [max_model_len is profile/auto-computed and model-derived context limit is available] -> [Clamp max_model_len to derived context limit; MUST NOT exceed it]
- [Model size inference from model id is required] -> [Support common size suffixes at least B and M; unknown remains safe path]
- [Model family is Qwen 3.5 and MODEL_PROFILE override is not explicit] -> [Force MODEL_PROFILE=qwen3_5_27b]
- [Model family is Qwen 3.5 on runtime path] -> [Keep LANGUAGE_MODEL_ONLY=true and use a vLLM build that exposes AsyncEngineArgs.language_model_only]
- [Large-context runtime path and no explicit escape hatch] -> [Keep ENABLE_CHUNKED_PREFILL=true]
- [Production runtime requires Hugging Face auth token] -> [Prefer HUGGINGFACE_ACCESS_TOKEN or supported token aliases]
- [Concurrency tuning plan is unspecified] -> [Start conservative and scale in stages 1->2->4]
- [No CUDA device is available and DEVICE is not explicit] -> [Default DEVICE=cpu for startup compatibility checks]
- [CUDA appears available but runtime probe fails and DEVICE is not explicit] -> [Treat CUDA as unavailable and fallback to DEVICE=cpu]
- [Startup fails on vLLM ModelConfig max_model_len validation] -> [Block rollout/release until profile defaults are adjusted or explicit override rationale is documented]

## Delegation Guidance
- [Work is multi-step, cross-file, or validation-heavy] -> [Delegate to specialized sub-agents; keep orchestrator as reviewer]
- [Work is single-file mechanical edit] -> [Direct execution allowed without delegation]
- [Delegation instruction is ambiguous] -> [Block agent creation, keep execution delegation enabled, request precise clarification only if outcome changes]

## Governance Contract
- [Any non-trivial implementation request] -> [Record objective, scope, acceptance_criteria, tests_expected, rollback_plan in aiwf.request.json]
- [Risk tier is T2-high] -> [Require threat_model + deploy_plan + rollback_plan before build]
- [Audit-relevant decision made] -> [Capture rationale in commit/PR notes; keep .aiwf/audit/** internal-only]

## Capability Graph
- @skill/fork-sync-guard

## Auto-invoke Skills

| Action | Skill |
|--------|-------|
| Any request mentioning upstream parity/sync/rebase/merge/cherry-pick/fetch/pull | [`fork-sync-guard`](/.opencode/skills/fork-sync-guard/SKILL.md) |

## Specialized Sub-agents (OpenCode Executables)

| Domain / Trigger | Agent (Executable) |
|------------------|--------------------|
| RunPod + vLLM runtime compatibility checks for `src/`, `builder/requirements.txt`, `Dockerfile`, `docker-bake.hcl` | [`runpod-runtime-guardian`](/.opencode/agent/runpod-runtime-guardian.md) |
| CI workflow and release automation hardening with least-privilege + deterministic tags | [`ci-release-engineer`](/.opencode/agent/ci-release-engineer.md) |
