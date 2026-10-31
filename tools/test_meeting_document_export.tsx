import assert from 'node:assert/strict';
import React from 'react';
import { act, create } from 'react-test-renderer';
import { applyCompanionV1ControlFixture, createCompanionV1Fixture } from '../packages/core/src/companionV1';
import { CompanionDashboard } from '../packages/ui/src/CompanionDashboard';
(globalThis as any).document={activeElement:null,getElementById:()=>null,querySelector:()=>null};
(globalThis as any).HTMLElement=class {};
(globalThis as any).HTMLButtonElement=class extends HTMLElement {};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
async function main(){
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};snapshot.meeting.active=false;
const first=snapshot.host.sessions[0]; snapshot.host.selectedSessionId=first.id;
const calls:any[]=[];
const tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null} onRefresh={()=>{}} onControl={()=>{}} onExportMeeting={async request=>{calls.push(request);return {path:'E:/fictional-output',bytes:200};}}/>);
const text=(n:any):string=>typeof n==='string'?n:(n.children??[]).map(text).join('');
const find=(s:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===s);
await act(async()=>{const b=find('我的记录');assert.ok(b);b!.props.onClick();});
await act(async()=>{const b=tree.root.findAllByType('button').find((n:any)=>n.props.className?.includes('ct-library-card'));assert.ok(b);b!.props.onClick();});
for(const [label,format] of [['导出 Word 文档','docx'],['导出思维导图（.mm）','mindmap']] as const) {
 const button=find(label);assert.ok(button,`missing ${label}`);assert.equal(button!.props.disabled,false);
 await act(async()=>{button!.props.onClick();});
 assert.equal(calls.at(-1).format,format);assert.equal(calls.at(-1).sessionId,first.id);assert.equal(calls.at(-1).meetingMode,'offlineStore');
}
await act(async()=>tree.unmount());console.log('PASS saved meeting Word and mind-map actions request the selected session and mode');

}
main().then(()=>process.exit(0),error=>{console.error(error);process.exit(1);});
