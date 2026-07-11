import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

import {
  COMPANION_V1_ASR_UPLOAD_MAX_BYTES,
  COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
  COMPANION_V1_ONE_HOUR_CHUNKS,
  COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
  selectedCompanionHostSession,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
} from '../packages/core/src/companionV1.ts';

const OUT_JSON = 'docs/validation/companion-type-productization-chain.json';
const OUT_MD = 'docs/validation/companion-type-productization-minutes.md';

const transcript = [
  'Alex opened the Companion beta meeting and reviewed the Windows host recording plan.',
  'Decision: Companion-Type owns ASR, BLE device state, OOBE, privacy, and meeting minutes.',
  'Action owner: Maya due: July 6 validates the OpenAI-compatible ASR provider.',
  'Action owner: Chen due: July 7 checks the native BLE device sync path.',
  'Question: should one hour meetings keep raw WAV or move to Opus chunks?',
].join('\n');

const steps: Array<{ label: string; request: CompanionV1ControlRequest }> = [
  { label: 'open setup and run checks', request: { action: 'oobeRunChecks' } },
  { label: 'scan Companion device', request: { action: 'deviceScan' } },
  { label: 'connect Companion device', request: { action: 'deviceConnect', deviceId: 'companion-nucleo-wb55rg' } },
  {
    label: 'sync short device flash recording',
    request: {
      action: 'deviceSyncRecordings',
      title: 'Companion short flash cache',
      audioPath: 'device://companion/flash/latest.wav',
      audioBytes: 1_920_000,
      durationMs: 60_000,
    },
  },
  { label: 'start one hour host meeting', request: { action: 'meetingStart', title: 'Companion beta meeting' } },
  {
    label: 'stop one hour host meeting',
    request: {
      action: 'meetingStop',
      durationMs: COMPANION_V1_LONG_MEETING_TARGET_SECONDS * 1000,
      audioBytes: COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
    },
  },
  { label: 'transcribe captured audio', request: { action: 'meetingTranscribeAudio', transcriptText: transcript } },
  { label: 'generate meeting minutes', request: { action: 'meetingGenerateMinutes' } },
  { label: 'export Markdown', request: { action: 'meetingExportMarkdown' } },
  { label: 'erase selected audio cache', request: { action: 'privacyEraseAudio' } },
  { label: 'erase selected transcript and minutes', request: { action: 'privacyEraseTranscript' } },
];

let snapshot: CompanionV1Snapshot = createCompanionV1Fixture();
const evidenceSteps = [];
let exportedMarkdown = '';

for (const step of steps) {
  snapshot = applyCompanionV1ControlFixture(snapshot, step.request);
  const session = selectedCompanionHostSession(snapshot);
  if (step.request.action === 'meetingExportMarkdown') {
    exportedMarkdown = session?.exportMarkdown ?? '';
  }
  evidenceSteps.push({
    label: step.label,
    action: step.request.action,
    meetingStatus: snapshot.meeting.status,
    device: snapshot.device,
    oobeComplete: snapshot.oobe.complete,
    privacy: snapshot.privacy,
    selectedSession: session
      ? {
        id: session.id,
        title: session.title,
        source: session.source,
        status: session.status,
        durationMs: session.durationMs,
        audioBytes: session.audioBytes,
        chunks: session.chunks.length,
        transcriptSegments: session.transcriptSegments,
        hasMinutes: Boolean(session.minutes),
        exportMarkdownBytes: new TextEncoder().encode(session.exportMarkdown).length,
        retention: session.retention,
      }
      : null,
  });
}

assert.equal(snapshot.oobe.complete, true);
assert.equal(snapshot.device.connected, true);
assert.equal(snapshot.host.recordingPolicy.oneHourChunkCount, COMPANION_V1_ONE_HOUR_CHUNKS);
assert.equal(snapshot.host.recordingPolicy.maxAsrUploadBytes, COMPANION_V1_ASR_UPLOAD_MAX_BYTES);
assert.ok(exportedMarkdown.includes('# Companion beta meeting'));
assert.ok(exportedMarkdown.includes('## Action Items'));
const oneHourStop = evidenceSteps.find((step) => step.action === 'meetingStop')?.selectedSession;
assert.equal(oneHourStop?.chunks, COMPANION_V1_ONE_HOUR_CHUNKS);
assert.equal(snapshot.privacy.audioCacheBytes, 1_920_000);
assert.equal(snapshot.privacy.transcriptBytes, 0);
assert.equal(snapshot.privacy.minutesBytes, 0);

const erasedSession = selectedCompanionHostSession(snapshot);
assert.ok(erasedSession);
assert.equal(erasedSession.audioPath, null);
assert.equal(erasedSession.transcriptText, '');
assert.equal(erasedSession.exportMarkdown, '');

const cargoCommands = [
  ['cargo', ['test', '--manifest-path', 'apps/windows/src-tauri/Cargo.toml', '--lib', 'openai_compatible_provider_posts_audio_multipart', '--', '--nocapture']],
  ['cargo', ['test', '--manifest-path', 'apps/windows/src-tauri/Cargo.toml', '--lib', 'bridge_exposes_native_device_operations', '--', '--nocapture']],
  ['cargo', ['test', '--manifest-path', 'apps/windows/src-tauri/Cargo.toml', '--lib', 'recording_chunk_parser_and_crc_match_firmware_contract', '--', '--nocapture']],
  ['cargo', ['test', '--manifest-path', 'apps/windows/src-tauri/Cargo.toml', '--lib', 'native_recording_wav_writer_uses_pcm16_16k_mono', '--', '--nocapture']],
  ['cargo', ['test', '--manifest-path', 'apps/windows/src-tauri/Cargo.toml', '--lib', 'privacy_manager_deletes_only_owned_audio_cache', '--', '--nocapture']],
] as const;

const commandResults = cargoCommands.map(([command, args]) => {
  const startedAt = new Date().toISOString();
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    encoding: 'utf8',
    env: {
      ...process.env,
      COMPANION_TYPE_HOST_RECORDING_MODE: 'synthetic',
    },
  });
  const report = {
    command: [command, ...args],
    startedAt,
    finishedAt: new Date().toISOString(),
    exitCode: result.status,
    stdoutTail: result.stdout.split(/\r?\n/).slice(-30).join('\n'),
    stderrTail: result.stderr.split(/\r?\n/).slice(-30).join('\n'),
  };
  assert.equal(report.exitCode, 0, `${report.command.join(' ')} failed\n${report.stdoutTail}\n${report.stderrTail}`);
  return report;
});

const artifact = {
  schema: 'companion_type.productization_chain.v1',
  generatedAt: new Date().toISOString(),
  result: 'PASS',
  coverage: {
    realAsrProvider: 'OpenAI-compatible multipart provider verified against local HTTP mock',
    nativeBleBoundary: 'Companion-Type Windows-native BLE scan/connect boundary plus recording_list/chunk parser, CRC/SHA, and WAV export verified without Listener-Type',
    longMeetingPolicy: {
      targetSeconds: COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
      rawPcmBytes: COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
      chunksPerHour: COMPANION_V1_ONE_HOUR_CHUNKS,
      maxAsrUploadBytes: COMPANION_V1_ASR_UPLOAD_MAX_BYTES,
    },
    meetingRecords: 'transcript -> minutes -> Markdown export exercised before privacy erase',
    oobe: 'setup checks passed in operation chain',
    privacyLifecycle: 'audio erase and transcript/minutes erase exercised',
    tauriUserPath: 'same CompanionV1ControlRequest actions are used by the Windows Tauri command surface',
  },
  steps: evidenceSteps,
  exportedMarkdownPath: OUT_MD,
  cargoCommands: commandResults,
};

mkdirSync(dirname(OUT_JSON), { recursive: true });
writeFileSync(OUT_JSON, `${JSON.stringify(artifact, null, 2)}\n`);
writeFileSync(OUT_MD, exportedMarkdown);
console.log(`PASS companion-type productization chain: ${OUT_JSON}`);
