import React from 'react';
import assert from 'node:assert/strict';
import {act,create} from 'react-test-renderer';
import {ContentExport} from '../apps/mobile/src/ContentExport';

const material='material:137c45e9-e02f-42ad-b05f-316411cbd203';
let tree:any;const calls:any[]=[],saved:string[]=[];
let info:any={key:'public',title:'虚构复盘',binding:'binding-one',libraryToken:'public-library',available:{minutes:true,transcript:true,translation:false,notes:false},materials:[{id:material,title:'已保存周报',edited:true}],minutesStale:false,minutesDraft:false,minutesManual:false,translationStale:false,translationLanguage:'',problems:[]};
const text=(n:any):string=>typeof n==='string'?n:(n?.children??[]).map(text).join('');
const button=(label:string)=>tree.root.findAllByType('button').find((n:any)=>text(n)===label);
const props:any={recordingKey:'public',busy:false,readingPreview:false,panelRef:React.createRef(),initialContent:'minutes',
 onCall:async(method:string,args:any)=>{calls.push({method,args});if(method==='exportInfo')return structuredClone(info);if(method==='prepareExport')return {id:'immutable-copy',filename:'public.'+args.format,mime:'application/test',bytes:100,copyAllowed:true,warnings:[],preview:'saved selected content'};if(method==='shareExport')return {opened:true};if(method==='copyExport')return true;throw Error(method);},
 onRun:async(_label:string,work:any)=>{try{return await work();}catch{return undefined;}},onSave:async(id:string)=>{saved.push(id);return false;},onAudioSave:async()=>{},onMindmap:async()=>{}};
async function main(){
 await act(async()=>{tree=create(<ContentExport {...props}/>);});
 await act(async()=>tree.root.findByType('details').props.onToggle({currentTarget:{open:true}}));
 const checkboxes=()=>tree.root.findAllByType('input');
 assert.equal(checkboxes().length,5);assert.equal(checkboxes()[0].props.checked,true);
 await act(async()=>checkboxes()[4].props.onChange());
 const select=()=>tree.root.findByType('select');
 for(const format of ['pptx','png','mindmap','xlsx']){
   await act(async()=>select().props.onChange({target:{value:format}}));
   await act(async()=>button('保存文件').props.onClick());
   const request=calls.filter(x=>x.method==='prepareExport').at(-1).args;
   assert.deepEqual(request.sections,['minutes',material]);assert.equal(request.format,format);assert.equal(request.binding,'binding-one');assert.equal(request.libraryToken,'public-library');
   assert.equal(saved.at(-1),'immutable-copy');assert.match(text(tree.toJSON()),/已取消保存/);
 }
 await act(async()=>button('分享文件').props.onClick());assert.equal(calls.at(-1).method,'shareExport');assert.match(text(tree.toJSON()),/不代表已经发送/);
 await act(async()=>button('复制所选文字').props.onClick());assert.equal(calls.filter(x=>x.method==='prepareExport').at(-1).args.format,'txt');assert.equal(calls.at(-1).method,'copyExport');
 // A missing/deleted material cannot remain silently selected after rediscovery.
 info={...info,binding:'binding-two',materials:[]};await act(async()=>button('重新读取').props.onClick());
 await act(async()=>button('保存文件').props.onClick());assert.deepEqual(calls.filter(x=>x.method==='prepareExport').at(-1).args.sections,['minutes']);
 await act(async()=>tree.update(<ContentExport {...props} busy={true}/>));assert.equal(button('保存文件').props.disabled,true);assert.equal(button('分享文件').props.disabled,true);
 await act(async()=>tree.unmount());
 console.log('PASS mobile selected saved AI materials; PPTX/PNG/MM/XLSX exact same selection/binding; cancelled save; immutable share/copy; deleted material rediscovery; busy guard. Controlled UI only, no OS dialogs/clipboard.');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
