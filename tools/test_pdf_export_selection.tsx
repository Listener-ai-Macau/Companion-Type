import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
(globalThis as any).document={activeElement:null,getElementById:()=>null,querySelector:()=>null};
(globalThis as any).HTMLElement=class {};
(globalThis as any).HTMLButtonElement=class extends HTMLElement {};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
async function main(){
 const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});snapshot.host.persistence={status:'ready'};snapshot.meeting.active=false;
 const row=snapshot.host.sessions[0];snapshot.host.selectedSessionId=row.id;const exports:any[]=[],previews:any[]=[];
 const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},onExportMeeting:async(r:any)=>{exports.push(r);return {path:'E:/fictional.pdf',bytes:100};},onPreviewMeetingExport:async(r:any)=>{previews.push(r);return {contentHash:'a'.repeat(64),textContent:'已保存的原文预览'};}});
 let tree:any;await act(async()=>{tree=create(<CompanionDashboard {...props()}/>);});
 const button=(name:string)=>{const b=tree.root.findAllByType('button').find((x:any)=>text(x)===name);assert.ok(b,'missing '+name);return b;};
 const input=(name:string)=>{const l=tree.root.findAllByType('label').find((x:any)=>text(x)===name);assert.ok(l,'missing '+name);return l.findByType('input');};
 await act(async()=>button('我的记录').props.onClick());await act(async()=>tree.root.findAllByType('button').find((x:any)=>x.props.className?.includes('ct-library-card')).props.onClick());
 assert.equal(input('整理结果').props.checked,true);assert.equal(input('录音文字').props.disabled,false);
 await act(async()=>input('整理结果').props.onChange({currentTarget:{checked:false}}));
 await act(async()=>input('录音文字').props.onChange({currentTarget:{checked:true}}));
 await act(async()=>button('预览所选内容').props.onClick());
 assert.deepEqual(previews.at(-1).contentSections,{minutes:false,transcript:true,highlights:false,timeline:false,noteIds:[]});
 assert.equal(tree.root.findByProps({'aria-label':'所选内容预览'}).props.children,'已保存的原文预览');
 await act(async()=>button('保存 PDF…').props.onClick());
 assert.deepEqual(exports.at(-1).contentSections,previews.at(-1).contentSections);assert.equal(exports.at(-1).expectedContentHash,'a'.repeat(64));
 // Saved transcript remains exportable even before AI minutes exist.
 const noMinutes=structuredClone(snapshot);noMinutes.host.sessions[0].minutes=null;noMinutes.host.sessions[0].minutesByMode={offlineStore:null,onlineLive:null};noMinutes.host.sessions[0].exportMarkdown='';
 await act(async()=>tree.update(<CompanionDashboard {...props()} snapshot={noMinutes}/>));
 assert.equal(input('整理结果').props.disabled,true);assert.equal(input('录音文字').props.disabled,false);assert.equal(button('保存 PDF…').props.disabled,false);
 await act(async()=>tree.unmount());console.log('PASS PDF selection, saved-source preview/hash and transcript-only use');
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
