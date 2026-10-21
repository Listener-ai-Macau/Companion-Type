import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

import {
  COMPANION_V1_ASR_UPLOAD_MAX_BYTES,
  COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS,
  COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
  COMPANION_V1_ONE_HOUR_CHUNKS,
  COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
  selectedCompanionHostSession,
  type CompanionV1Snapshot,
} from '../packages/core/src/companionV1.ts';

const OUT_JSON = 'docs/validation/companion-type-long-meeting-chain.json';
const OUT_MD = 'docs/validation/companion-type-long-meeting-minutes.md';

const transcript = [
  'Alex opened the one hour product review and summarized Companion recording reliability.',
  'Decision: keep the STM32 flash path as a short cache and use the Windows host for long meetings.',
  'Decision: split a one hour meeting into five minute ASR upload windows.',
  'Action owner: Maya due: July 6 validates the OpenAI-compatible ASR key with a real WAV.',
  'Action owner: Chen due: July 7 checks installed app sync from the Companion board.',
  'Question: do we need local always-on wake word before beta hardware?',
].join('\n');

let snapshot: CompanionV1Snapshot = createCompanionV1Fixture();
snapshot = applyCompanionV1ControlFixture(snapshot, {
  action: 'meetingStart',
  title: 'Companion one hour meeting',
});
snapshot = applyCompanionV1ControlFixture(snapshot, {
  action: 'meetingStop',
  durationMs: COMPANION_V1_LONG_MEETING_TARGET_SECONDS * 1000,
  audioBytes: COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
});

const captured = selectedCompanionHostSession(snapshot);
assert.ok(captured);
assert.equal(captured.durationMs, COMPANION_V1_LONG_MEETING_TARGET_SECONDS * 1000);
assert.equal(captured.audioBytes, COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES);
assert.equal(captured.chunks.length, COMPANION_V1_ONE_HOUR_CHUNKS);
assert.equal(captured.chunks.reduce((sum, chunk) => sum + chunk.bytes, 0), COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES);
assert.ok(captured.chunks.every((chunk) => chunk.durationMs <= COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS * 1000));
assert.ok(captured.chunks.every((chunk) => chunk.bytes < COMPANION_V1_ASR_UPLOAD_MAX_BYTES));
assert.ok(captured.chunks.every((chunk) => chunk.status === 'sealed'));

snapshot = applyCompanionV1ControlFixture(snapshot, {
  action: 'meetingTranscribeAudio',
  transcriptText: transcript,
});
snapshot = applyCompanionV1ControlFixture(snapshot, { action: 'meetingGenerateMinutes' });
snapshot = applyCompanionV1ControlFixture(snapshot, { action: 'meetingExportMarkdown' });

const minutesReady = selectedCompanionHostSession(snapshot);
assert.ok(minutesReady?.minutes);
assert.equal(minutesReady.transcriptSegments, 6);
assert.equal(minutesReady.minutes.decisions.length, 2);
assert.equal(minutesReady.minutes.actionItems.length, 2);
assert.equal(minutesReady.minutes.questions.length, 1);
assert.ok(minutesReady.exportMarkdown.includes('# Companion one hour meeting'));
assert.ok(minutesReady.exportMarkdown.includes('## Decisions'));

snapshot = applyCompanionV1ControlFixture(snapshot, { action: 'privacyEraseAudio' });
const audioErased = selectedCompanionHostSession(snapshot);
assert.equal(audioErased?.audioBytes, 0);
assert.equal(audioErased?.chunks.every((chunk) => chunk.status === 'erased'), true);

const artifact = {
  schema: 'companion_type.long_meeting_chain.v1',
  generatedAt: new Date().toISOString(),
  result: 'PASS',
  targetSeconds: COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
  chunkSeconds: COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS,
  chunkCount: captured.chunks.length,
  rawPcmBytes: COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
  maxAsrUploadBytes: COMPANION_V1_ASR_UPLOAD_MAX_BYTES,
  chunkBytes: captured.chunks.map((chunk) => chunk.bytes),
  chunkDurationsMs: captured.chunks.map((chunk) => chunk.durationMs),
  minutes: {
    transcriptSegments: minutesReady.transcriptSegments,
    decisions: minutesReady.minutes.decisions.length,
    actionItems: minutesReady.minutes.actionItems.length,
    questions: minutesReady.minutes.questions.length,
    markdownPath: OUT_MD,
  },
  privacyAfterErase: {
    audioBytes: audioErased?.audioBytes,
    chunkStatuses: audioErased?.chunks.map((chunk) => chunk.status) ?? [],
  },
  note: 'This is a deterministic one-hour meeting simulation and chunk planner check; it is not a real one-hour microphone soak.',
};

mkdirSync(dirname(OUT_JSON), { recursive: true });
writeFileSync(OUT_JSON, `${JSON.stringify(artifact, null, 2)}\n`);
writeFileSync(OUT_MD, minutesReady.exportMarkdown);
console.log(`PASS companion-type long meeting chain: ${OUT_JSON}`);
