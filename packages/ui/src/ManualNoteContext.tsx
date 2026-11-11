import type {ReactNode} from 'react';
import type {ManualNoteEvidence,ManualNoteKind} from '../../core/src/manualNoteContext';
import {manualChecklist,MANUAL_CONTEXT_LIMITS} from '../../core/src/manualNoteContext';
import './manualNoteContext.css';

export function sameManualReferences(a:ManualNoteEvidence[]=[],b:ManualNoteEvidence[]=[]):boolean{
 const identity=(item:ManualNoteEvidence)=>JSON.stringify(Object.entries(item).filter(([key,value])=>value!==undefined).sort(([a],[b])=>a.localeCompare(b)));
 return a.length===b.length&&a.every((item,index)=>identity(item)===identity(b[index]));
}
export function addManualReference(current:ManualNoteEvidence[],reference:ManualNoteEvidence):ManualNoteEvidence[]{
 if(current.some(item=>sameManualReferences([{...item,id:''}],[{...reference,id:''}])))return current;
 if(current.length>=MANUAL_CONTEXT_LIMITS.references||current.reduce((n,item)=>n+item.quote.length,0)+reference.quote.length>MANUAL_CONTEXT_LIMITS.totalQuotesUtf16)throw Error('这一条的引用已达到保存范围，请先保存或减少引用；完整资料仍保留。');
 return [...current,reference];
}
export function ManualEvidenceList({references,onRemove,onOpen,disabled=false}:{references:ManualNoteEvidence[];onRemove?:(id:string)=>void;onOpen?:(reference:ManualNoteEvidence)=>Promise<void>;disabled?:boolean}){
 return <div className="manual-evidence-list">{references.map((reference,index)=><details key={reference.id} className="manual-evidence" open={references.length===1}><summary><span>依据 {index+1} · {reference.name}{reference.kind==='document'?' · '+reference.sectionLabel+(reference.row?' · 第'+reference.row+'行':''):''}</span></summary><blockquote>{reference.quote}</blockquote><small>人工选择的保存时摘录 · 不会随原文更新</small><div className="manual-evidence-actions">{onOpen&&<button type="button" disabled={disabled} onClick={()=>void onOpen(reference)}>查看当前依据</button>}{onRemove&&<button type="button" disabled={disabled} onClick={()=>onRemove(reference.id)}>移除此引用</button>}</div></details>)}</div>;
}
export function ManualContextControls({kind,references,onKind,onReferences,onChecklist,disabled=false}:{kind:ManualNoteKind;references:ManualNoteEvidence[];onKind:(kind:ManualNoteKind)=>void;onReferences:(references:ManualNoteEvidence[])=>void;onChecklist:()=>void;disabled?:boolean}){
 return <div className="manual-context-controls"><label>补充类型<select aria-label="补充类型" value={kind} disabled={disabled} onChange={e=>onKind(e.target.value as ManualNoteKind)}><option value="note">普通备注</option><option value="followup">人工跟进</option></select></label>{kind==='followup'&&<><button type="button" disabled={disabled} onClick={onChecklist}>添加可勾选事项</button><small>自己写的跟进清单；每行用 - [ ] 开头，保存后可勾选。它不代表会议已作决定。</small></>}<ManualEvidenceList references={references} onRemove={id=>onReferences(references.filter(item=>item.id!==id))} disabled={disabled}/></div>;
}
export function ManualChecklist({text,onToggle,disabled=false,renderText}:{text:string;onToggle:(offset:number,checked:boolean)=>void;disabled?:boolean;renderText?:(text:string)=>ReactNode}){
 const items=manualChecklist(text),byLine=new Map(items.map(item=>[item.line,item]));
 const show=(value:string)=>renderText?renderText(value):value;
 return <fieldset className="manual-checklist"><legend>人工跟进{items.length?' · '+items.filter(item=>item.checked).length+'/'+items.length+' 已完成':''}</legend>{text.split('\n').map((raw,line)=>{
  const item=byLine.get(line);return item?<label key={line}><input type="checkbox" checked={item.checked} disabled={disabled} onChange={e=>onToggle(item.markerOffset,e.target.checked)}/><span>{show(item.text)}</span></label>:<p key={line} className="manual-followup-line">{show(raw.replace(/\r$/,''))||'\u00a0'}</p>;
 })}</fieldset>;
}
