import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
import {loadPlaybackMemory,savePlaybackMemory,clearSessionPlaybackMemory,clearPlaybackMemory} from '../packages/ui/src/playbackMemory';
// UI requests and preference lifecycle, no physical audio/BLE/cloud or native library claim.
let snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const a=structuredClone(snapshot.host.sessions[0]);a.id='library-a';a.title='访谈 A';a.organization={revision:4,folder:'',tags:[],favorite:false};
const b=structuredClone(a);b.id='library-b';b.title='访谈 B';b.organization.revision=9;
snapshot.host.sessions=[a,b];snapshot.host.selectedSessionId=a.id;let fail=true;const calls:any[]=[];let tree:any;let unsaved=false;
const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},onUnsavedChange:(v:boolean)=>{unsaved=v;},
 onSaveLibraryOrganization:async(request:any)=>{calls.push(request);if(fail)throw Error('another window changed');
  snapshot=structuredClone(snapshot);for(const r of snapshot.host.sessions){r.organization={revision:(r.organization?.revision??0)+1,folder:'工作/访谈',tags:['重点'],favorite:true};}
  tree.update(<CompanionDashboard {...props()}/>);return snapshot;}});
act(()=>{tree=create(<CompanionDashboard {...props()}/>);});
const text=(n:any):string=>typeof n==='string'?n:(n.children??[]).map(text).join('');
const button=(s:string)=>tree.root.findAllByType('button').find((n:any)=>text(n).includes(s));
const set=(name:string,value:any,checkbox=false)=>act(()=>tree.root.findByProps({'aria-label':name}).props.onChange({target:checkbox?{checked:value}:{value}}));
act(()=>button('选择当前筛选结果').props.onClick());set('修改文件夹',true,true);set('目标录音文件夹','工作/访谈');set('批量标签操作','add');set('批量录音标签','重点');set('批量收藏操作','yes');assert.ok(unsaved);
await act(async()=>button('保存 2 场分类').props.onClick());assert.match(text(tree.toJSON()),/选择和输入仍保留/);
assert.equal(tree.root.findByProps({'aria-label':'目标录音文件夹'}).props.value,'工作/访谈');
assert.deepEqual(calls[0],{targets:[{sessionId:a.id,expectedRevision:4},{sessionId:b.id,expectedRevision:9}],folder:'工作/访谈',tags:['重点'],tagAction:'add',favorite:true});
fail=false;await act(async()=>button('保存 2 场分类').props.onClick());assert.match(text(tree.toJSON()),/已保存 2 场/);assert.equal(unsaved,false);
set('筛选录音文件夹','工作');assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,2);
set('筛选录音标签','重点');act(()=>button('只看收藏').props.onClick());assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,2);
snapshot=structuredClone(snapshot);snapshot.host.sessions[1].organization!.favorite=false;act(()=>tree.update(<CompanionDashboard {...props()}/>));
assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,1);
snapshot=structuredClone(snapshot);snapshot.host.sessions[0].organization!.favorite=false;act(()=>tree.update(<CompanionDashboard {...props()}/>));
assert.match(text(tree.toJSON()),/当前筛选没有录音/);act(()=>button('清除分类筛选').props.onClick());assert.equal(tree.root.findAllByProps({className:'ct-library-entry'}).length,2);
snapshot=structuredClone(snapshot);snapshot.meeting.active=true;act(()=>tree.update(<CompanionDashboard {...props()}/>));assert.equal(button('选择当前筛选结果').props.disabled,true);act(()=>tree.unmount());
console.log('PASS library UI: exact batch IDs/revisions, retained failed drafts, durable-success UI, folder descendants/tag/favorite filters, empty recovery and recording gate; component only');

const stored=new Map<string,string>();(globalThis as any).window={localStorage:{get length(){return stored.size;},key:(i:number)=>[...stored.keys()][i]??null,
 getItem:(k:string)=>stored.get(k)??null,setItem:(k:string,v:string)=>stored.set(k,v),removeItem:(k:string)=>stored.delete(k)}};
const identity='a'.repeat(64);const value={version:1 as const,position:10,duration:30,speed:1.5,completed:false};
stored.set(`companion.playback.v1:${identity}`,JSON.stringify(value));const old=loadPlaybackMemory(identity,'one');assert.equal(old.value?.position,10);
assert.ok(savePlaybackMemory(identity,value,'one',old.generation,old.epoch));assert.ok(!stored.has(`companion.playback.v1:${identity}`));
assert.ok(clearSessionPlaybackMemory('one'));assert.ok(savePlaybackMemory(identity,value,'one',old.generation,old.epoch));
assert.equal(loadPlaybackMemory(identity,'one').value,null,'late unmount cannot resurrect deleted-session progress');
stored.set(`companion.playback.v1:${identity}`,JSON.stringify(value));assert.equal(loadPlaybackMemory(identity,'one').value,null,'legacy preference cannot bypass a scoped clear');
const fresh=loadPlaybackMemory(identity,'one');savePlaybackMemory(identity,value,'one',fresh.generation,fresh.epoch);assert.equal(loadPlaybackMemory(identity,'one').value?.position,10);
assert.equal(loadPlaybackMemory('b'.repeat(64),'one').value,null,'same meeting with changed audio resets progress');
const beforeClear=loadPlaybackMemory(identity,'one');stored.set('other-setting','keep');assert.ok(clearPlaybackMemory());
savePlaybackMemory(identity,value,'one',beforeClear.generation,beforeClear.epoch);assert.equal(loadPlaybackMemory(identity,'one').value,null);
stored.set(`companion.playback.v1:${identity}`,JSON.stringify(value));assert.equal(loadPlaybackMemory(identity,'one').value,null,'older apps cannot resurrect legacy progress after explicit global cleanup');
assert.equal(stored.get('other-setting'),'keep');console.log('PASS playback cleanup: R45 migration, scoped clear, legacy fallback suppression, old-player retirement, explicit new listen and global cleanup without resurrection; storage model only');
