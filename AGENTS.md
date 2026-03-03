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
- [Change not required for objective] -> [DO NOT modify]

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
- [Model size is >=14B or unknown and RUNTIME_PROFILE is not explicit] -> [Default RUNTIME_PROFILE=safe]
- [Model family is Qwen 3.5 and MODEL_PROFILE override is not explicit] -> [Force MODEL_PROFILE=qwen3_5_27b]
- [Large-context runtime path and no explicit escape hatch] -> [Keep ENABLE_CHUNKED_PREFILL=true]
- [Production runtime requires Hugging Face auth token] -> [Prefer HUGGINGFACE_ACCESS_TOKEN or supported token aliases]
- [Concurrency tuning plan is unspecified] -> [Start conservative and scale in stages 1->2->4]

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
