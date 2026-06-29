import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';

import {
  COMPANION_V1_GATT_BOUNDARY,
  applyCompanionV1ControlFixture,
  characteristicForCompanionAction,
  companionActionPayloadHex,
  companionBleNameIsValid,
  createCompanionV1Fixture,
} from './companionV1.ts';

assert.equal(companionBleNameIsValid('companion-v1'), true);
assert.equal(companionBleNameIsValid('companion lab'), true);
assert.equal(companionBleNameIsValid(''), false);
assert.equal(companionBleNameIsValid('companion=lab'), false);
assert.equal(companionBleNameIsValid('companion-123456789012345678901'), false);

const initial = createCompanionV1Fixture();
assert.equal(initial.schema, 'companion.host.v1');
assert.equal(initial.connected, false);
assert.equal(initial.gatt.meetingControlUuid, COMPANION_V1_GATT_BOUNDARY.meetingControlUuid);

const named = applyCompanionV1ControlFixture(initial, {
  action: 'stageBleName',
  bleName: 'companion-v1',
});
assert.equal(named.bleName.stagedName, 'companion-v1');
assert.equal(named.bleName.pendingRestart, true);
assert.equal(named.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.bleNameConfigUuid);
assert.equal(named.lastControl?.payloadHex.startsWith('011d'), true);

const finalized = applyCompanionV1ControlFixture(initial, { action: 'meetingFinalize' });
assert.equal(finalized.meeting.status, 'finalized');
assert.equal(finalized.meeting.transcriptCount, 1);
assert.equal(finalized.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.meetingControlUuid);

const wakeDetected = applyCompanionV1ControlFixture(initial, { action: 'wakeTestDetect' });
assert.equal(wakeDetected.wakeWord.armed, true);
assert.equal(wakeDetected.wakeWord.confidence, 0.92);
assert.equal(wakeDetected.lastControl?.characteristicUuid, COMPANION_V1_GATT_BOUNDARY.wakeWordControlUuid);

assert.equal(characteristicForCompanionAction('speakerPrompt'), COMPANION_V1_GATT_BOUNDARY.speakerControlUuid);
assert.equal(companionActionPayloadHex({ action: 'speakerPrompt' }), '01');
assert.throws(() => applyCompanionV1ControlFixture(initial, { action: 'stageBleName', bleName: 'bad=name' }));

if (process.argv.includes('--write-docs')) {
  const artifact = {
    schema: 'companion_type.core_fixture.v1',
    generatedAt: new Date().toISOString(),
    gatt: COMPANION_V1_GATT_BOUNDARY,
    snapshots: {
      initial,
      named,
      finalized,
      wakeDetected,
    },
  };
  mkdirSync('docs/validation', { recursive: true });
  writeFileSync('docs/validation/companion-type-core-fixture.json', `${JSON.stringify(artifact, null, 2)}\n`);
  console.log('companion-type: wrote docs/validation/companion-type-core-fixture.json');
} else {
  console.log('companion-type: core assertions passed');
}

