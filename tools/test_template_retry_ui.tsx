import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
snapshot.host.persistence={status:'ready'};snapshot.meeting.active=false;
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
async function check(warning?:string){
 const props={snapshot,surface:'windows' as const,busyAction:null,error:null,onRefresh:()=>{},onControl:()=>{},
  onRestoreLibrary:async()=>({...snapshot,templateRestoreOnly:true,templateRestoreWarning:warning})};
 let tree:any;act(()=>{tree=create(<CompanionDashboard {...props}/>);});
 const button=tree.root.findAllByType('button').find((n:any)=>text(n)==='从备份恢复');assert.ok(button);
 await act(async()=>{button.props.onClick();await Promise.resolve();});
 const rendered=text(tree.toJSON());assert.match(rendered,/会议已存在，未覆盖/);
 if(warning){assert.match(rendered,/模拟保存失败/);assert.doesNotMatch(rendered,/已恢复模板/);}
 else assert.match(rendered,/已恢复模板/);
 act(()=>tree.unmount());
}
(async()=>{await check();await check('模拟保存失败');console.log('PASS existing meetings retain accurate template retry success and failure messages');process.exit(0);})().catch(e=>{console.error(e);process.exit(1);});
