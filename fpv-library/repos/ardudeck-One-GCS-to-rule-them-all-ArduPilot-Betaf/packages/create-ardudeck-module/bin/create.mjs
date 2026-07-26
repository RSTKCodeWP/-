#!/usr/bin/env node
import { readFile, writeFile, mkdir, readdir, copyFile } from 'node:fs/promises';
import { join, dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline';
import { stdin, stdout, argv, exit } from 'node:process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEMPLATE_DIR = join(__dirname, '..', 'template');

const SLUG_RE = /^[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)+$/;

function createPrompter() {
  const queue = [];
  let pending = null;
  const rl = createInterface({ input: stdin, output: stdout });
  rl.on('line', (line) => {
    if (pending) {
      const { resolve } = pending;
      pending = null;
      resolve(line);
    } else {
      queue.push(line);
    }
  });
  rl.on('close', () => {
    if (pending) {
      pending.resolve('');
      pending = null;
    }
  });
  return {
    ask(question, defaultValue) {
      const hint = defaultValue ? ` (${defaultValue})` : '';
      stdout.write(`${question}${hint}: `);
      return new Promise((resolve) => {
        if (queue.length > 0) {
          resolve(queue.shift());
        } else {
          pending = { resolve };
        }
      }).then((raw) => raw.trim() || defaultValue);
    },
    close() {
      rl.close();
    },
  };
}

async function walk(dir) {
  const out = [];
  const entries = await readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = join(dir, e.name);
    if (e.isDirectory()) out.push(...(await walk(full)));
    else out.push(full);
  }
  return out;
}

async function main() {
  const targetArg = argv[2];
  if (!targetArg) {
    console.error('Usage: create-ardudeck-module <target-directory>');
    exit(1);
  }
  const target = resolve(process.cwd(), targetArg);

  const p = createPrompter();
  const slug = await p.ask('Module slug (e.g. acme.telemetry-plus)', 'acme.my-module');
  if (!SLUG_RE.test(slug)) {
    console.error(`Invalid slug: ${slug}`);
    console.error('Must match ^[a-z][a-z0-9]*(\\.[a-z][a-z0-9-]*)+$');
    p.close();
    exit(1);
  }
  const name = await p.ask('Display name', 'My Module');
  const version = await p.ask('Initial version', '0.1.0');
  const wantsPty = (await p.ask('Needs PTY access? (y/N)', 'N'))
    .toLowerCase()
    .startsWith('y');
  p.close();

  await mkdir(target, { recursive: true });

  const files = await walk(TEMPLATE_DIR);
  const permissionsLine = wantsPty ? '"permissions": ["pty"],\n  ' : '';
  const tokens = {
    __SLUG__: slug,
    __NAME__: name,
    __VERSION__: version,
    __PERMISSIONS__: permissionsLine,
  };

  const textExt = /\.(ts|tsx|json|mjs|md|gitignore)$/;

  for (const src of files) {
    const rel = relative(TEMPLATE_DIR, src);
    const dest = join(target, rel);
    await mkdir(dirname(dest), { recursive: true });

    if (textExt.test(src) || src.endsWith('/.gitignore')) {
      let content = await readFile(src, 'utf-8');
      for (const [k, v] of Object.entries(tokens)) {
        content = content.replaceAll(k, v);
      }
      await writeFile(dest, content);
    } else {
      await copyFile(src, dest);
    }
  }

  console.log(`\nModule scaffolded at ${target}`);
  console.log('\nNext steps:');
  console.log(`  cd ${targetArg}`);
  console.log('  pnpm install');
  console.log('  pnpm build');
}

main().catch((err) => {
  console.error(err);
  exit(1);
});
