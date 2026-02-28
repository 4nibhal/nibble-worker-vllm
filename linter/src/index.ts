#!/usr/bin/env bun
import * as path from 'path';
import { LinterEngine } from './core/engine';

type CliOptions = {
  dir: string;
  fix: boolean;
};

function showHelp(): void {
  process.stdout.write(
    [
      'Usage: bun src/index.ts [options]',
      '',
      'Options:',
      '  -d, --dir <path>   Root directory to scan (default: current working directory)',
      '  --fix              Automatically apply available fixes',
      '  -h, --help         Show this help message',
    ].join('\n') + '\n'
  );
}

function parseArgs(argv: string[]): CliOptions {
  const options: CliOptions = {
    dir: process.cwd(),
    fix: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === '-h' || arg === '--help') {
      showHelp();
      process.exit(0);
    }

    if (arg === '--fix') {
      options.fix = true;
      continue;
    }

    if (arg === '-d' || arg === '--dir') {
      const value = argv[index + 1];
      if (!value || value.startsWith('-')) {
        throw new Error('Missing value for --dir');
      }
      options.dir = value;
      index += 1;
      continue;
    }

    throw new Error(`Unknown option: ${arg}`);
  }

  if (options.dir.trim().length === 0) {
    throw new Error('Directory path cannot be empty');
  }

  return options;
}

async function main(): Promise<void> {
  try {
    const options = parseArgs(process.argv.slice(2));
    const rootDir = path.resolve(options.dir);

    console.log(`Linting architectural files in: ${rootDir}`);
    const runtime = typeof (globalThis as { Bun?: unknown }).Bun !== 'undefined' ? 'Bun' : 'Node';
    console.log(`Runtime: ${runtime}`);

    if (options.fix) {
      console.log('Autofix enabled');
    }

    const engine = new LinterEngine(rootDir, options.fix);
    const errors = await engine.run();

    if (errors.length === 0) {
      console.log('All files passed validation.');
      process.exit(0);
    }

    console.log(`\nFound ${errors.length} issues:`);

    let errorCount = 0;
    for (const err of errors) {
      const relativePath = path.relative(rootDir, err.file);
      if (err.severity === 'error') {
        errorCount += 1;
      }

      console.log(`\n${relativePath}:${err.line || 1}`);
      console.log(`[${err.code}] ${err.message}`);
    }

    console.log(`\n${'-'.repeat(40)}`);
    if (errorCount > 0) {
      console.log(`FAILED: ${errorCount} errors found.`);
      process.exit(1);
    }

    console.log('Passed with warnings.');
    process.exit(0);
  } catch (error) {
    console.error('Fatal error during linting:', error);
    process.exit(1);
  }
}

void main();
