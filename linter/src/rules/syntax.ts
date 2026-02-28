import { Rule, LintError, RuleContext } from '../core/types';
import * as path from 'path';
import { z } from 'zod';

// Define Zod schemas
const PrioritySchema = z.enum(['critical', 'high', 'medium', 'low']);
const AgentTypeSchema = z.enum(['rules', 'agent', 'skill']);

const AgentMetadataSchema = z.object({
  scope: z.string().min(1, "Missing required field for AGENTS.md: 'scope'"),
  type: AgentTypeSchema,
  role: z.string().min(1, "Missing required field for AGENTS.md: 'role'"),
  priority: PrioritySchema.optional()
}).passthrough(); // Allow other properties

const SkillMetadataSchema = z.object({
  name: z.string().min(1, "Missing required field for SKILL.md: 'name'"),
  description: z.string().min(1, "Missing required field for SKILL.md: 'description'")
}).passthrough();

export const syntaxRules: Rule[] = [
  {
    code: 'E001',
    description: 'Validates that the file has a valid YAML frontmatter',
    validate: (ctx: RuleContext): LintError[] => {
      const trimmedStart = ctx.rawContent.trimStart();
      const hasFrontmatterFence = trimmedStart.startsWith('---\n') || trimmedStart.startsWith('---\r\n');

      if (!hasFrontmatterFence) {
        return [{
          code: 'E001',
          message: 'File must start with YAML frontmatter enclosed in "---"',
          severity: 'error',
          file: ctx.file,
          line: 1
        }];
      }

      if (Object.keys(ctx.frontmatter).length === 0) {
        return [{
          code: 'E001',
          message: 'Frontmatter block is present but empty or invalid',
          severity: 'error',
          file: ctx.file,
          line: 1
        }];
      }

      return [];
    }
  },
  {
    code: 'E002',
    description: 'Validates required schema fields using Zod',
    validate: (ctx: RuleContext): LintError[] => {
      const fileName = path.basename(ctx.file);
      let schema: z.ZodSchema<any>;

      if (fileName === 'AGENTS.md') {
        schema = AgentMetadataSchema;
      } else if (fileName === 'SKILL.md') {
        schema = SkillMetadataSchema;
      } else {
        return [];
      }

      const result = schema.safeParse(ctx.frontmatter);
      if (!result.success) {
        return result.error.issues.map(issue => ({
          code: 'E002',
          message: issue.message.includes('Required') || issue.message.includes('Missing') 
            ? issue.message 
            : `Invalid value for '${issue.path.join('.')}': ${issue.message}`,
          severity: 'error',
          file: ctx.file,
          line: 1
        }));
      }

      return [];
    },
    fix: (ctx: RuleContext) => {
      const fm = { ...ctx.frontmatter };
      const fileName = path.basename(ctx.file);
      let changed = false;

      if (fileName === 'AGENTS.md') {
        if (!fm.type) { fm.type = 'rules'; changed = true; }
        if (!fm.role) { fm.role = 'TODO: Define role'; changed = true; }
        if (!fm.scope) { fm.scope = 'TODO_SCOPE'; changed = true; }
      } else if (fileName === 'SKILL.md') {
         if (!fm.name) {
             const dirName = path.basename(path.dirname(ctx.file));
             fm.name = dirName;
             changed = true;
         }
         if (!fm.description) { fm.description = 'TODO: Add description'; changed = true; }
      }

      return changed ? { frontmatter: fm } : null;
    }
  }
];
