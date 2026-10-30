import assert from 'node:assert/strict';
import React from 'react';import {act,create} from 'react-test-renderer';import {renderToStaticMarkup} from 'react-dom/server';import {PetProfile} from '../apps/windows/src/PetProfile';import {CompanionHelp} from '../packages/ui/src/CompanionHelp';
const uid='120011000d50335754363720',now=1793318400,old=now-86400*8;Date.now=()=>now*1000;
const saved:any={uid,generation:1,personality:0,seed:1,petName:'Companion',ownerName:'',memoryEnabled:true,briefReplies:true,doNotInterrupt:true,memories:[{id:7,createdUtc:old,expiresUtc:0,kind:0,text:'以前的内容'}]};let writes:any[]=[];
(globalThis as any).__petInvoke=async(command:string,args:any)=>{if(command==='get_companion_pet_profile')return {profile:saved,persisted:true,cleanupPending:false,presets:[]};if(command==='save_companion_pet_profile'){writes.push(args.profile);return {profile:args.profile,persisted:true,cleanupPending:false,presets:[]};}throw Error(command)};
let tree:any;await act(async()=>{tree=create(<PetProfile disabled={false} deviceUid={uid}/>)});
await act(async()=>tree.root.findByType('details').props.onToggle({currentTarget:{open:true}}));
const button=(name:string)=>tree.root.findAllByType('button').find((b:any)=>b.children.join('')===name);
await act(async()=>button('查看这只宠物').props.onClick());await act(async()=>button('修改').props.onClick());
await act(async()=>tree.root.findByType('textarea').props.onChange({target:{value:'明天去公园'}}));
await act(async()=>button('保存这条记忆').props.onClick());
assert.equal(writes.length,1);assert.equal(writes[0].memories[0].text,'明天去公园');assert.equal(writes[0].memories[0].createdUtc,now,'修改后的内容应以本次确认时间解释相对日期');assert.equal(writes[0].memories[0].expiresUtc,0);
tree.unmount();
// Changing retention alone must not pretend that the old text was reconfirmed.
writes=[];await act(async()=>{tree=create(<PetProfile disabled={false} deviceUid={uid}/>)});
await act(async()=>tree.root.findByType('details').props.onToggle({currentTarget:{open:true}}));
await act(async()=>button('查看这只宠物').props.onClick());await act(async()=>button('修改').props.onClick());
let expiry=tree.root.findAllByType('select').find((x:any)=>x.props.value==='keep');
await act(async()=>expiry.props.onChange({target:{value:'7'}}));await act(async()=>button('保存这条记忆').props.onClick());
assert.equal(writes[0].memories[0].createdUtc,old);assert.equal(writes[0].memories[0].expiresUtc,now+7*86400);tree.unmount();
// A changed, expired memory needs an explicit new retention choice.
saved.memories[0].expiresUtc=now-100;writes=[];await act(async()=>{tree=create(<PetProfile disabled={false} deviceUid={uid}/>)});
await act(async()=>tree.root.findByType('details').props.onToggle({currentTarget:{open:true}}));
await act(async()=>button('查看这只宠物').props.onClick());await act(async()=>button('修改').props.onClick());
await act(async()=>tree.root.findByType('textarea').props.onChange({target:{value:'明天去公园'}}));
await act(async()=>button('保存这条记忆').props.onClick());assert.equal(writes.length,0);assert.match(JSON.stringify(tree.toJSON()),/原有效期已结束/);
expiry=tree.root.findAllByType('select').find((x:any)=>x.props.value==='keep');await act(async()=>expiry.props.onChange({target:{value:'7'}}));
await act(async()=>button('保存这条记忆').props.onClick());assert.equal(writes[0].memories[0].createdUtc,now);assert.equal(writes[0].memories[0].expiresUtc,now+7*86400);tree.unmount();
console.log('PASS edited confirmation date, unchanged content retention, expired memory requires renewed retention');

const noop=()=>{};const help=renderToStaticMarkup(<CompanionHelp onClose={noop} onDevice={noop} onLibrary={noop} onDiagnostics={noop}/>);
assert.match(help,/宠物怎么玩/);assert.match(help,/id="ct-help-play"/);assert.match(help,/眼神小游戏/);assert.match(help,/向右滑/);assert.match(help,/录音时以录音状态为准/);
console.log('PASS pet interaction help is reachable and describes supported gestures');
