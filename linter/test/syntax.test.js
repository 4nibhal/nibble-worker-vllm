const { test, expect } = require('bun:test');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { LinterEngine } = require('../dist/core/engine.js');

function mkTempDir(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

test('E001 reports missing frontmatter fence', async () => {
  const root = mkTempDir('aiwf-linter-syntax-');
  const file = path.join(root, 'AGENTS.md');

  fs.writeFileSync(file, '# Missing frontmatter\n', 'utf-8');

  const engine = new LinterEngine(root, false);
  const errors = await engine.run();

  expect(errors.some((err) => err.code === 'E001')).toBe(true);
});
