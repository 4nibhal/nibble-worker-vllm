## Change Summary

- Objective:
- Scope:

## Required Global Checks

- [ ] I confirmed absolute upstream prohibition: this repo performs no upstream interaction of any kind (sync, fetch, pull, rebase, merge, cherry-pick, PR, push) against `runpod-workers/worker-vllm`.
- [ ] I documented rollback steps.
- [ ] I added validation evidence (commands run, manual checks, outcomes).

## Conditional Checklists

### Runtime changes (`src/`, `Dockerfile`, `docker-bake.hcl`)

- [ ] I ran required checks from `docs/VALIDATION_MATRIX.md` or marked manual checks with reason.
- [ ] I documented RunPod + vLLM compatibility impact.

### CI/Release changes (`.github/workflows/*`, tag/release logic)

- [ ] I reviewed trigger scope and permissions.
- [ ] I verified fork-safe naming (`repository_owner` defaults, no hardcoded upstream namespace).

### Dependency bumps (`builder/requirements.txt`, base image/toolchain pins)

- [ ] I documented old and new versions and rationale.
- [ ] I documented compatibility risk and fallback version.

### Governance/process changes (`AGENTS.md`, `aiwf*.json`, docs)

- [ ] I confirmed no runtime behavior changes.
- [ ] I validated file format integrity where applicable (JSON/frontmatter/manual).

## Rollback Note

- Known-good tag/image:
- Revert method:

## Validation Evidence

| Check | Command or method | Result |
|---|---|---|
| Example | `python3 -m compileall src` | pass |
