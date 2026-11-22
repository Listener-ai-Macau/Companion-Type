import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture,companionTranscriptSources,
  companionTranscriptSourceIsCurrent,companionMinutesReferencedSources,companionReviewedTranscript,
  companionMinutesMatchTranscript} from '../packages/core/src';
import {CompanionTranscriptReview} from '../packages/ui/src/CompanionTranscriptReview';

// Software review/navigation contract only; no model, phone, card or cloud is used.
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};
const original=structuredClone(snapshot.host.sessions[0]);
original.transcriptFinal=true;
original.transcriptText='先核对预算。\n暂不承诺日期。\n核对后再决定。';
original.utterances=[
  {text:'先核对预算。',startMs:0,endMs:16000,speaker:0,approximateTiming:true},
  {text:'暂不承诺日期。',startMs:16000,endMs:32000,speaker:0,approximateTiming:true},
  {text:'核对后再决定。',startMs:32000,endMs:48000,speaker:null,approximateTiming:true},
];
const reviewed=structuredClone(original);
reviewed.transcriptReview={revision:1,editedAt:'2026-11-04T09:00:00Z',
  sourceTranscriptText:original.transcriptText,sourceUtterances:structuredClone(original.utterances),
  speakerNames:[{speaker:0,name:'小李'}],
  utteranceEdits:[{index:1,text:'暂不承诺日期。',speakerName:'小王'},
    {index:2,text:'核对后再决定。',speakerName:'主持人'}]};

// Saved/reopened JSON has the same human attribution and source revision.
const reopened=JSON.parse(JSON.stringify(reviewed));
const anchors=companionTranscriptSources(reopened);
assert.deepEqual(companionMinutesReferencedSources(anchors,'小李: 先核对预算。').map(row=>row.index),[0],
  'a human-confirmed name must remain locatable without a new speaker model');
assert.deepEqual(companionMinutesReferencedSources(anchors,'小李: 先核对预算。 小王: 暂不承诺日期。').map(row=>row.index),[0]);
assert.deepEqual(companionMinutesReferencedSources(anchors,'主持人: 核对后再决定。').map(row=>row.index),[2]);
assert.deepEqual(companionMinutesReferencedSources(anchors,'小李: 暂不承诺日期。'),[],
  'a name must never be stripped to link another person’s words');
assert.ok(companionReviewedTranscript(reopened).includes('小王: 暂不承诺日期。'));
assert.equal(companionMinutesMatchTranscript(reopened,null),false,'old minutes still require regeneration');
assert.equal(companionMinutesMatchTranscript(reopened,1),true);
assert.ok(anchors.every(row=>companionTranscriptSourceIsCurrent(reopened,row)));
const changed=structuredClone(reopened);changed.transcriptReview.revision=2;
assert.ok(anchors.every(row=>!companionTranscriptSourceIsCurrent(changed,row)));

const repeated=anchors.map(row=>({...row,text:'核对后再决定。'}));
assert.deepEqual(companionMinutesReferencedSources(repeated,'核对后再决定。'),[]);
assert.deepEqual(companionMinutesReferencedSources(repeated,'小王: 核对后再决定。').map(row=>row.index),[1]);
const ambiguous=repeated.map(row=>({...row,speakerLabel:'同名'}));
assert.deepEqual(companionMinutesReferencedSources(ambiguous,'同名: 核对后再决定。'),[]);

const recorded=structuredClone(original);
recorded.utterances![0].text='先核对预算，';
recorded.transcriptText='说话人1: 先核对预算，暂不承诺日期。\n说话人?: 核对后再决定。';
const recordedAnchors=companionTranscriptSources(recorded);
for (const quote of ['先核对预算，暂不承诺日期。','说话人1: 先核对预算，暂不承诺日期。']) {
  assert.deepEqual(companionMinutesReferencedSources(recordedAnchors,quote).map(s=>s.index),[0]);
  assert.deepEqual(companionMinutesReferencedSources(recordedAnchors.filter(s=>s.index!==1),quote),[]);
}
assert.deepEqual(companionMinutesReferencedSources(recordedAnchors,'先核对预算， 暂不承诺日期。'),[]);
const spaced=structuredClone(recorded);
spaced.transcriptText=spaced.transcriptText.replace('预算，暂','预算， 暂');
const spacedAnchors=companionTranscriptSources(spaced);
assert.deepEqual(companionMinutesReferencedSources(spacedAnchors,'先核对预算，暂不承诺日期。'),[]);
assert.deepEqual(companionMinutesReferencedSources(spacedAnchors,'先核对预算， 暂不承诺日期。').map(s=>s.index),[0]);
assert.deepEqual(companionMinutesReferencedSources([{...recordedAnchors[0],text:'原来没有批准。原来没有批准。'}],
  '原来没有批准。'),[]);

let tree:ReturnType<typeof create>;
const sought:typeof anchors=[];
act(()=>{tree=create(<CompanionTranscriptReview session={reopened} visible blocked={false}
  onUnsavedChange={()=>{}} onSeekSource={async source=>{sought.push(source);}}/>);});
const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
const rows=tree!.root.findAllByProps({className:'ct-reviewed-utterance'});
assert.ok(text(rows[0]).includes('小李'),'approximate timing must not hide a saved human name');
assert.ok(text(rows[1]).includes('小王'));
assert.ok(text(rows[2]).includes('主持人'));
assert.ok(text(rows[0]).includes('约 '),'a human name does not upgrade approximate timing to precise timing');
await act(async()=>{await tree!.root.findByProps({'aria-label':'定位第2段原音'}).props.onClick();});
assert.equal(sought[0].index,1);
assert.equal(sought[0].startMs,16000);
assert.equal(sought[0].speakerLabel,'小王');
assert.equal(sought[0].approximateTiming,true);
act(()=>tree!.unmount());
assert.equal(original.transcriptText,'先核对预算。\n暂不承诺日期。\n核对后再决定。');
assert.equal(original.utterances![1].speaker,0,'human corrections must not rewrite the model clusters');
console.log('PASS reviewed people survive reopening, exact source navigation and approximate-time reading without a model');
