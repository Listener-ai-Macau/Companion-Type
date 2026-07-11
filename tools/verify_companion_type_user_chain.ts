import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

import {
  COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
  COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
  selectedCompanionHostSession,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
} from '../packages/core/src/companionV1.ts';

const OUT_JSON = 'docs/validation/companion-type-user-chain.json';
const OUT_MD = 'docs/validation/companion-type-user-chain.md';

const transcript = [
  'Alex opened the weekly product meeting and reviewed Companion recording status.',
  'Decision: Companion keeps the STM32 flash as a short cache while the host app owns one hour meeting recordings.',
  'Action: Maya will wire the BLE recording trigger into the Windows app before Friday.',
  'Action owner: Chen due: July 5 should validate imported transcripts and exported Markdown.',
  'Question: do we need local wake word before the first hardware beta?',
].join('\n');

const steps: Array<{ label: string; request: CompanionV1ControlRequest }> = [
  { label: 'click Start', request: { action: 'meetingStart', title: 'Companion host workflow' } },
  {
    label: 'click Stop after one hour',
    request: {
      action: 'meetingStop',
      durationMs: COMPANION_V1_LONG_MEETING_TARGET_SECONDS * 1000,
    },
  },
  {
    label: 'import transcript',
    request: {
      action: 'meetingImportTranscript',
      transcriptText: transcript,
    },
  },
  { label: 'generate minutes', request: { action: 'meetingGenerateMinutes' } },
  { label: 'export Markdown', request: { action: 'meetingExportMarkdown' } },
];

let snapshot: CompanionV1Snapshot = createCompanionV1Fixture();
const evidenceSteps = [];

for (const step of steps) {
  snapshot = applyCompanionV1ControlFixture(snapshot, step.request);
  const session = selectedCompanionHostSession(snapshot);
  evidenceSteps.push({
    label: step.label,
    action: step.request.action,
    meetingStatus: snapshot.meeting.status,
    lastControl: snapshot.lastControl,
    selectedSession: session
      ? {
        id: session.id,
        status: session.status,
        durationMs: session.durationMs,
        transcriptSegments: session.transcriptSegments,
        hasMinutes: Boolean(session.minutes),
        exportMarkdownBytes: new TextEncoder().encode(session.exportMarkdown).length,
      }
      : null,
  });
}

const session = selectedCompanionHostSession(snapshot);
assert.ok(session, 'selected session should exist');
assert.equal(snapshot.meeting.status, 'minutesReady');
assert.equal(session.durationMs, 3600000);
assert.equal(session.transcriptSegments, 5);
assert.ok(session.minutes, 'minutes should be generated');
assert.equal(session.minutes.decisions.length, 1);
assert.equal(session.minutes.actionItems.length, 2);
assert.equal(session.minutes.questions.length, 1);
assert.ok(session.exportMarkdown.includes('# Companion host workflow'));
assert.ok(session.exportMarkdown.includes('## Action Items'));
assert.equal(snapshot.host.recordingPolicy.oneHourRawPcmBytes, COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES);

const artifact = {
  schema: 'companion_type.user_chain.v1',
  generatedAt: new Date().toISOString(),
  result: 'PASS',
  validationMode: 'simulated human operation chain',
  policy: snapshot.host.recordingPolicy,
  steps: evidenceSteps,
  finalSession: session,
};

mkdirSync(dirname(OUT_JSON), { recursive: true });
writeFileSync(OUT_JSON, `${JSON.stringify(artifact, null, 2)}\n`);
writeFileSync(OUT_MD, session.exportMarkdown);

console.log(`PASS companion-type user chain: ${OUT_JSON}`);
