import * as fs from 'fs';
import * as path from 'path';
import matter from 'gray-matter';
import { Rule, LintError, RuleContext } from './types';

// Load all rules
import { syntaxRules } from '../rules/syntax';
import { semanticRules } from '../rules/semantics';

const ALL_RULES: Rule[] = [
  ...syntaxRules,
  ...semanticRules
];

export class LinterEngine {
  private rootDir: string;

  constructor(rootDir: string, private autoFix: boolean = false) {
    this.rootDir = path.resolve(rootDir);
  }

  async run(): Promise<LintError[]> {
    const errors: LintError[] = [];
    const files = this.findLintableFiles(this.rootDir);

    for (const relativePath of files) {
      const absolutePath = path.join(this.rootDir, relativePath);
      const fileContent = fs.readFileSync(absolutePath, 'utf-8');
      
      let parsed: matter.GrayMatterFile<string> | any;
      try {
        parsed = matter(fileContent);
      } catch (e) {
        // If gray-matter fails, we treat it as empty frontmatter
        // The syntax rule E001 will likely catch this if it's invalid YAML
        parsed = { data: {}, content: fileContent };
      }

      let context: RuleContext = {
        file: absolutePath,
        rootDir: this.rootDir,
        content: parsed.content,
        rawContent: fileContent,
        frontmatter: parsed.data
      };

      let fileModified = false;

      for (const rule of ALL_RULES) {
        try {
          const ruleErrors = rule.validate(context);
          
          if (ruleErrors.length > 0 && this.autoFix && rule.fix) {
             const fixResult = rule.fix(context);
             if (fixResult) {
                 // Apply fix
                 context.frontmatter = fixResult.frontmatter;
                 fileModified = true;
                 // We don't push the error if it was fixed
                 continue;
             }
          }

          errors.push(...ruleErrors);
        } catch (e) {
          console.error(`Error running rule ${rule.code} on ${relativePath}:`, e);
        }
      }

      if (fileModified && this.autoFix) {
         // Reconstruct the file using gray-matter
         // Note: gray-matter stringify takes (content, data)
         const newContent = matter.stringify(context.content, context.frontmatter);
         fs.writeFileSync(absolutePath, newContent);
      }
    }

    return errors;
  }

  private findLintableFiles(scanDir: string): string[] {
    const entries = fs.readdirSync(scanDir, { withFileTypes: true });
    const files: string[] = [];

    for (const entry of entries) {
      if (entry.isDirectory()) {
        if (entry.name === 'node_modules' || entry.name === 'dist' || entry.name === '.git') {
          continue;
        }
        files.push(...this.findLintableFiles(path.join(scanDir, entry.name)));
        continue;
      }

      if (!entry.isFile()) {
        continue;
      }

      if (entry.name !== 'AGENTS.md' && entry.name !== 'SKILL.md') {
        continue;
      }

      files.push(path.relative(this.rootDir, path.join(scanDir, entry.name)));
    }

    return files;
  }
}
