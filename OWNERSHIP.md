# Decision Ownership Matrix

| Domain | Primary owner | Secondary owner | Required decision outputs |
|---|---|---|---|
| Runtime (`src/`, `Dockerfile`, `docker-bake.hcl`) | Runtime Maintainer | Platform Reviewer | Compatibility assessment, validation evidence, rollback |
| CI/Release (`.github/workflows/*`, tags) | CI/Release Maintainer | Runtime Maintainer | Trigger safety, permission review, release traceability |
| Governance artifacts (`AGENTS.md`, `aiwf*.json`, process docs) | Repo Governance Maintainer | CI/Release Maintainer | Policy diff rationale, non-behavioral impact note |
| Security/Secrets | Security Owner | Repo Maintainer | Secret handling plan, exposure risk review, remediation path |
| Dependency strategy (`builder/requirements.txt`, base image pins) | Dependency Maintainer | Runtime Maintainer | Version strategy, compatibility risk, rollback pin |

## Escalation Rule

- High-risk change (runtime break risk, release break risk, permission expansion, secret exposure risk) requires explicit approval from Primary + Secondary owner before merge.
- If either owner is unavailable, escalate to repository admin and block merge until written approval is recorded in PR.
