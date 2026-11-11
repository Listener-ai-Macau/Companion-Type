import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{
  action:'meetingLoadDemo',title:'示例会议',transcriptText:'小林负责完成界面。',durationMs:12000,
});
const session=snapshot.host.sessions[0];
const markdown='# 示例会议\n\n## Summary\n- 讨论界面。\n\n## Action Items\n- 完成界面 (owner: 小林)\n\n## Decisions\n- 先完成界面。';
if(!session.minutes||!session.minutesByMode?.offlineStore)throw new Error('fixture did not create minutes');
session.minutes={...session.minutes,markdown,source:'llm_deepseek',quality:'final'};
session.minutesByMode={...session.minutesByMode,offlineStore:{...session.minutesByMode.offlineStore,markdown,source:'llm_deepseek',quality:'final'}};
snapshot.host.persistence={status:'ready'};
let renderer:any;
act(()=>{renderer=create(<CompanionDashboard snapshot={snapshot} busyAction={null} error={null} surface="windows"
  onRefresh={()=>{}} onControl={()=>{}} onSaveMeeting={async()=>snapshot} onExportMeeting={async()=>null}
  onPreviewMeetingExport={async()=>({contentHash:'synthetic',textContent:'示例'})}/>);});
const text=(node:any):string=>node==null||typeof node==='boolean'?'':typeof node==='string'||typeof node==='number'?String(node):(node.children??[]).map(text).join('');
const open=renderer.root.findAllByType('button').find((button:any)=>text(button)==='打开整理结果');
assert.ok(open,'saved result entry exists');act(()=>open.props.onClick());
const visibleText=text(renderer.root.findByProps({id:'ct-recording-result'}));
const action=visibleText.indexOf('完成界面'),exportAction=visibleText.indexOf('导出待办 TXT');
assert.ok(action>=0&&exportAction>action,'saved result appears before export controls');
assert.match(visibleText,/负责人/);assert.match(visibleText,/小林/);
act(()=>renderer.unmount());
console.log('PASS saved minutes: action and owner appear before export controls');
