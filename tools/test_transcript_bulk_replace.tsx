import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionTranscriptReview} from '../packages/ui/src/CompanionTranscriptReview';

const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const source=structuredClone(snapshot.host.sessions[0]);
source.transcriptFinal=true;
source.transcriptText='自动化产品的风险。\n自动化产品的收益，自动化产品的监管。';
source.utterances=[
  {text:'自动化产品的风险。',startMs:0,endMs:16000,speaker:0,approximateTiming:true},
  {text:'自动化产品的收益，自动化产品的监管。',startMs:16000,endMs:32000,speaker:1,approximateTiming:true},
];
const requests:any[]=[];let tree:any;
const props=(session:any)=>({session,visible:true,blocked:false,onUnsavedChange:()=>{},onSave:async (request:any)=>{requests.push(request);return snapshot;}});
const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
const button=(name:string)=>tree.root.findAllByType('button').find((node:any)=>text(node)===name);
const set=(name:string,value:string)=>act(()=>tree.root.findByProps({'aria-label':name}).props.onChange({target:{value}}));
act(()=>{tree=create(<CompanionTranscriptReview {...props(source)}/>);});
act(()=>button('修正文字').props.onClick());
assert.equal(button('替换 0 处').props.disabled,true);
set('查找文字','自动化产品');set('替换文字','结构化产品');
assert.equal(button('替换 3 处').props.disabled,false);
act(()=>button('替换 3 处').props.onClick());
assert.equal(tree.root.findByProps({'aria-label':'第1段转写'}).props.value,'结构化产品的风险。');
assert.equal(tree.root.findByProps({'aria-label':'第2段转写'}).props.value,'结构化产品的收益，结构化产品的监管。');
assert.equal(source.transcriptText,'自动化产品的风险。\n自动化产品的收益，自动化产品的监管。','original transcript must stay untouched');
await act(async()=>button('保存转写修订').props.onClick());
assert.deepEqual(requests[0].transcriptReview.utteranceEdits.map((x:any)=>x.text),['结构化产品的风险。','结构化产品的收益，结构化产品的监管。']);
assert.equal(requests[0].transcriptReview.expectedTranscriptText,source.transcriptText);
assert.equal(requests[0].transcriptReview.expectedUtterances[0].text,source.utterances[0].text);
act(()=>tree.unmount());

const plain=structuredClone(source);plain.id='plain';plain.source='importedTranscript';plain.utterances=[];plain.transcriptText='a.b 与 a.b，不是 axb。';
act(()=>{tree=create(<CompanionTranscriptReview {...props(plain)}/>);});act(()=>button('修正文字').props.onClick());
set('查找文字','a.b');set('替换文字','$1');act(()=>button('替换 2 处').props.onClick());
assert.equal(tree.root.findByProps({'aria-label':'修订转写全文'}).props.value,'$1 与 $1，不是 axb。','search and replacement must be literal');
const changed=structuredClone(plain);changed.transcriptText='后台更新的文字';
act(()=>tree.update(<CompanionTranscriptReview {...props(changed)}/>));
set('查找文字','$1');assert.equal(button('替换 2 处').props.disabled,true,'changed source must not accept a stale bulk edit');
assert.equal(tree.root.findByProps({'aria-label':'修订转写全文'}).props.value,'$1 与 $1，不是 axb。','stale draft is retained');
act(()=>button('取消修订').props.onClick());
assert.equal(plain.transcriptText,'a.b 与 a.b，不是 axb。');
act(()=>tree.unmount());
act(()=>{tree=create(<CompanionTranscriptReview {...props(plain)}/>);});act(()=>button('修正文字').props.onClick());
set('查找文字','a.b');act(()=>button('替换 2 处').props.onClick());
assert.equal(tree.root.findByProps({'aria-label':'修订转写全文'}).props.value,' 与 ，不是 axb。');
await act(async()=>button('保存转写修订').props.onClick());
assert.equal(requests[1].transcriptReview.text,' 与 ，不是 axb。');
assert.equal(requests[1].transcriptReview.expectedTranscriptText,plain.transcriptText);
act(()=>tree.unmount());
console.log('PASS transcript replacement is explicit, literal, draft-only and saved through the existing revision');
