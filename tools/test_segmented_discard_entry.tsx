import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
const text=(n:any):string=>typeof n==='string'?n:(n.children??[]).map(text).join('');
async function main(){
 let snapshot=createCompanionV1Fixture();snapshot.connected=true;snapshot.device.connected=true;snapshot.device.deviceId='loss-device';
 snapshot.device.recordingCapacity={layoutVersion:1,busy:false,confirmedDiscardSupported:false,usedEntries:3,maxEntries:7,catalogGeneration:9,dataBytes:8380416,freeBytes:16384,largestFreeExtent:16384,protectedBytes:8364032,consumedBytes:0,bytesPerSecond:2100,reserveHeadroom:4096,localLimitSeconds:1800,unsyncedEntries:3,writingEntries:0,consumedEntries:0};
 let calls=0;const props=()=>({snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},onDiscardOldestRecording:async()=>{calls++;return {status:'cancelled' as const,message:'已取消，未发送删除确认。'};}});
 let renderer:any;act(()=>{renderer=create(<CompanionDashboard {...props()}/>)});
 const buttons=()=>renderer.root.findAllByType('button').filter((n:any)=>text(n)==='查看可释放的最旧录音');
 assert.equal(buttons().length,0,'legacy unsupported must remain hidden');
 snapshot=structuredClone(snapshot);snapshot.device.recordingCapacity!.layoutVersion=3;
 act(()=>renderer.update(<CompanionDashboard {...props()}/>));
 assert.equal(buttons().length,1,'segmented device may safely attempt capability preview');
 await act(async()=>{buttons()[0].props.onClick();});assert.equal(calls,1);
 assert.match(text(renderer.toJSON()),/已取消，未发送删除确认/);
 snapshot=structuredClone(snapshot);snapshot.device.recordingCapacity!.busy=true;
 act(()=>renderer.update(<CompanionDashboard {...props()}/>));
 assert.equal(buttons()[0].props.disabled,true,'busy device cannot offer action');
 act(()=>renderer.unmount());console.log('PASS_SEGMENTED_PREVIEW_ENTRY');
}
main().catch(e=>{console.error(e);process.exitCode=1});
