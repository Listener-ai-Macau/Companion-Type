import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {companionTranscriptSources,companionTranscriptSourceIsCurrent,companionMinutesReferencedSources} from '../packages/core/src/minutesSources';
import {CompanionTranscriptReview} from '../packages/ui/src/CompanionTranscriptReview';

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
console.log('PASS local ASR approximate source range, review and seek');
