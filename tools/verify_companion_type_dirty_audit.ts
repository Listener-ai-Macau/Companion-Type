import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

const OUT_JSON = 'docs/validation/companion-type-dirty-audit.json';

function command(command: string, args: string[]) {
  const result = spawnSync(command, args, { encoding: 'utf8' });
  return {
    command: [command, ...args],
    exitCode: result.status,
    stdout: result.stdout,
    stderr: result.stderr,
  };
}

function parsePorcelain(stdout: string) {
  return stdout
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const status = line.slice(0, 2);
      const path = line.slice(3);
      return {
        status,
        path,
        tracked: status !== '??',
        category: categorizePath(path),
      };
    });
}

function categorizePath(path: string) {
  if (path.startsWith('apps/windows/src-tauri/src/backend/')) return 'windows-backend';
  if (path.startsWith('apps/windows/src-tauri/src/')) return 'windows-tauri-shell';
  if (path.startsWith('apps/windows/')) return 'windows-frontend-or-tauri-config';
  if (path.startsWith('apps/mobile/')) return 'mobile-shell';
  if (path.startsWith('packages/core/')) return 'core-contract';
  if (path.startsWith('packages/ui/')) return 'shared-ui';
  if (path.startsWith('tools/')) return 'validation-tooling';
  if (path.startsWith('docs/validation/')) return 'validation-evidence';
  if (path === 'package.json' || path === 'package-lock.json') return 'npm-manifest';
  if (path === 'README.md') return 'docs';
  return 'other';
}

function countBy<T extends string>(values: T[]) {
  return values.reduce<Record<T, number>>((counts, value) => {
    counts[value] = (counts[value] ?? 0) + 1;
    return counts;
  }, {} as Record<T, number>);
}

function fileEvidence(path: string) {
  return {
    path,
    exists: existsSync(path),
    bytes: existsSync(path) ? statSync(path).size : 0,
  };
}

const statusShort = command('git', ['status', '--short', '--branch']);
const statusPorcelain = command('git', ['status', '--porcelain=v1']);
const diffStat = command('git', ['diff', '--stat']);
const diffNameStatus = command('git', ['diff', '--name-status']);
const untrackedFiles = command('git', ['ls-files', '--others', '--exclude-standard']);
const entries = parsePorcelain(statusPorcelain.stdout);
const paths = entries.map((entry) => entry.path);
const listenerTypeTouched = paths.some((path) => /(^|[\\/])Listener-Type([\\/]|$)/.test(path));

const report = {
  schema: 'companion_type.dirty_audit.v1',
  generatedAt: new Date().toISOString(),
  result: listenerTypeTouched ? 'FAIL_LISTENER_TYPE_PATH_PRESENT' : 'PASS_DIRTY_WORKTREE_AUDITED',
  repo: process.cwd(),
  branch: statusShort.stdout.split(/\r?\n/)[0] ?? '',
  dirty: entries.length > 0,
  counts: {
    total: entries.length,
    tracked: entries.filter((entry) => entry.tracked).length,
    untracked: entries.filter((entry) => !entry.tracked).length,
    byCategory: countBy(entries.map((entry) => entry.category)),
    byStatus: countBy(entries.map((entry) => entry.status)),
  },
  listenerTypeTouched,
  entries,
  commands: {
    statusShort,
    statusPorcelain,
    diffStat,
    diffNameStatus,
    untrackedFiles,
  },
  evidence: [
    fileEvidence('docs/validation/companion-type-joint-acceptance.json'),
    fileEvidence('docs/validation/companion-type-installed-ui-sync.json'),
    fileEvidence('docs/validation/companion-type-installed-ui-sync-05-after-sync-settled.png'),
    fileEvidence('docs/validation/companion-type-msi-install-smoke.json'),
    fileEvidence('docs/validation/companion-type-long-meeting-chain.json'),
    fileEvidence('docs/validation/companion-type-real-microphone.json'),
  ],
  note: 'This audit is read-only. It preserves the dirty worktree and does not stage, commit, stash, reset, delete, or modify Listener-Type.',
};

mkdirSync(dirname(OUT_JSON), { recursive: true });
writeFileSync(OUT_JSON, `${JSON.stringify(report, null, 2)}\n`);

if (report.result !== 'PASS_DIRTY_WORKTREE_AUDITED') {
  console.error(`FAIL companion-type dirty audit: ${report.result}`);
  process.exit(1);
}

console.log(`PASS companion-type dirty audit: ${OUT_JSON}`);
