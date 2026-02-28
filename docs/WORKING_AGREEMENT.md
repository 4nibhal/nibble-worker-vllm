# Working Agreement

## Core Operational Laws

1. Fork isolation: all automation, releases, and registry writes must target this fork only.
2. Absolute upstream prohibition: `runpod-workers/worker-vllm` is permanently out of scope; no interaction from this repo (sync, fetch, pull, rebase, merge, cherry-pick, PR, push).
3. Critical surface: treat `src/`, `Dockerfile`, `docker-bake.hcl`, `builder/requirements.txt`, and `.github/workflows/*` as high-impact paths.
4. Compatibility gate: any change on critical surface must include compatibility evidence for RunPod + vLLM runtime.
5. Deterministic release: releases must come from immutable tags and reproducible image tags; no floating release labels except explicit dev tags.
6. Minimal reversible changes: prefer smallest diff that solves objective and define rollback for each non-trivial change.
7. Evidence in PR notes: validation commands, outputs, and rollback notes are required in PR description.

## Definition Of Done

### Runtime Change (`src/`, `Dockerfile`, `docker-bake.hcl`, runtime env)

- Scope documented in PR.
- Required checks from `docs/VALIDATION_MATRIX.md` executed or marked manual with reason.
- RunPod + vLLM compatibility impact stated.
- Rollback step documented.

### CI/Release Change (`.github/workflows/*`, release logic)

- Trigger logic and permissions reviewed for least privilege.
- No upstream interaction of any kind from this repo (`runpod-workers/worker-vllm` stays out of scope).
- Dry-run or manual workflow verification evidence included.
- Rollback trigger and previous known-good tag identified.

### Dependency Update (`builder/requirements.txt`, base image pins)

- Version strategy stated (pin/range and reason).
- Compatibility risk called out (runtime, CUDA, vLLM, RunPod SDK).
- Validation evidence captured; unresolved checks marked manual.
- Revert path defined (exact prior version or tag).

### Governance/Docs Change (`AGENTS.md`, `aiwf*.json`, docs)

- Content aligns with current fork policy and does not alter runtime behavior.
- JSON/YAML/frontmatter parse checks pass where applicable.
- Cross-links updated if files/sections renamed.
- PR includes concise rationale for policy/process change.
