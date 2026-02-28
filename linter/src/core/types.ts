export type Severity = 'error' | 'warning' | 'info';

export interface LintError {
  code: string;
  message: string;
  severity: Severity;
  file: string;
  line?: number;
}

export interface AgentMetadata {
  system?: string;
  [key: string]: any;
}

export interface AgentDefinition {
  scope: string;
  type: 'rules' | 'agent' | 'skill';
  role: string;
  priority?: 'critical' | 'high' | 'medium' | 'low';
  parent?: string;
  metadata?: AgentMetadata;
  filePath: string;
  content: string; // Raw content
  frontmatter: any; // Raw parsed frontmatter
}

export interface RuleContext {
  file: string;
  rootDir: string;
  content: string;
  rawContent: string;
  frontmatter: any;
  ast?: any; // For future use if we need deep parsing
}

export interface Rule {
  code: string;
  description: string;
  validate: (ctx: RuleContext) => LintError[];
  fix?: (ctx: RuleContext) => { frontmatter: any } | null; // Returns updated frontmatter or null if no fix possible
}
