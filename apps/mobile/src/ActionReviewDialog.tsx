import {useEffect,useRef} from 'react';
import type {MobileActionDraft} from './mobileActionEditing';

export function ActionReviewDialog({value,dirty,busy,error,onChange,onSave,onCancel}:{value:MobileActionDraft;dirty:boolean;busy:boolean;error:string;onChange:(value:MobileActionDraft)=>void;onSave:()=>void;onCancel:()=>void}){
 const heading=useRef<HTMLHeadingElement>(null);useEffect(()=>{heading.current?.focus();},[]);
 return <section className="transcript-editor action-review-dialog" role="dialog" aria-modal="true" aria-labelledby="action-review-title" onKeyDown={event=>{
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onCancel();}
  if(event.key==='Tab'){const items=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),textarea:not(:disabled)'));const index=items.indexOf(document.activeElement as HTMLElement);if(event.shiftKey&&index<=0){event.preventDefault();items.at(-1)?.focus();}else if(!event.shiftKey&&index===items.length-1){event.preventDefault();items[0]?.focus();}}
 }}>
  <header className="action-review-head"><button type="button" className="text-button" disabled={busy} onClick={onCancel}>取消</button><h2 id="action-review-title" tabIndex={-1} ref={heading}>核对行动事项</h2><button type="button" className="primary" disabled={busy||!dirty||!value.body.trim()} onClick={onSave}>{busy?'正在保存…':'保存'}</button></header>
  <div className="action-review-body"><span className="action-review-kicker">人工核对</span><h3>把下一步写清楚</h3><p>修改会保存在这份纪要中，编辑前的版本可在历史里查看。</p>{error&&<div className="action-review-error" role="alert">{error}</div>}
   <label>事项内容<textarea aria-label="事项内容" rows={5} maxLength={3000} value={value.body} disabled={busy} onChange={event=>onChange({...value,body:event.target.value})}/></label>
   <label>负责人<input aria-label="事项负责人" maxLength={80} value={value.owner} placeholder="尚未确认可留空" disabled={busy} onChange={event=>onChange({...value,owner:event.target.value})}/></label>
   <label>时间说明<input aria-label="事项时间" maxLength={120} value={value.due} placeholder="例如 周五18:00，或待双方确认" disabled={busy} onChange={event=>onChange({...value,due:event.target.value})}/></label>
   <p className="action-review-note">人工填写的负责人和时间表示你的安排，不会被当作已识别出的会议原话。</p>
   <label className="action-review-check"><input type="checkbox" checked={value.confirmed} disabled={busy} onChange={event=>onChange({...value,confirmed:event.target.checked})}/>这条事项的内容已人工核对</label>
   <label className="action-review-check"><input type="checkbox" checked={value.completed} disabled={busy} onChange={event=>onChange({...value,completed:event.target.checked})}/>标记为已完成</label>
  </div>
 </section>;
}
