import {useEffect,useRef,useState} from 'react';
import {confirmedCalendarTime,seedCalendarTime,readableCalendarTime,type CalendarTimeDraft} from './calendarTime';
import type {CalendarExecutionSlot} from './CalendarExportItems';

/** A time block is a separate calendar choice, never a checklist edit. */
export function CalendarExecutionSlotEditor({deadline,initial,label,disabled,onConfirm,onClose,onPending}:{
  deadline:string;initial?:CalendarExecutionSlot;label:string;disabled:boolean;
  onConfirm:(slot:CalendarExecutionSlot)=>void;onClose:()=>void;onPending?:(delta:1|-1)=>void;
}){
  const draft=(value:string,existing:boolean):CalendarTimeDraft=>({...seedCalendarTime(value),time:existing?seedCalendarTime(value).time:'',timed:true,before:false});
  const [start,setStart]=useState(()=>draft(initial?.start??deadline,!!initial));
  const [end,setEnd]=useState(()=>draft(initial?.end??deadline,!!initial));
  const dialog=useRef<HTMLDialogElement|null>(null);
  useEffect(()=>{onPending?.(1);dialog.current?.showModal();return()=>{onPending?.(-1);};},[]);
  const from=confirmedCalendarTime(start),to=confirmedCalendarTime(end);
  const ordered=from.ok&&to.ok&&Date.parse(to.value)>Date.parse(from.value);
  const cutoff=deadline.endsWith('前')?deadline.slice(0,-1):deadline;
  const cutoffMs=/^\d{4}-\d{2}-\d{2}T/i.test(cutoff)?Date.parse(cutoff):NaN;
  const extendsPastCutoff=ordered&&to.ok&&Number.isFinite(cutoffMs)&&Date.parse(to.value)>cutoffMs;
  const zoneName=Intl.DateTimeFormat().resolvedOptions().timeZone||'本机时区';
  const timeFields=(name:'开始'|'结束',value:CalendarTimeDraft,set:(patch:Partial<CalendarTimeDraft>)=>void)=><fieldset disabled={disabled} style={{marginBottom:12}}>
    <legend>{name}</legend>
    <label>日期<input type="date" min="0001-01-01" max="9999-12-31" aria-label={`${label} 时段${name}日期`} value={value.date} onChange={event=>set({date:event.target.value})}/></label>
    <label>时刻<input type="time" aria-label={`${label} 时段${name}时刻`} value={value.time} onChange={event=>set({time:event.target.value})}/></label>
    <label>时区<select aria-label={`${label} 时段${name}时区`} value={value.zone} onChange={event=>set({zone:event.target.value as 'local'|'offset'})}>
      <option value="local">本机时区：{zoneName}</option><option value="offset">明确的 UTC 偏移</option>
    </select></label>
    {value.zone==='offset'?<label>UTC 偏移<input aria-label={`${label} 时段${name} UTC 偏移`} value={value.offset} placeholder="+08:00" onChange={event=>set({offset:event.target.value})}/></label>:null}
  </fieldset>;
  return <dialog ref={dialog} aria-label={`${label} 执行时段`} onCancel={event=>{event.preventDefault();onClose();}}
    style={{width:'min(92vw,30rem)',maxHeight:'85vh',overflow:'auto',boxSizing:'border-box',padding:24,border:'1px solid #c7d3c9',borderRadius:16}}>
    <h3>预留执行时段</h3>
    <p>清单截止仍为：{readableCalendarTime(deadline)}</p>
    <p className="ct-step-meta">只改变本次日历的开始和结束，不修改清单截止或原文。已设置的截止提醒仍按截止时间计算。</p>
    <p className="ct-step-meta">旧版本 Type 不能保留执行时段；如需使用旧版本导出，请另存文件，保留当前日历文件。</p>
    {timeFields('开始',start,patch=>setStart(current=>({...current,...patch})))}
    {timeFields('结束',end,patch=>setEnd(current=>({...current,...patch})))}
    <p role="status">{!from.ok?from.error:!to.ok?to.error:!ordered?'结束时刻须晚于开始时刻。':`${from.label} 至 ${to.label}`}</p>
    {extendsPastCutoff?<p className="ct-step-warn">执行时段结束晚于清单截止时间，请确认这是你需要的安排。</p>:null}
    <div className="ct-button-row"><button type="button" className="ct-action ct-action-primary" disabled={disabled||!ordered} onClick={()=>{if(from.ok&&to.ok&&ordered){onConfirm({start:from.value,end:to.value});onClose();}}}>使用此执行时段</button>
      <button type="button" className="ct-action" onClick={onClose}>取消</button></div>
  </dialog>;
}
