import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

(globalThis as any).document={activeElement:null,getElementById:()=>null};
(globalThis as any).HTMLElement=class {};
(globalThis as any).HTMLButtonElement=class extends HTMLElement {};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;}};
const snapshot=createCompanionV1Fixture();
const settings={defaultMeetingMode:'offlineStore',asrProvider:'volcengine',localAsrAvailable:false,
  volcAppKeySet:false,volcAccessKeySet:false,volcResourceId:'volc.bigasr.sauc.duration',
  openaiAsrEndpoint:'https://example.invalid/transcriptions',openaiAsrApiKeySet:false,openaiAsrModel:'fake',
  deepseekApiKeySet:false,deepseekBaseUrl:'https://example.invalid',deepseekModel:'fake',
  deepseekMinutesEnabled:false,bleCompress:false,settingsPath:'synthetic'};
let prepared=0;const saved:any[]=[];
const props=()=>({snapshot,productSettings:settings,surface:'windows' as const,busyAction:null,error:null,
  onRefresh:()=>{},onControl:()=>{},onPrepareLocalAsr:async()=>{prepared++;},onSaveProductSettings:async(value:unknown)=>{saved.push(value);}});
let renderer:any;act(()=>{renderer=create(<CompanionDashboard {...props()}/>);});
const text=(node:any):string=>typeof node==='string'?node:(node.children??[]).map(text).join('');
const button=(label:string)=>renderer.root.findAllByType('button').find((b:any)=>text(b)===label);
act(()=>button('设置与工具').props.onClick());
const select=renderer.root.findAllByType('select').find((s:any)=>s.findAllByType('option').some((o:any)=>o.props.value==='local-paraformer'));
assert.ok(select,'local recognition should be selectable');
act(()=>select.props.onChange({target:{value:'local-paraformer'}}));
assert.ok(button('准备本地转写模型'));
await act(async()=>{button('准备本地转写模型').props.onClick();await Promise.resolve();});
assert.equal(prepared,1);
await act(async()=>{button('保存设置').props.onClick();await Promise.resolve();await Promise.resolve();});
assert.equal(saved.at(-1)?.asrProvider,'local-paraformer');
settings.asrProvider='local-paraformer';settings.localAsrAvailable=true;
act(()=>renderer.update(<CompanionDashboard {...props()}/>));
assert.ok(renderer.root.findAll((n:any)=>n.type==='span'&&text(n)==='本地模型已准备').length>0);
console.log('PASS local transcription settings and preparation entry');
