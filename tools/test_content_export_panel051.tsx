import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {ContentExportPanel} from '../packages/ui/src/ContentExportPanel';
import {shareHandoffMessage} from '../packages/ui/src/shareHandoff';
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
async function main(){
 const calls:{preview:any[];save:any[];copy:any[];share:any[];routes:any[]}={preview:[],save:[],copy:[],share:[],routes:[]};
 let cancelSave=false,failedShare=false,wrongFolderStatus=false,staleCopy=false,tree:any;
 const body='## 录音文字\n李明：20%差额尚未确认。\n## 用户备注\n> The purchase has not been approved.';
 const props={sessionId:'public-session',meetingMode:'offlineStore' as const,sourceVersion:'1',minutes:true,transcript:true,highlights:true,timing:true,exactTiming:true,
   notes:[{id:'translation',text:'AI 材料（请核对）｜英语译文\nThe purchase has not been approved.'},{id:'private',text:'不选这份材料'}],blocked:false,
   unsaved:{title:false,minutes:false,transcript:false,highlights:false,notes:false},
   onPreview:async(r:any)=>{calls.preview.push(r);return{contentHash:'f'.repeat(64),textContent:body};},
   onSave:async(r:any)=>{calls.save.push(r);return cancelSave?null:{path:'E:/public-file.'+r.format,bytes:200};},
   onCopy:async(r:any)=>{calls.copy.push(r);if(staleCopy)throw Error('导出内容已变化，请重新查看当前记录。');return{status:'copied'};},
   onShare:async(r:any,destination?:string)=>{calls.share.push(r);calls.routes.push(destination);if(failedShare)throw Error('分享面板未打开，请保存后分享。');return{status:destination==='folder'&&!wrongFolderStatus?'folderOpened':'opened',fileName:'公开测试.pdf',bytes:200};}};
 await act(async()=>{tree=create(<ContentExportPanel {...props}/>);});
 const button=(name:string)=>{const n=tree.root.findAllByType('button').find((node:any)=>text(node)===name);assert.ok(n,name);return n;};
 const check=async(name:string,value:boolean)=>{const node=tree.root.findAllByType('label').find((node:any)=>text(node)===name)?.findByType('input');assert.ok(node,name);await act(async()=>node.props.onChange({currentTarget:{checked:value}}));};
 await check('整理结果',false);await check('录音文字',true);
 await act(async()=>tree.root.findByProps({'aria-label':'选择材料：AI 材料（请核对）｜英语译文'}).props.onChange({currentTarget:{checked:true}}));
 const choice={minutes:false,transcript:true,highlights:false,timeline:false,noteIds:['translation']};
 for(const [format,label] of [['txt','TXT'],['markdown','Markdown'],['docx','Word'],['pdf','PDF'],['xlsx','Excel'],['mindmap','思维导图（可编辑）'],['pptx','PowerPoint'],['png','思维导图 PNG']]){
   await act(async()=>tree.root.findByProps({'aria-label':'所选内容文件格式'}).props.onChange({currentTarget:{value:format}}));
   await act(async()=>button(`保存 ${label}…`).props.onClick());
   assert.deepEqual(calls.save.at(-1).contentSections,choice);assert.equal(calls.save.at(-1).expectedContentHash,'f'.repeat(64));assert.equal(calls.save.at(-1).format,format);
 }
 cancelSave=true;await act(async()=>button('保存 思维导图 PNG…').props.onClick());assert.match(text(tree.root),/已取消保存/);
 await act(async()=>button('复制所选内容').props.onClick());assert.deepEqual(calls.copy.at(-1).contentSections,choice);assert.match(text(tree.root),/已复制所选内容/);
 staleCopy=true;await act(async()=>button('复制所选内容').props.onClick());assert.match(text(tree.root),/内容已变化/);assert.equal(tree.root.findAllByProps({'aria-label':'手动复制所选内容'}).length,0);
 await act(async()=>button('分享所选文件…').props.onClick());assert.match(text(tree.root),/以接收应用为准/);assert.deepEqual(calls.share.at(-1).contentSections,choice);
 failedShare=true;await act(async()=>button('分享所选文件…').props.onClick());assert.match(text(tree.root),/分享面板未打开/);assert.doesNotMatch(text(tree.root.findByProps({'aria-label':'所选内容操作结果'})),/已打开/);
 assert.equal(calls.routes.at(-1),'system','a failure must not open another app automatically');
 failedShare=false;await act(async()=>button('在文件夹中分享所选文件…').props.onClick());
 assert.equal(calls.routes.at(-1),'folder');assert.deepEqual(calls.share.at(-1).contentSections,choice);
 assert.equal(calls.share.at(-1).expectedContentHash,'f'.repeat(64));
 assert.match(text(tree.root),/文件尚未发送/);assert.match(text(tree.root),/资源管理器/);
 wrongFolderStatus=true;await act(async()=>button('在文件夹中分享所选文件…').props.onClick());
 assert.match(text(tree.root.findByProps({'aria-label':'所选内容操作结果'})),/分享文件夹未打开/);
 assert.throws(()=>shareHandoffMessage({status:'folderOpened',bytes:200},'system'),/分享面板未打开/);
 assert.throws(()=>shareHandoffMessage({status:'sent',bytes:200},'folder'),/分享文件夹未打开/);
 assert.doesNotMatch(shareHandoffMessage({status:'opened',bytes:200}),/已发送|已保存|已打开/);
 await act(async()=>tree.root.findByProps({'aria-label':'所选内容文件格式'}).props.onChange({currentTarget:{value:'srt'}}));
 await act(async()=>button('保存 字幕 SRT…').props.onClick());
 assert.deepEqual(calls.save.at(-1).contentSections,{minutes:false,transcript:true,highlights:false,timeline:true,noteIds:[]});
 const before=calls.preview.length;
 await act(async()=>tree.update(<ContentExportPanel {...props} unsaved={{...props.unsaved,transcript:true}}/>));
 await act(async()=>button('复制所选内容').props.onClick());assert.equal(calls.preview.length,before);assert.match(text(tree.root),/未保存的修改/);
 await act(async()=>tree.unmount());
 console.log('PASS all selected-content formats, explicit material exclusion, native copy/hash, cancel, explicit folder route with exact selection/hash, no automatic fallback or false sent/saved feedback, subtitle scope and unsaved edits');
}
main().then(()=>process.exit(0),error=>{console.error(error);process.exit(1);});
