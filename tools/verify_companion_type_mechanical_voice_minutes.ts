/**
 * Mechanical-voice acceptance for Companion meeting minutes.
 *
 * 1) Windows SAPI TTS writes a real WAV + transcript sidecar (spoken script).
 * 2) Core fixture proves Sync-short / host capture → needs_transcription → L0 minutes.
 * 3) Rust backend test proves sidecar ASR + minutes on that WAV.
 * 4) Writes a durable JSON receipt under docs/validation/.
 */
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, statSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import {
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
  selectedCompanionHostSession,
} from '../packages/core/src/companionV1.ts';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const outDir = join(root, 'docs', 'validation', 'companion-type-mechanical-voice-minutes');
const outJson = join(outDir, 'acceptance.json');
const spoken = [
  'Decision: Companion host owns long meeting recordings.',
  'Action owner: Chen due: Friday validates mechanical voice minutes.',
  'Question: is offline needs_transcription explicit?',
].join(' ');

mkdirSync(outDir, { recursive: true });
const wavPath = join(outDir, 'mechanical-meeting.wav');
const sidecarPath = join(outDir, 'mechanical-meeting.transcript.txt');

const tts = spawnSync(
  'pwsh',
  [
    '-NoProfile',
    '-File',
    join(root, 'tools', 'run_companion_type_mechanical_voice_tts.ps1'),
    '-OutWav',
    wavPath,
    '-Text',
    spoken,
    '-OutTranscript',
    sidecarPath,
  ],
  { encoding: 'utf8', cwd: root },
);
assert.equal(tts.status, 0, `TTS failed: ${tts.stdout}\n${tts.stderr}`);
assert.ok(existsSync(wavPath), 'TTS WAV missing');
assert.ok(existsSync(sidecarPath), 'TTS transcript sidecar missing');
const wavBytes = statSync(wavPath).size;
assert.ok(wavBytes > 1000, 'TTS WAV too small');
const wavHeader = readFileSync(wavPath).subarray(0, 12).toString('ascii');
assert.ok(wavHeader.startsWith('RIFF'), 'TTS output is not RIFF/WAV');
assert.ok(wavHeader.includes('WAVE'), 'TTS output is not WAVE');

// Core: device short sync path → pending → import spoken text → L0 minutes.
let snap = createCompanionV1Fixture();
snap = applyCompanionV1ControlFixture(snap, {
  action: 'deviceSyncRecordings',
  title: 'Mechanical short device capture',
  audioPath: wavPath,
  audioBytes: wavBytes,
  durationMs: 4000,
});
const synced = selectedCompanionHostSession(snap);
assert.equal(synced?.source, 'deviceFlash');
assert.equal(synced?.status, 'captured');
assert.equal(synced?.pendingReason, 'needs_transcription');

snap = applyCompanionV1ControlFixture(snap, {
  action: 'meetingImportTranscript',
  transcriptText: spoken,
});
assert.equal(selectedCompanionHostSession(snap)?.pendingReason, null);
snap = applyCompanionV1ControlFixture(snap, { action: 'meetingGenerateMinutes' });
const deviceMinutes = selectedCompanionHostSession(snap);
assert.equal(deviceMinutes?.status, 'minutesReady');
assert.equal(deviceMinutes?.minutes?.source, 'rules_l0');
assert.ok((deviceMinutes?.minutes?.decisions.length ?? 0) >= 1);
assert.ok((deviceMinutes?.minutes?.actionItems.length ?? 0) >= 1);

// Core: host long path.
snap = createCompanionV1Fixture();
snap = applyCompanionV1ControlFixture(snap, {
  action: 'meetingStart',
  title: 'Mechanical host long meeting',
  audioPath: wavPath,
  audioBytes: wavBytes,
});
snap = applyCompanionV1ControlFixture(snap, {
  action: 'meetingStop',
  durationMs: 5000,
  audioBytes: wavBytes,
  audioPath: wavPath,
});
assert.equal(selectedCompanionHostSession(snap)?.pendingReason, 'needs_transcription');
snap = applyCompanionV1ControlFixture(snap, {
  action: 'meetingTranscribeAudio',
  transcriptText: spoken,
});
snap = applyCompanionV1ControlFixture(snap, { action: 'meetingGenerateMinutes' });
const hostMinutes = selectedCompanionHostSession(snap);
assert.equal(hostMinutes?.status, 'minutesReady');
assert.ok(hostMinutes?.exportMarkdown.includes('## Action Items'));

// Rust backend: sidecar ASR + minutes on mechanical WAV (retry once for Windows cargo races).
let cargoOut = '';
let cargoStatus = 1;
for (let attempt = 0; attempt < 2; attempt += 1) {
  const cargo = spawnSync(
    'cargo',
    [
      'test',
      '--manifest-path',
      'apps/windows/src-tauri/Cargo.toml',
      '--lib',
      'mechanical_voice_session_transcribe_and_minutes',
      '--',
      '--nocapture',
    ],
    {
      encoding: 'utf8',
      cwd: root,
      env: {
        ...process.env,
        COMPANION_TYPE_TRANSCRIPT_TEXT: '',
      },
    },
  );
  cargoOut = `${cargo.stdout}\n${cargo.stderr}`;
  cargoStatus = cargo.status ?? 1;
  if (cargoStatus === 0) break;
}
if (cargoStatus !== 0) {
  process.stdout.write(cargoOut);
}
assert.equal(cargoStatus, 0, 'rust mechanical voice test failed');
assert.match(cargoOut, /mechanical_voice_session_transcribe_and_minutes/);

const markdownPath = join(outDir, 'mechanical-meeting-minutes.md');
writeFileSync(markdownPath, hostMinutes?.exportMarkdown ?? '', 'utf8');

const receipt = {
  schema: 'companion_type.mechanical_voice_minutes_acceptance.v1',
  generatedAt: new Date().toISOString(),
  result: 'PASS',
  spokenScript: spoken,
  tts: {
    wavPath,
    wavBytes,
    sidecarPath,
    engine: 'Windows System.Speech SAPI',
  },
  core: {
    deviceFlashPath: {
      status: deviceMinutes?.status,
      pendingAfterSync: 'needs_transcription',
      minutesSource: deviceMinutes?.minutes?.source,
      decisions: deviceMinutes?.minutes?.decisions.length ?? 0,
      actionItems: deviceMinutes?.minutes?.actionItems.length ?? 0,
    },
    hostMicrophonePath: {
      status: hostMinutes?.status,
      minutesSource: hostMinutes?.minutes?.source,
      quality: hostMinutes?.minutes?.quality,
      markdownPath,
    },
  },
  rustBackendTest: {
    filter: 'mechanical_voice_session_transcribe_and_minutes',
    status: 'PASS',
  },
  policy: {
    short: snap.host.recordingPolicy.shortCaptureGuide,
    long: snap.host.recordingPolicy.longMeetingGuide,
  },
  note:
    'Mechanical voice = SAPI TTS WAV. Offline ASR uses transcript sidecar bound to the spoken script; L0 rules_l0 generates draft minutes. Cloud LLM is optional via COMPANION_TYPE_MINUTES_COMMAND.',
};

writeFileSync(outJson, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
console.log(`PASS companion-type mechanical voice minutes: ${outJson}`);
