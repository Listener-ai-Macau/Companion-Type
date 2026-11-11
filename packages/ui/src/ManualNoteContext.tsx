import type {ReactNode} from 'react';
import {FileText,Quote,ChevronDown,ArrowUpRight} from 'lucide-react';
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
 return <div className="manual-evidence-list">{references.map((reference,index)=>{
  const location=reference.kind==='document'?reference.sectionLabel+(reference.row?' · 第'+reference.row+'行':''):'录音转写';
  return <div key={reference.id} className="manual-evidence">
   <details className="manual-evidence-excerpt"><summary>
    <span className="manual-evidence-icon" aria-hidden="true">{reference.kind==='document'?<FileText size={16}/>:<Quote size={16}/>}</span>
    <span className="manual-evidence-heading"><span className="manual-evidence-kind">依据 {index+1} · {reference.kind==='document'?'文档摘录':'转写摘录'}</span><strong title={reference.name}>{reference.name}</strong><span className="manual-evidence-location">{location}</span><span className="manual-evidence-hint"><span className="manual-evidence-expand">展开查看摘录</span><span className="manual-evidence-collapse">收起摘录</span></span></span>
    <ChevronDown size={15} className="manual-evidence-chevron" aria-hidden="true"/>
   </summary><blockquote>{reference.quote}</blockquote><small>保存时的原文摘录 · 原文更新后需重新核对</small></details>
   <div className="manual-evidence-actions">{onOpen&&<button type="button" disabled={disabled} onClick={()=>void onOpen(reference)}>查看当前依据<ArrowUpRight size={13} aria-hidden="true"/></button>}{onRemove&&<button type="button" disabled={disabled} onClick={()=>onRemove(reference.id)}>移除此引用</button>}</div>
  </div>;
 })}</div>;
}
export function ManualContextControls({kind,references,onKind,onReferences,disabled=false}:{kind:ManualNoteKind;references:ManualNoteEvidence[];onKind:(kind:ManualNoteKind)=>void;onReferences:(references:ManualNoteEvidence[])=>void;onChecklist?:()=>void;disabled?:boolean}){
 return <div className="manual-context-controls"><label>补充类型<select aria-label="补充类型" value={kind} disabled={disabled} onChange={e=>onKind(e.target.value as ManualNoteKind)}><option value="note">普通备注</option><option value="followup">人工跟进</option></select></label>{kind==='followup'&&<small>自己的跟进与会议结论分开保存，依据可独立核对。</small>}<ManualEvidenceList references={references} onRemove={id=>onReferences(references.filter(item=>item.id!==id))} disabled={disabled}/></div>;
}
export function ManualChecklist({text,onToggle,disabled=false,renderText}:{text:string;onToggle:(offset:number,checked:boolean)=>void;disabled?:boolean;renderText?:(text:string)=>ReactNode}){
 const items=manualChecklist(text),byLine=new Map(items.map(item=>[item.line,item]));
 const show=(value:string)=>renderText?renderText(value):value;
 return <fieldset className="manual-checklist"><legend>人工跟进{items.length?' · '+items.filter(item=>item.checked).length+'/'+items.length+' 已完成':''}</legend>{text.split('\n').map((raw,line)=>{
  const item=byLine.get(line);return item?<label key={line}><input type="checkbox" checked={item.checked} disabled={disabled} onChange={e=>onToggle(item.markerOffset,e.target.checked)}/><span>{show(item.text)}</span></label>:<p key={line} className="manual-followup-line">{show(raw.replace(/\r$/,''))||'\u00a0'}</p>;
 })}</fieldset>;
}
