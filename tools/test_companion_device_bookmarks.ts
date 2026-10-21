import assert from 'node:assert/strict';
import { applyCompanionV1ControlFixture,createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { companionBookmarkAudioPosition,companionBookmarkUtteranceIndex, type CompanionRecordingBookmark } from '../packages/core/src/recordingBookmarks';

// Source binding and UI navigation only. No physical recording or ASR proof.
const row=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'}).host.sessions[0];
row.audioStored=true;row.retention.audioCached=true;row.audioPath='owned.wav';row.durationMs=140;
row.sourceDeviceId='C8:92:FF:DD:3B:CA';row.deviceRecordingId=901;row.deviceSha256=null;
row.deviceRecordingKey={deviceUid:'35'.repeat(12),formatEpoch:'0000000000000007',sessionId:'0000000000000017'};
const point:CompanionRecordingBookmark={id:'00000000-0000-8000-8000-000000000001',label:'离线重点',
  origin:'boardOffline',positionMs:120,audioPositionMs:100,createdAt:'device-elapsed:1040ms',
  sourceDeviceId:'c892ffdd3bca',recordingId:902,sourceSha256:'a'.repeat(64),sourceRecordingKey:row.deviceRecordingKey};
assert.equal(companionBookmarkAudioPosition(row,point),100,'second physical segment still maps into the same original');
for (const invalid of [
  {...point,sourceRecordingKey:{...row.deviceRecordingKey,sessionId:'0000000000000018'}},
  {...point,sourceDeviceId:'00:11:22:33:44:55'},
  {...point,sourceSha256:null}, {...point,sourceSha256:'not-a-hash'},
  {...point,audioPositionMs:141}, {...point,audioPositionMs:null}, {...point,recordingId:0},
]) assert.equal(companionBookmarkAudioPosition(row,invalid),null);
assert.equal(companionBookmarkAudioPosition({...row,audioStored:false},point),null);
row.transcriptFinal=true;row.utterances=[{speaker:0,startMs:80,endMs:130,text:'实际片段'}];
assert.equal(companionBookmarkUtteranceIndex(row,point),0);
assert.equal(companionBookmarkUtteranceIndex(row,{...point,audioPositionMs:140}),null,'no invented nearest transcript match');
console.log('PASS device bookmark original-key/source binding and exact playback/transcript navigation; UI software only');
