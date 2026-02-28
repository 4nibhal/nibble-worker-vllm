# Release Policy

## Tag And Version Policy

- Stable tags: `vMAJOR.MINOR.PATCH` only.
- Optional prerelease tags: `vMAJOR.MINOR.PATCH-rc.N`.
- Tag must reference an immutable commit on this fork.
- Release note must include validation evidence and rollback target.

## Image Naming (Fork-Safe)

- Registry namespace default: `github.repository_owner`.
- Image name default: `worker-v1-vllm` unless overridden by repo variable.
- Stable tag image format: `<owner>/<image>:vMAJOR.MINOR.PATCH`.
- Dev tag format: `<owner>/<image>:dev-<safe-branch>`.
- Do not assume `runpod/*` namespace exists for this fork.

## Release Triggers

- Tag push matching `v[0-9]+.[0-9]+.[0-9]+*` triggers release workflow.
- Manual dispatch allowed with explicit `version` input.
- Absolute upstream prohibition: release triggers and automation must never interact with `runpod-workers/worker-vllm` in any way (sync, fetch, pull, rebase, merge, cherry-pick, PR, push).

## Rollback Protocol

1. Identify last known-good tag and image.
2. Repoint deployment to known-good image tag.
3. Revert offending commit or publish patch tag.
4. Document incident scope, validation gap, and corrective action in release notes/PR.
