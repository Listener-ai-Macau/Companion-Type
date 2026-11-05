import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {applyCompanionV1ControlFixture,createCompanionV1Fixture} from '../packages/core/src/companionV1';
import {CompanionDashboard} from '../packages/ui/src/CompanionDashboard';

(globalThis as any).document={activeElement:null,getElementById:()=>null,querySelector:()=>null};
(globalThis as any).HTMLElement=class {};
(globalThis as any).HTMLButtonElement=class extends HTMLElement {};
(globalThis as any).window={requestAnimationFrame:(fn:()=>void)=>{fn();return 0;},cancelAnimationFrame:()=>{}};
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const copied:string[]=[];
let denyClipboard=false;
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:async(value:string)=>{
  if(denyClipboard)throw Error('Permission denied');copied.push(value);
}}}});
type Preview={contentHash:string;textContent:string};
const pending=()=>{let resolve!:(value:Preview)=>void;const promise=new Promise<Preview>(done=>{resolve=done;});return{promise,resolve};};

async function main(){
 const snapshot=applyCompanionV1ControlFixture(createCompanionV1Fixture(),{action:'meetingLoadDemo'});
 snapshot.host.persistence={status:'ready'};snapshot.meeting.active=false;
 snapshot.host.selectedSessionId=snapshot.host.sessions[0].id;
 const requests:any[]=[];
 let delayed:ReturnType<typeof pending>|null=null;
 const preview=(r:any):Promise<Preview>=>{
   requests.push(r);
   if(delayed)return delayed.promise;
   return Promise.resolve({contentHash:'a'.repeat(64),textContent:r.contentSections.transcript?'录音文字\n李明：11月8日前核对20%差额，尚未确认采购。':'会议纪要\n等待采购核对，不表示已批准。'});
 };
 let tree:any;
 await act(async()=>{tree=create(<CompanionDashboard snapshot={snapshot} surface="windows" busyAction={null} error={null}
   onRefresh={()=>{}} onControl={()=>{}} onPreviewMeetingExport={preview}/>);});
 const button=(name:string)=>{const node=tree.root.findAllByType('button').find((x:any)=>text(x)===name);assert.ok(node,'missing '+name);return node;};
 const input=(name:string)=>{const label=tree.root.findAllByType('label').find((x:any)=>text(x)===name);assert.ok(label,'missing '+name);return label.findByType('input');};
 const check=async(name:string,checked:boolean)=>{await act(async()=>input(name).props.onChange({currentTarget:{checked}}));};
 await act(async()=>button('我的记录').props.onClick());
 await act(async()=>tree.root.findAllByType('button').find((x:any)=>x.props.className?.includes('ct-library-card')).props.onClick());
 await check('整理结果',false);await check('录音文字',true);
 await act(async()=>button('复制所选内容').props.onClick());
 assert.equal(copied.length,1);
 assert.equal(copied[0],'录音文字\n李明：11月8日前核对20%差额，尚未确认采购。');
 assert.deepEqual(requests.at(-1).contentSections,{minutes:false,transcript:true,highlights:false,timeline:false,noteIds:[]});
 assert.match(text(tree.root.findByProps({'aria-label':'所选内容操作结果'})),/已复制所选内容/);

 // A source selection change while the native read is pending must not copy
 // the old result or show a success banner for the new selection.
 delayed=pending();
 await act(async()=>{button('复制所选内容').props.onClick();});
 await check('录音文字',false);await check('整理结果',true);
 await act(async()=>delayed!.resolve({contentHash:'b'.repeat(64),textContent:'旧选择：不应进入剪贴板'}));
 delayed=null;
 assert.equal(copied.length,1);
 assert.equal(tree.root.findAllByProps({'aria-label':'所选内容操作结果'}).length,0);

 // Clipboard denial still offers exactly the saved selected content, without
 // reporting success or exporting any file.
 denyClipboard=true;
 await act(async()=>button('复制所选内容').props.onClick());
 const manual=tree.root.findByProps({'aria-label':'手动复制所选内容'});
 assert.equal(manual.props.value,'会议纪要\n等待采购核对，不表示已批准。');
 assert.equal(copied.length,1);
 assert.match(text(tree.root.findByProps({'aria-label':'所选内容操作结果'})),/自动复制未完成/);
 denyClipboard=false;

 // The existing stop-waiting action prevents any late native response from
 // writing to the clipboard. Returning to an earlier selection is retryable.
 delayed=pending();
 await act(async()=>{button('复制所选内容').props.onClick();});
 await act(async()=>button('取消等待').props.onClick());
 await act(async()=>delayed!.resolve({contentHash:'c'.repeat(64),textContent:'取消后迟到'}));
 delayed=null;
 assert.equal(copied.length,1);
 await act(async()=>button('复制所选内容').props.onClick());
 assert.equal(copied.length,2);
 await check('整理结果',false);
 assert.equal(button('复制所选内容').props.disabled,true);
 await check('录音文字',true);
 delayed=pending();
 await act(async()=>{button('复制所选内容').props.onClick();});
 await act(async()=>tree.unmount());
 delayed.resolve({contentHash:'d'.repeat(64),textContent:'卸载后迟到'});
 await new Promise(done=>setTimeout(done,0));
 assert.equal(copied.length,2);
 console.log('PASS selected saved content, exact clipboard text, source change, denied clipboard fallback, stop/retry, empty selection and unmount');
}
main().then(()=>process.exit(0),error=>{console.error(error);process.exit(1);});
