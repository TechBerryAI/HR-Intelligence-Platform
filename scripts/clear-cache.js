#!/usr/bin/env node
/**
 * Clear local build / bytecode / test caches across the monorepo.
 *
 * Usage (from repo root):
 *   npm run clear-cache
 *   node scripts/clear-cache.js
 *   node scripts/clear-cache.js --dry-run
 *   node scripts/clear-cache.js --dist   # also remove Vite dist outputs
 *
 * Safe by design: never deletes venv/, node_modules/ (except Vite's .vite),
 * .git/, media data, or .env files.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

const SKIP_DIR_NAMES = new Set([
  '.git',
  'venv',
  '.venv',
  'node_modules',
  'hcip-data',
  'media',
]);

/** Directory names removed wherever found under ROOT (except under SKIP). */
const CACHE_DIR_NAMES = new Set([
  '__pycache__',
  '.pytest_cache',
  '.mypy_cache',
  '.ruff_cache',
  '.tox',
  '.hypothesis',
  '.cache',
  'htmlcov',
  '.parcel-cache',
  '.turbo',
]);

/** Exact relative paths (posix) removed when present. */
const EXACT_REL_PATHS = [
  'apps/frontend/node_modules/.vite',
  'apps/frontend/node_modules/.cache',
];

/** Optional build outputs (only with --dist). */
const DIST_REL_PATHS = [
  'apps/frontend/dist',
];

const BYTECODE_EXT = new Set(['.pyc', '.pyo']);

function parseArgs(argv) {
  const flags = new Set(argv.slice(2));
  return {
    dryRun: flags.has('--dry-run') || flags.has('-n'),
    dist: flags.has('--dist'),
    help: flags.has('--help') || flags.has('-h'),
  };
}

function toPosix(p) {
  return p.split(path.sep).join('/');
}

function rel(abs) {
  return toPosix(path.relative(ROOT, abs));
}

function rm(abs, dryRun, removed) {
  if (!fs.existsSync(abs)) return;
  const key = rel(abs) || abs;
  if (dryRun) {
    console.log(`[dry-run] ${key}`);
  } else {
    fs.rmSync(abs, { recursive: true, force: true });
    console.log(`[removed] ${key}`);
  }
  removed.push(key);
}

function walk(dir, dryRun, removed) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }

  for (const ent of entries) {
    const abs = path.join(dir, ent.name);

    if (ent.isDirectory()) {
      if (SKIP_DIR_NAMES.has(ent.name)) continue;
      if (CACHE_DIR_NAMES.has(ent.name)) {
        rm(abs, dryRun, removed);
        continue;
      }
      walk(abs, dryRun, removed);
      continue;
    }

    if (ent.isFile()) {
      const ext = path.extname(ent.name).toLowerCase();
      if (BYTECODE_EXT.has(ext)) {
        rm(abs, dryRun, removed);
      }
    }
  }
}

function main() {
  const opts = parseArgs(process.argv);
  if (opts.help) {
    console.log(`Clear local caches under ${ROOT}

Usage:
  node scripts/clear-cache.js [--dry-run] [--dist]

Options:
  --dry-run, -n   Print paths that would be removed
  --dist          Also remove frontend dist/ build output
  --help, -h      Show this help
`);
    process.exit(0);
  }

  const removed = [];
  console.log(`${opts.dryRun ? 'Dry-run' : 'Clearing'} caches under ${ROOT}`);

  // Vite / tool caches under node_modules are hit explicitly (walk skips node_modules).
  for (const relPath of EXACT_REL_PATHS) {
    rm(path.join(ROOT, ...relPath.split('/')), opts.dryRun, removed);
  }

  if (opts.dist) {
    for (const relPath of DIST_REL_PATHS) {
      rm(path.join(ROOT, ...relPath.split('/')), opts.dryRun, removed);
    }
  }

  walk(ROOT, opts.dryRun, removed);

  const unique = [...new Set(removed)].sort();
  console.log(
    unique.length
      ? `\n${opts.dryRun ? 'Would remove' : 'Removed'} ${unique.length} path(s).`
      : '\nNothing to clear — already clean.'
  );
}

main();
