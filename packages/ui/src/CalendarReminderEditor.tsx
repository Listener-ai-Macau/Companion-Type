import {useEffect,useRef,useState} from 'react';
import {confirmedCalendarTime,seedCalendarTime,readableCalendarTime,type CalendarTimeDraft} from './calendarTime';

/** A separate alarm never edits the action's deadline or original wording. */
export function CalendarReminderEditor({deadline,initial,label,disabled,onConfirm,onClose,onPending}:{
  deadline:string;initial?:string;label:string;disabled:boolean;onConfirm:(at:string)=>void;onClose:()=>void;onPending?:(delta:1|-1)=>void;
}){
  const[draft,setDraft]=useState<CalendarTimeDraft>(()=>({...seedCalendarTime(initial??deadline),time:initial?seedCalendarTime(initial).time:'',timed:true,before:false}));
  const dialog=useRef<HTMLDialogElement|null>(null);
  useEffect(()=>{onPending?.(1);dialog.current?.showModal();return()=>{onPending?.(-1);};},[]);
  const result=confirmedCalendarTime(draft),patch=(change:Partial<CalendarTimeDraft>)=>setDraft(current=>({...current,...change}));
  const zoneName=Intl.DateTimeFormat().resolvedOptions().timeZone||'本机时区';
  return <dialog ref={dialog} aria-label={`${label} 独立提醒`} onCancel={event=>{event.preventDefault();onClose();}}
    style={{width:'min(92vw,28rem)',maxHeight:'85vh',overflow:'auto',boxSizing:'border-box',padding:24,border:'1px solid #c7d3c9',borderRadius:16}}>
    <h3>指定提醒时刻</h3>
    <p>截止时间仍为：{readableCalendarTime(deadline)}</p>
    <p className="ct-step-meta">单独选择什么时候提醒你；不会改变本项截止日期和原文。</p>
    <label style={{display:'block',marginBottom:12}}>提醒日期<input type="date" min="0001-01-01" max="9999-12-31" aria-label={`${label} 提醒日期`} value={draft.date} disabled={disabled} onChange={event=>patch({date:event.target.value})}/></label>
    <label style={{display:'block',marginBottom:12}}>提醒时刻<input type="time" aria-label={`${label} 提醒时刻`} value={draft.time} disabled={disabled} onChange={event=>patch({time:event.target.value})}/></label>
    <label style={{display:'block',marginBottom:12}}>时区<select aria-label={`${label} 提醒时区`} value={draft.zone} disabled={disabled} onChange={event=>patch({zone:event.target.value as 'local'|'offset'})}>
      <option value="local">本机时区：{zoneName}</option><option value="offset">明确的 UTC 偏移</option>
    </select></label>
    {draft.zone==='offset'?<label style={{display:'block',marginBottom:12}}>UTC 偏移<input aria-label={`${label} 提醒 UTC 偏移`} value={draft.offset} disabled={disabled} placeholder="+08:00" onChange={event=>patch({offset:event.target.value})}/></label>:null}
    <p role="status">{result.ok?`将在 ${result.label} 提醒`:result.error}</p>
    <p className="ct-step-meta">这项设置随本次日历文件保存；导入后由接收日历负责提醒。</p>
    <div className="ct-button-row"><button type="button" className="ct-action ct-action-primary" disabled={disabled||!result.ok} onClick={()=>{if(result.ok){onConfirm(result.value);onClose();}}}>使用此提醒时刻</button>
      <button type="button" className="ct-action" onClick={onClose}>取消</button></div>
  </dialog>;
}
