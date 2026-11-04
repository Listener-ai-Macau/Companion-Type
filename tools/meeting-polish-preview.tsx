// Isolated browser fixture: public meeting text, no installed app or hardware.
import React from 'react';
import {createRoot} from 'react-dom/client';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
import '../packages/ui/src/companionUi.css';
import '../packages/ui/src/companionDesign.css';
import '../packages/ui/src/companionDark.css';
import '../apps/windows/src/workspaceRefinement.css';

const fixture=(window as any).meetingFixture;
const params=new URLSearchParams(location.search);
{
 const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
 snapshot.host.persistence={status:'ready'};
 const row=snapshot.host.sessions[0];
 Object.assign(row,{id:'public-61',title:'超市运营与服务改进会议',source:'importedTranscript',durationMs:3660000,
  audioPath:null,audioBytes:0,audioStored:false,sourceDeviceId:null,deviceRecordingId:null,deviceRecordingKey:null,
  recorderControl:null,recorderControlUncertain:false,chunks:[],transcriptText:fixture.text,transcriptFinal:true,pendingReason:null,captureIncomplete:false});
 row.retention.audioCached=false;row.minutes={...row.minutes!,...fixture.minutes};
 row.minutesByMode={offlineStore:{...row.minutesByMode.offlineStore!,...fixture.minutes,status:'minutesReady'}};
 snapshot.host.sessions=[row];snapshot.host.selectedSessionId=row.id;
 createRoot(document.getElementById('root')!).render(<div className={`ct-windows ${params.get('theme')==='dark'?'ct-theme-dark':''}`}>
  <CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}}
   onSaveMeeting={async()=>snapshot} onAskMeetings={async()=>{throw Error('Isolated visual fixture: no AI requests');}}/>
 </div>);
}
