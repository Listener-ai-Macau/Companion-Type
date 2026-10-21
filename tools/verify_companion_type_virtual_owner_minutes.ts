/**
 * Virtual owner acceptance for meeting minutes — click-by-click dry run.
 * Does NOT open popups or touch hardware. Produces a receipt the real human
 * session can reuse as the expected path.
 */
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import {
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
  describeSessionPendingReason,
  selectedCompanionHostSession,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
} from '../packages/core/src/companionV1.ts';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const outDir = join(root, 'docs', 'validation', 'companion-type-virtual-owner-minutes');
mkdirSync(outDir, { recursive: true });

const spoken = [
  'Decision: Companion host owns long meeting recordings.',
  'Action owner: Chen due: Friday validates mechanical voice minutes.',
  'Question: is offline needs_transcription explicit?',
].join(' ');

type StepResult = {
  n: number;
  ownerAction: string;
  uiHint: string;
  action: string;
  ok: boolean;
  meetingStatus: string;
  sessionStatus: string | null;
  pendingReason: string | null;
  note: string;
};

const steps: StepResult[] = [];
let n = 0;

function run(
  snap: CompanionV1Snapshot,
  ownerAction: string,
  uiHint: string,
  request: CompanionV1ControlRequest,
  check: (s: CompanionV1Snapshot) => string,
): CompanionV1Snapshot {
  n += 1;
  const next = applyCompanionV1ControlFixture(snap, request);
  const session = selectedCompanionHostSession(next);
  let note = '';
  let ok = true;
  try {
    note = check(next);
  } catch (err) {
    ok = false;
    note = err instanceof Error ? err.message : String(err);
  }
  steps.push({
    n,
    ownerAction,
    uiHint,
    action: request.action,
    ok,
    meetingStatus: next.meeting.status,
    sessionStatus: session?.status ?? null,
    pendingReason: session?.pendingReason ?? null,
    note,
  });
  assert.ok(ok, `step ${n} failed: ${ownerAction} — ${note}`);
  return next;
}

// --- Path A: short device capture (what owner does after offline recording) ---
let snap = createCompanionV1Fixture();
snap = run(
  snap,
  '打开 Companion Type，点 Setup → Check',
  'Setup panel',
  { action: 'oobeRunChecks' },
  (s) => {
    assert.equal(s.oobe.complete, true);
    return 'OOBE complete';
  },
);
snap = run(
  snap,
  '点 Device → Scan',
  'Device panel',
  { action: 'deviceScan' },
  (s) => {
    assert.ok(s.device.deviceId);
    return `found ${s.device.deviceId}`;
  },
);
snap = run(
  snap,
  '点 Device → Connect',
  'Device panel',
  { action: 'deviceConnect', deviceId: 'companion-nucleo-wb55rg' },
  (s) => {
    assert.equal(s.device.connected, true);
    return 'connected';
  },
);
snap = run(
  snap,
  '点 Device → Sync short（短录同步）',
  'Device panel / Sync short',
  {
    action: 'deviceSyncRecordings',
    title: 'Virtual short flash capture',
    audioPath: 'device://companion/flash/latest.wav',
    audioBytes: 1_920_000,
    durationMs: 60_000,
  },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.equal(session?.source, 'deviceFlash');
    assert.equal(session?.status, 'captured');
    assert.equal(session?.pendingReason, 'needs_transcription');
    assert.ok(describeSessionPendingReason(session?.pendingReason ?? null));
    return 'session captured; yellow pending needs_transcription expected';
  },
);
snap = run(
  snap,
  '点 Transcript → Import（粘贴转写或等 ASR）',
  'Transcript panel / Import',
  { action: 'meetingImportTranscript', transcriptText: spoken },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.equal(session?.status, 'transcribed');
    assert.equal(session?.pendingReason, null);
    return 'pending cleared; transcribed';
  },
);
snap = run(
  snap,
  '点 Transcript → Minutes',
  'Transcript panel / Minutes',
  { action: 'meetingGenerateMinutes' },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.equal(session?.status, 'minutesReady');
    assert.equal(session?.minutes?.source, 'rules_l0');
    assert.equal(session?.minutes?.quality, 'draft');
    assert.ok((session?.minutes?.decisions.length ?? 0) >= 1);
    assert.ok((session?.minutes?.actionItems.length ?? 0) >= 1);
    return 'minutes draft ready';
  },
);
snap = run(
  snap,
  '点 Export → Markdown',
  'Export panel',
  { action: 'meetingExportMarkdown' },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.ok(session?.exportMarkdown.includes('## Action Items'));
    writeFileSync(join(outDir, 'path-a-short-device-minutes.md'), session!.exportMarkdown, 'utf8');
    return 'markdown exported';
  },
);
const pathASession = selectedCompanionHostSession(snap)!;

// --- Path B: long host meeting ---
snap = createCompanionV1Fixture();
snap = run(
  snap,
  'Meeting 区填标题，点 Start host',
  'Meeting panel / Start host',
  { action: 'meetingStart', title: 'Virtual one-hour host meeting' },
  (s) => {
    assert.equal(s.meeting.status, 'recording');
    assert.equal(selectedCompanionHostSession(s)?.source, 'hostMicrophone');
    return 'host recording';
  },
);
snap = run(
  snap,
  '会后点 Stop',
  'Meeting panel / Stop',
  {
    action: 'meetingStop',
    durationMs: 3_600_000,
    audioBytes: 115_200_000,
  },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.equal(session?.status, 'captured');
    assert.equal(session?.pendingReason, 'needs_transcription');
    assert.ok((session?.chunks.length ?? 0) >= 12);
    return `captured ${session?.chunks.length} chunks; pending transcription`;
  },
);
snap = run(
  snap,
  '无 ASR 时先点 Transcribe 应仍停在 pending（虚拟：空转写）',
  'Transcript / Transcribe without provider',
  { action: 'meetingTranscribeAudio' },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.equal(session?.status, 'captured');
    assert.equal(session?.pendingReason, 'needs_transcription');
    return 'soft fail: still needs_transcription (correct)';
  },
);
snap = run(
  snap,
  '点 Import 或配置 ASR 后 Transcribe',
  'Transcript / Import',
  { action: 'meetingImportTranscript', transcriptText: spoken },
  (s) => {
    assert.equal(selectedCompanionHostSession(s)?.pendingReason, null);
    return 'transcribed';
  },
);
snap = run(
  snap,
  '点 Minutes → 再 Export Markdown',
  'Minutes + Export',
  { action: 'meetingGenerateMinutes' },
  (s) => {
    assert.equal(selectedCompanionHostSession(s)?.status, 'minutesReady');
    return 'minutes ready';
  },
);
snap = run(
  snap,
  '点 Export Markdown',
  'Export',
  { action: 'meetingExportMarkdown' },
  (s) => {
    writeFileSync(
      join(outDir, 'path-b-host-long-minutes.md'),
      selectedCompanionHostSession(s)!.exportMarkdown,
      'utf8',
    );
    return 'exported';
  },
);
snap = run(
  snap,
  '点 Retention → Audio（只删音频，保留纪要文本）',
  'Retention / Audio',
  { action: 'privacyEraseAudio' },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.equal(session?.audioBytes, 0);
    assert.ok(session?.minutes);
    return 'audio erased; minutes kept';
  },
);
snap = run(
  snap,
  '点 Retention → Text（清转写与纪要）',
  'Retention / Text',
  { action: 'privacyEraseTranscript' },
  (s) => {
    const session = selectedCompanionHostSession(s);
    assert.equal(session?.transcriptText, '');
    assert.equal(session?.minutes, null);
    // no audio left → idle, no pending
    assert.ok(session?.status === 'idle' || session?.status === 'captured');
    return `text erased; status=${session?.status}`;
  },
);

// --- Path C: mechanical TTS dry-run (reuse existing accept if present, else generate) ---
const mechDir = join(root, 'docs', 'validation', 'companion-type-mechanical-voice-minutes');
const mechReceipt = join(mechDir, 'acceptance.json');
let mechPass = existsSync(mechReceipt);
if (!mechPass) {
  const r = spawnSync(
    'npm',
    ['run', 'verify:mechanical-voice-minutes'],
    { encoding: 'utf8', cwd: root, shell: true },
  );
  mechPass = r.status === 0 && existsSync(mechReceipt);
}
assert.ok(mechPass, 'mechanical voice acceptance must pass first');
const mech = JSON.parse(readFileSync(mechReceipt, 'utf8')) as { result: string; tts: { wavBytes: number } };
assert.equal(mech.result, 'PASS');

// Human checklist for later (not executed now)
const humanChecklist = [
  {
    id: 'H1',
    title: '短录路径',
    steps: [
      '板子上录一段短语音并停止（或确认已有一条 recording list）',
      '打开 Companion Type',
      'Device → Scan → Connect',
      'Device → Sync short',
      '确认 UI 出现 needs_transcription / 待转写提示',
      'Transcript → Transcribe（若已配 ASR）或 Import 粘贴文稿',
      'Minutes → 确认有 Summary / Decisions / Action Items',
      'Export → Markdown，确认能看见导出内容',
    ],
    expect: 'session minutesReady；不要求你判断文案文学质量，只确认流程通',
  },
  {
    id: 'H2',
    title: '主机长会路径',
    steps: [
      'Meeting 填标题 → Start host（会用本机麦克风）',
      '说几句含 Decision / Action / Question 的话，约 10–30 秒',
      'Stop',
      '确认 pending 待转写',
      'Transcribe 或 Import',
      'Minutes + Export Markdown',
    ],
    expect: '同样 minutesReady；长会不必真录满 1 小时',
  },
  {
    id: 'H3',
    title: '隐私',
    steps: [
      'Retention → Audio：音频缓存清掉，纪要仍在',
      'Retention → Text：转写与纪要清掉',
    ],
    expect: '两步都成功且无报错弹窗',
  },
];

const failed = steps.filter((s) => !s.ok);
const receipt = {
  schema: 'companion_type.virtual_owner_minutes.v1',
  generatedAt: new Date().toISOString(),
  result: failed.length === 0 ? 'PASS_VIRTUAL' : 'FAIL_VIRTUAL',
  mode: 'virtual_owner_dry_run',
  humanPopupOpened: false,
  ownerActionRequired: false,
  pathA_shortDevice: {
    status: pathASession.status,
    minutesSource: pathASession.minutes?.source,
    decisions: pathASession.minutes?.decisions.length ?? 0,
    actionItems: pathASession.minutes?.actionItems.length ?? 0,
    exportFile: 'path-a-short-device-minutes.md',
  },
  pathB_hostLong: {
    exportFile: 'path-b-host-long-minutes.md',
  },
  pathC_mechanicalVoice: {
    receipt: mechReceipt,
    wavBytes: mech.tts.wavBytes,
    result: mech.result,
  },
  clickSteps: steps,
  humanChecklistWhenReady: humanChecklist,
  howToStartHumanAcceptance: [
    '确认本文件 result=PASS_VIRTUAL',
    '确认 Type 已安装或 dev 可开',
    '告诉 AI「开始人工验收」——再开弹窗/步骤，不要现在开',
  ],
  note:
    'Virtual pass only. Human acceptance is blocked until owner explicitly starts it. No popup was opened in this run.',
};

const outJson = join(outDir, 'VIRTUAL_OWNER_PASS.json');
writeFileSync(outJson, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');

const readme = `# 虚拟人工验收 — 会议纪要

**结果：${receipt.result}**  
生成时间：${receipt.generatedAt}

## 虚拟已跑通

1. **路径 A 短录**：Scan → Connect → Sync short → pending → Import → Minutes → Markdown  
2. **路径 B 主机长会**：Start host → Stop → pending → Import → Minutes → 隐私 Audio/Text  
3. **路径 C 机械语音**：SAPI TTS + sidecar + backend minutes（见 mechanical-voice acceptance）

## 你本人验收时（尚未开始）

见 \`VIRTUAL_OWNER_PASS.json\` 里的 \`humanChecklistWhenReady\`。  
**现在不要做**；等你说「开始人工验收」再开环境/弹窗。

## 复跑虚拟

\`\`\`powershell
cd Companion-Type
npm run verify:virtual-owner-minutes
\`\`\`
`;
writeFileSync(join(outDir, 'README.md'), readme, 'utf8');

console.log(`PASS virtual owner minutes: ${outJson}`);
console.log(`steps=${steps.length} failed=${failed.length}`);
for (const s of steps) {
  console.log(`  [${s.ok ? 'OK' : 'FAIL'}] ${s.n}. ${s.ownerAction} → ${s.note}`);
}
