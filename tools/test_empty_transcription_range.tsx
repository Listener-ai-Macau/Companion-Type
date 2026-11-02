import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';

const storage=new Map<string,string>();
(globalThis as any).window={localStorage:{getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),
  removeItem:(k:string)=>storage.delete(k),key:(i:number)=>[...storage.keys()][i]??null,get length(){return storage.size;}}};
(globalThis as any).document={getElementById:()=>({scrollIntoView:()=>{}})};
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};snapshot.meeting.active=false;
const row=snapshot.host.sessions[0];snapshot.host.selectedSessionId=row.id;
Object.assign(row,{status:'needsTranscription',source:'importedAudio',audioPath:'C:/test/no-words.wav',audioStored:true,
  audioBytes:10000,durationMs:300000,transcriptText:'',transcriptFinal:false,transcriptUnrecognized:[]});
row.retention.audioCached=true;
const player={duration:300,currentTime:12.25,readyState:1,paused:true,playbackRate:1,preservesPitch:false,
  pause(){this.paused=true;},play(){this.paused=false;return Promise.resolve();},removeAttribute(){},load(){}};
let captured:any,savedNote:any,tree:any;
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
  onPrepareAudio:async(id:string)=>({sessionId:id,url:'asset://original',sourceIdentity:'a'.repeat(64)}),
  onPreviewGap:async(id:string,range:any)=>{captured={id,range};return {text:'片段识别结果',unrecognized:[]};},
  onSaveNote:async(note:any)=>{savedNote=note;const result=structuredClone(snapshot);
    result.host.sessions[0].meetingNotes=[{id:note.noteId,text:note.text,bookmarkId:null,createdAt:'now',updatedAt:'now'}];return result;}});
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
await act(async()=>{tree=create(<CompanionDashboard {...props()}/>,{createNodeMock:(n:any)=>n.type==='audio'?player:null});});
await act(async()=>{await button('回听').props.onClick();});
const retry=button('转写当前位置起最多 15 秒');assert.ok(retry);assert.equal(retry.props.disabled,false);
await act(async()=>{await retry.props.onClick();});
assert.deepEqual(captured,{id:row.id,range:{startMs:12250,endMs:27250}});
assert.equal(tree.root.findByProps({'aria-label':'单段转写文字'}).props.value,'片段识别结果');
assert.match(text(tree.toJSON()),/并非整场转写/);
assert.equal(row.transcriptText,'');assert.equal(row.transcriptFinal,false);
await act(async()=>{await button('保存为备注').props.onClick();});
assert.match(savedNote.text,/单段重新转写参考/);assert.match(savedNote.text,/片段识别结果/);
assert.equal(row.transcriptText,'');assert.equal(row.transcriptFinal,false);
player.currentTime=298;await act(async()=>{await retry.props.onClick();});
assert.deepEqual(captured.range,{startMs:298000,endMs:300000},'the final interval ends at the original duration');
act(()=>tree.unmount());console.log('PASS selected short range when the full recording has no transcript; original text remains untouched');
