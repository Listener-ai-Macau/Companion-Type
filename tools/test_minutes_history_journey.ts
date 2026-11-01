import assert from 'node:assert/strict';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '@companion-type/core';
import {meetingHasFinalMinutes,meetingJourney} from '../packages/ui/src/CompanionJourney';

const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const row=snapshot.host.sessions[0];
const current=row.minutesByMode!.offlineStore!;
current.status='minutesReady';current.quality='final';current.processing=null;
row.minutes!.quality='final';row.minutes!.processing=null;
const history=[{mode:'offlineStore' as const,archivedAt:'2026-11-02T00:00:00Z',variant:{...current,markdown:'Earlier saved result'}}];
// Native JSON may present history before current mode; property order must not
// change the state or cause an exception when opening a saved meeting.
row.minutesByMode={history,offlineStore:current};
assert.equal(Object.keys(row.minutesByMode)[0],'history');
assert.equal(meetingHasFinalMinutes(row),true);
assert.doesNotThrow(()=>meetingJourney(row,{connected:false,asrReady:true,minutesReady:true}));
row.minutesByMode.offlineStore={...current,quality:'draft'};
assert.equal(meetingHasFinalMinutes(row),false);
row.minutesByMode={history};
assert.equal(meetingHasFinalMinutes(row),true,'older sessions may have only the main saved minutes');
console.log('PASS: archived minutes do not alter the current meeting state');
