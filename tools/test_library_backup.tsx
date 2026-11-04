import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionLibraryTools} from '../packages/ui/src/CompanionLibraryTools';
import {createCompanionV1Fixture,applyCompanionV1ControlFixture} from '../packages/core/src/companionV1';
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
async function main(){
 const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});let calls:string[]=[];
 const props={sessions:snapshot.host.sessions,visible:snapshot.host.sessions,selection:{},setSelection:()=>{},filters:{folder:'*',tag:'',favorites:false},setFilters:()=>{},blocked:false,
  onBackup:async()=>{calls.push('backup');return {path:'E:/virtual-backup',sessions:1,files:2,bytes:100};},onRestore:async()=>{calls.push('restore');return snapshot;}};
 let tree:any;await act(async()=>{tree=create(<CompanionLibraryTools {...props}/>)});
 const button=(label:string)=>{let item=tree.root.findAllByType('button').find((b:any)=>text(b)===label);assert.ok(item,label);return item;};
 await act(async()=>button('备份会议库').props.onClick());assert.deepEqual(calls,['backup']);assert.ok(tree.root.findAllByProps({role:'status'}).some((x:any)=>text(x).includes('已备份 1 场会议')));
 await act(async()=>button('从备份恢复').props.onClick());assert.deepEqual(calls,['backup','restore']);assert.ok(tree.root.findAllByProps({role:'status'}).some((x:any)=>text(x).includes('备份已恢复')));
 await act(async()=>tree.update(<CompanionLibraryTools {...props} sessions={[]} visible={[]}/>));
 assert.equal(button('备份会议库').props.disabled,true);assert.equal(button('从备份恢复').props.disabled,false);
 await act(async()=>tree.update(<CompanionLibraryTools {...props} sessions={[]} visible={[]} blocked={true} restoreBlocked={false}/>));
 assert.equal(button('备份会议库').props.disabled,true);assert.equal(button('从备份恢复').props.disabled,false);
 await act(async()=>tree.unmount());console.log('PASS backup and restore controls, results and empty-library restore');
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1)});
