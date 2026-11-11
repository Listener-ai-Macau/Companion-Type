import assert from 'node:assert/strict';
import React from 'react';
import {act,create,type ReactTestRenderer} from 'react-test-renderer';
import {ContentExportPanel,type ContentExportTarget} from '../packages/ui/src/ContentExportPanel';
let tree:ReactTestRenderer,delayed:((value:{contentHash:string;textContent:string})=>void)|undefined;
const calls:any[]=[],saved:any[]=[],copied:any[]=[],shared:any[]=[];
const notes=[{id:'one',text:'- [ ] 我的核对清单\n预算 FALSE 0 尚未确认'},{id:'other',text:'其它备注，不能自动带走'}];
const props={sessionId:'public',meetingMode:'offlineStore' as const,sourceVersion:'r1',minutes:true,transcript:true,highlights:true,timing:true,exactTiming:true,notes,blocked:false,desktopFileSharing:true,unsaved:{title:false,minutes:false,transcript:false,highlights:false,notes:false},
 onPreview:async(request:any)=>{calls.push(request);if(delayed!==undefined)return new Promise<{contentHash:string;textContent:string}>(resolve=>delayed=resolve);return{contentHash:'a'.repeat(64),textContent:'只包含指定人工清单及原文摘录 FALSE 0'};},
 onSave:async(request:any)=>{saved.push(request);return{path:'public.pdf',bytes:10};},onCopy:async(request:any)=>{copied.push(request);return{status:'copied'};},
 onShare:async(request:any,destination:any)=>{shared.push({request,destination});return{status:'fileCopied',bytes:10,fileName:'public.pdf'};}};
const target=(id:string,requestId:string):ContentExportTarget=>({sessionId:'public',noteId:id,requestId});
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>{const node=tree.root.findAllByType('button').find(node=>text(node)===label);assert(node,label);return node;};
await act(async()=>{tree=create(<ContentExportPanel {...props} target={target('one','first')}/>);});
await act(async()=>button('预览所选内容').props.onClick());assert.equal(saved.length+copied.length+shared.length,0);
assert.deepEqual(calls.at(-1).contentSections,{minutes:false,transcript:false,highlights:false,timeline:false,noteIds:['one']});
assert(text(tree.root.findByProps({'aria-label':'所选正文预览'})).includes('FALSE 0'));
await act(async()=>button('保存 PDF…').props.onClick());assert.equal(saved.length,1);assert.equal(saved[0].expectedContentHash,'a'.repeat(64));assert.deepEqual(saved[0].contentSections.noteIds,['one']);
await act(async()=>button('复制所选内容').props.onClick());await act(async()=>button('复制所选文件').props.onClick());assert.equal(copied.length,1);assert.equal(shared.length,1);assert.equal(shared[0].destination,'clipboard');
delayed=()=>{};await act(async()=>{button('保存 PDF…').props.onClick();});const resolve=delayed;
await act(async()=>tree.update(<ContentExportPanel {...props} target={target('other','second')}/>));
await act(async()=>resolve!({contentHash:'b'.repeat(64),textContent:'过期第一张，不可保存'}));assert.equal(saved.length,1);delayed=undefined;
await act(async()=>button('预览所选内容').props.onClick());assert.deepEqual(calls.at(-1).contentSections.noteIds,['other']);
await act(async()=>tree.update(<ContentExportPanel {...props} target={target('missing','third')}/>));assert.equal(button('复制所选内容').props.disabled,true);assert.equal(button('保存 PDF…').props.disabled,true);assert(text(tree.toJSON()).includes('尚未导出其它内容'));
await act(async()=>tree.update(<ContentExportPanel {...props} unsaved={{...props.unsaved,notes:true}} target={target('one','fourth')}/>));
await act(async()=>button('复制所选内容').props.onClick());assert.equal(copied.length,1);assert(text(tree.toJSON()).includes('未保存的修改'));
act(()=>tree.unmount());
console.log('PASS Windows per-note exact scope, visible preview, same content-hash save/copy/file handoff, stale intent suppression, missing-note no broadening and unsaved guard.');
