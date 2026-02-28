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
- [Change not required for objective] -> [DO NOT modify]

## Scope Boundaries
- [Path starts with ai-workflow/] -> [Treat as framework source; do not modify unless explicitly requested]
- [Request targets root runtime artifacts] -> [Prefer AGENTS.md, aiwf.config.json, aiwf.request.json, .aiwf/session/*]
- [Secrets or credentials appear in task] -> [Refuse persistence; require redaction or env injection]

## CI And Container Boundaries
- [Change touches .github/workflows/*] -> [Allowed only for this fork's CI behavior; do not mirror upstream assumptions automatically]
- [Change touches Dockerfile, docker-bake.hcl, builder/*] -> [Require explicit compatibility checks for RunPod + vLLM runtime]
- [Container/CI change lacks rollback note in request contract] -> [Block completion until rollback plan is defined]

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
