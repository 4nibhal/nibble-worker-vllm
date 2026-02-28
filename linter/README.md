# @ai-workflows/linter

An architectural linter designed to enforce the "Modular, Scope-Aware" architecture of the `ai-workflows` project. It validates the integrity of `AGENTS.md` and `SKILL.md` files, ensuring they are correctly structured and linked.

## Features

- **Syntax Validation (E001)**: Ensures files start with YAML frontmatter and that it is not empty.
- **Schema Validation (E002)**: Checks for required fields (`scope`, `type`, `role`, `priority`) and valid enums.
- **Semantic Validation (E003)**: Verifies that the declared `scope` matches the physical file location.
- **Auto-Fixing (`--fix`)**: Automatically corrects missing fields and scope mismatches.

## Usage

### Running the Linter
From the project root:

```bash
# Run validation
bun run --cwd linter lint

# Run validation on specific directory
bun run --cwd linter lint -- -d /path/to/scan
```

### Auto-Fixing
The linter can automatically fix common issues like missing fields or incorrect scopes.

```bash
# Fix issues automatically
bun run --cwd linter lint -- --fix -d ..
```

## Rules

| Code | Severity | Description | Fixable |
| :--- | :--- | :--- | :--- |
| `E001` | Error | Invalid YAML Frontmatter | No |
| `E002` | Error | Missing required fields or invalid values | Yes |
| `E003` | Error | Scope mismatch (declared vs file path) | Yes |

## Development

The linter is a standalone TypeScript project located in `linter/`.

### Build
```bash
bun install --cwd linter --frozen-lockfile
bun run --cwd linter build
```

### Test
```bash
bun run --cwd linter test
```

### Extending
To add new rules:
1. Create a new rule in `src/rules/`.
2. Implement the `Rule` interface.
3. Add it to `ALL_RULES` in `src/core/engine.ts`.
