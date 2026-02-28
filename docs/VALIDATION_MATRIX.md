# Validation Matrix

| Touched path | Required checks | Command / method | Evidence in PR |
|---|---|---|---|
| `src/` | Python syntax integrity | `python3 -m compileall src` | Paste command + pass/fail output |
| `src/` | Runtime behavior sanity | Manual verification on representative request path | Input used, observed output, environment |
| `builder/requirements.txt` | Dependency file parses and installs | `docker buildx bake --print` (static) + manual install risk review | Print output + risk note |
| `builder/requirements.txt` | Version policy consistency | Manual check for pin/range intent and compatibility | Old->new versions + rationale |
| `Dockerfile` | Build graph validity | `docker buildx bake --print` | Print output snippet |
| `Dockerfile` | Runtime compatibility gate (RunPod + vLLM) | Manual verification (GPU/runtime dependent) | Compatibility statement + test context |
| `docker-bake.hcl` | Tag rendering and target validity | `docker buildx bake --print` | Rendered tag and target summary |
| `.github/workflows/*` | YAML validity and trigger review | Manual verification (no repo-local workflow linter guaranteed) | Trigger diff + permission review |
| `.github/workflows/*` | Fork-safe release naming | Manual check for `github.repository_owner` default behavior | Screenshot/log or quoted lines |
| `AGENTS.md` | Rule metadata/frontmatter consistency | Manual verification or repository linter if available | Validation method + result |
| `aiwf.config.json` / `aiwf.request.json` | JSON validity | `python3 -m json.tool aiwf.config.json >/dev/null` and `python3 -m json.tool aiwf.request.json >/dev/null` | Command list + pass/fail |

## Notes

- If a required tool is unavailable locally, mark check as `manual verification` and include exact reviewer steps.
- Do not substitute upstream CI output for fork-local validation evidence.
