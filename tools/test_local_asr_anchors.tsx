import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {companionTranscriptSources,companionTranscriptSourceIsCurrent,companionMinutesReferencedSources} from '../packages/core/src/minutesSources';
import {CompanionTranscriptReview} from '../packages/ui/src/CompanionTranscriptReview';
import {companionReviewedTranscript,companionReviewedUtterances} from '../packages/core/src/transcriptReview';

const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
const session=snapshot.host.sessions[0];
session.transcriptText='今天下午三点开会。\n记得带蓝色文件夹。';session.transcriptFinal=true;
session.utterances=[{text:'今天下午三点开会。',startMs:0,endMs:16000,speaker:null,approximateTiming:true},
  {text:'记得带蓝色文件夹。',startMs:16000,endMs:32000,speaker:null,approximateTiming:true}];
const sources=companionTranscriptSources(session);
assert.equal(sources.length,2);assert.equal(sources[1].approximateTiming,true);
assert.equal(companionMinutesReferencedSources(sources,'“带蓝色文件夹”')[0].startMs,16000);
assert.equal(companionMinutesReferencedSources(sources,'三点开会。 记得带蓝色')[0].startMs,0,'exact adjacent quote should seek to its first segment');
assert.equal(companionMinutesReferencedSources([sources[0],{...sources[1],index:2}],'三点开会。 记得带蓝色').length,0,'must not bridge a missing segment');
const duplicate=[...sources,{...sources[0],index:2,startMs:32000,endMs:48000}, {...sources[1],index:3,startMs:48000,endMs:64000}];
assert.equal(companionMinutesReferencedSources(duplicate,'三点开会。 记得带蓝色').length,0,'ambiguous repeated cross-segment quote must not seek');
const mixed=[...sources,{...sources[1],index:2,text:'三点开会。 记得带蓝色',startMs:32000,endMs:48000}];
assert.equal(companionMinutesReferencedSources(mixed,'三点开会。 记得带蓝色').length,0,'a single-segment and a cross-segment occurrence are ambiguous');
assert.equal(companionMinutesReferencedSources(sources,'三点开会。记得带蓝色').length,0,'unmatched spacing must not fabricate an anchor');
assert.equal(companionTranscriptSourceIsCurrent(session,sources[1]),true);
const changed=structuredClone(session);changed.utterances[1].approximateTiming=false;
assert.equal(companionTranscriptSourceIsCurrent(changed,sources[1]),false,'stale precision must not silently reuse a source link');
const seeked:any[]=[];let tree:any;
act(()=>tree=create(<CompanionTranscriptReview session={session} visible={true} blocked={false}
  onUnsavedChange={()=>{}} onSeekSource={async source=>{seeked.push(source);}}/>));
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
assert.ok(tree.root.findAllByType('time').some((n:any)=>text(n)==='约 0:16–0:32'));
assert.ok(tree.root.findAllByType('strong').some((n:any)=>text(n)==='本地转写分段'));
await act(async()=>tree.root.findByProps({'aria-label':'定位第2段原音'}).props.onClick());
assert.equal(seeked.length,1);assert.equal(seeked[0].startMs,16000);assert.equal(seeked[0].approximateTiming,true);
act(()=>tree.unmount());
const alternative=structuredClone(session);
alternative.transcriptReview={revision:1,editedAt:'now',sourceTranscriptText:session.transcriptText,
  sourceUtterances:structuredClone(session.utterances),text:'重新转写的新文字。',utteranceEdits:[],speakerNames:[]};
assert.equal(companionReviewedTranscript(alternative),'重新转写的新文字。');
assert.equal(companionReviewedUtterances(alternative).length,0);
assert.equal(companionTranscriptSources(alternative).length,0,'a new transcription must not borrow old segment timestamps');
act(()=>tree=create(<CompanionTranscriptReview session={alternative} visible={true} blocked={false}
  onUnsavedChange={()=>{}} onSave={async()=>snapshot}/>));
assert.ok(text(tree.toJSON()).includes('重新转写的新文字。'));
act(()=>tree.root.findAllByType('button').find((n:any)=>text(n)==='修正文字').props.onClick());
assert.equal(tree.root.findByProps({'aria-label':'修订转写全文'}).props.value,'重新转写的新文字。');
act(()=>tree.unmount());
console.log('PASS local ASR approximate source range, review and seek');
