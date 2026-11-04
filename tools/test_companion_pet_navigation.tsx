import assert from 'node:assert/strict';
import React, {useState} from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

function PetDraft(){
  const [value,setValue]=useState('');
  return <label>示例宠物草稿<input aria-label="示例宠物草稿" value={value} onChange={event=>setValue(event.target.value)}/></label>;
}
const props={snapshot:createCompanionV1Fixture(),busyAction:null,error:null,surface:'windows' as const,
  onRefresh:()=>{},onControl:()=>{}};
const text=(node:any):string=>typeof node==='string'?node:(node.children??[]).map(text).join('');
let renderer:any;
act(()=>{renderer=create(<CompanionDashboard {...props} petPanel={<PetDraft/>}/>);});
const nav=()=>renderer.root.findByProps({'aria-label':'主要功能'});
const click=(label:string)=>act(()=>{
  const button=nav().findAllByType('button').find((item:any)=>text(item)===label);
  assert.ok(button,`missing navigation ${label}`);button.props.onClick();
});
const page=()=>renderer.root.findByProps({'aria-label':'宠物与互动'});
assert.equal(page().props.hidden,true,'pet panel begins hidden');
click('我的宠物');assert.equal(page().props.hidden,false,'pet panel is reachable from navigation');
const field=()=>renderer.root.findByProps({'aria-label':'示例宠物草稿'});
act(()=>field().props.onChange({target:{value:'未保存的示例'}}));
click('设置与工具');assert.equal(page().props.hidden,true);
click('我的宠物');assert.equal(field().props.value,'未保存的示例','navigation preserves the mounted draft');
assert.match(text(renderer.root.findByType('h1')),/我的宠物/);
act(()=>renderer.unmount());

act(()=>{renderer=create(<CompanionDashboard {...props}/>);});
assert.equal(nav().findAllByType('button').some((item:any)=>text(item)==='我的宠物'),false,'no empty pet entry without a panel');
act(()=>renderer.unmount());
console.log('PASS pet navigation: accessible entry, mounted draft preserved, no empty entry');
