const { test, expect } = require('bun:test');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { LinterEngine } = require('../dist/core/engine.js');

function mkTempDir(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

test('E003 detects scope mismatch for nested AGENTS.md', async () => {
  const root = mkTempDir('aiwf-linter-semantic-');
  const nestedDir = path.join(root, 'linter');
  fs.mkdirSync(nestedDir, { recursive: true });

  const nestedAgents = path.join(nestedDir, 'AGENTS.md');
  fs.writeFileSync(
    nestedAgents,
    `---
scope: "/skills/"
type: "rules"
role: "Nested Rules"
---

# Nested
`,
    'utf-8'
  );

  const engine = new LinterEngine(root, false);
  const errors = await engine.run();

  const scopeErrors = errors.filter((err) => err.code === 'E003');
  expect(scopeErrors.length).toBe(1);
  expect(scopeErrors[0].message).toMatch(/Scope mismatch/);
});

test('autofix rewrites mismatched scope using file location', async () => {
  const root = mkTempDir('aiwf-linter-autofix-');
  const nestedDir = path.join(root, 'skills');
  fs.mkdirSync(nestedDir, { recursive: true });

  const nestedAgents = path.join(nestedDir, 'AGENTS.md');
  fs.writeFileSync(
    nestedAgents,
    `---
scope: "backend"
type: "rules"
role: "Skills Rules"
---

# Skills Rules
`,
    'utf-8'
  );

  const fixEngine = new LinterEngine(root, true);
  await fixEngine.run();

  const updated = fs.readFileSync(nestedAgents, 'utf-8');
  expect(updated).toMatch(/scope: skills/);
});
