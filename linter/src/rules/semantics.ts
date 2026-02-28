import * as path from 'path';
import { Rule, LintError, RuleContext } from '../core/types';

function normalizeScope(scope: string): string {
  if (scope === '/') {
    return '';
  }

  return scope.replace(/^\/+|\/+$/g, '').replace(/\\/g, '/');
}

function toPosixRelativeDir(rootDir: string, filePath: string): string {
  const rel = path.relative(rootDir, path.dirname(filePath));
  return rel === '' ? '' : rel.split(path.sep).join('/');
}

function inferScopeWithStyle(existingScope: string | undefined, relativeDir: string): string {
  if (relativeDir === '') {
    return '/';
  }

  if (!existingScope) {
    return relativeDir;
  }

  const startsWithSlash = existingScope.startsWith('/');
  const endsWithSlash = existingScope.endsWith('/');

  if (startsWithSlash && endsWithSlash) {
    return `/${relativeDir}/`;
  }
  if (startsWithSlash) {
    return `/${relativeDir}`;
  }
  if (endsWithSlash) {
    return `${relativeDir}/`;
  }

  return relativeDir;
}

export const semanticRules: Rule[] = [
  {
    code: 'E003',
    description: 'Validates that the scope matches the file location',
    validate: (ctx: RuleContext): LintError[] => {
      const fileName = path.basename(ctx.file);
      if (fileName !== 'AGENTS.md') {
        return [];
      }

      const declaredScope = ctx.frontmatter?.scope;
      if (!declaredScope || typeof declaredScope !== 'string') {
        return [];
      }

      const expectedDir = toPosixRelativeDir(ctx.rootDir, ctx.file);
      const normalizedDeclared = normalizeScope(declaredScope);
      const normalizedExpected = normalizeScope(expectedDir);

      if (normalizedDeclared !== normalizedExpected) {
        const expectedScope = expectedDir === '' ? '/' : expectedDir;

        const error: LintError = {
          code: 'E003',
          message: `Scope mismatch. Declared scope '${declaredScope}' does not match expected scope '${expectedScope}' for '${ctx.file}'`,
          severity: 'error',
          file: ctx.file,
          line: 1
        };

        return [error];
      }

      return [];
    },
    fix: (ctx: RuleContext) => {
      const fileName = path.basename(ctx.file);
      if (fileName !== 'AGENTS.md') {
        return null;
      }

      const relativeDir = toPosixRelativeDir(ctx.rootDir, ctx.file);
      const fixedScope = inferScopeWithStyle(ctx.frontmatter?.scope, relativeDir);

      if (ctx.frontmatter?.scope === fixedScope) {
        return null;
      }

      const frontmatter = { ...ctx.frontmatter, scope: fixedScope };
      return { frontmatter };
    }
  }
];
