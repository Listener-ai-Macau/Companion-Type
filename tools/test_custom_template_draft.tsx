import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';

const data=new Map<string,string>(); let failWrites=false;
const storage={getItem:(key:string)=>data.get(key)??null,
  setItem:(key:string,value:string)=>{if(failWrites) throw Error('storage unavailable');data.set(key,value);},
  removeItem:(key:string)=>data.delete(key),key:(index:number)=>[...data.keys()][index]??null,
  get length(){return data.size;}};
(globalThis as any).window={localStorage:storage};(globalThis as any).localStorage=storage;
(globalThis as any).document={getElementById:()=>null};
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'}; snapshot.meeting.active=false;
const session=snapshot.host.sessions[0];snapshot.host.selectedSessionId=session.id;
session.status='transcribed';session.transcriptText='虚构会议文字';session.transcriptFinal=true;
let backedUp:any;
const props={snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
  onBackupLibrary:async(draft:any)=>{backedUp=draft;return null;}};
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
let tree:any;
function mount(){act(()=>{tree=create(<CompanionDashboard {...props}/>);});
  act(()=>tree.root.findByProps({'aria-label':'整理视角'}).props.onChange({target:{value:'custom'}}));}
mount();
act(()=>tree.root.findByProps({'aria-label':'模板名称'}).props.onChange({target:{value:'项目会议'}}));
act(()=>tree.root.findByProps({'aria-label':'整理要求'}).props.onChange({target:{value:'按项目列出结论和下一步'}}));
act(()=>tree.unmount());mount();
assert.equal(tree.root.findByProps({'aria-label':'模板名称'}).props.value,'项目会议');
assert.equal(tree.root.findByProps({'aria-label':'整理要求'}).props.value,'按项目列出结论和下一步');
failWrites=true;
act(()=>tree.root.findByProps({'aria-label':'整理要求'}).props.onChange({target:{value:'新的要求'}}));
assert.equal(tree.root.findByProps({'aria-label':'整理要求'}).props.value,'新的要求','a storage error must not discard the current input');
assert.match(text(tree.toJSON()),/模板未能保存到本机/);
const backup=tree.root.findAllByType('button').find((button:any)=>text(button)==='备份会议库');
assert.ok(backup);assert.equal(backup.props.disabled,false);act(()=>backup.props.onClick());
assert.deepEqual(backedUp,{name:'项目会议',instructions:'新的要求'},'backup must receive the current input even after a storage write failure');
failWrites=false;
act(()=>tree.root.findByProps({'aria-label':'整理要求'}).props.onChange({target:{value:'更新后的要求'}}));
assert.doesNotMatch(text(tree.toJSON()),/模板未能保存到本机/);
act(()=>tree.unmount());mount();
assert.equal(tree.root.findByProps({'aria-label':'整理要求'}).props.value,'更新后的要求');
act(()=>tree.unmount());console.log('PASS template draft persists before organization and survives a write failure');
