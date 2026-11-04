import {useEffect,useRef,useState} from 'react';
import {confirmedCalendarTime,readableCalendarTime,type CalendarTimeDraft} from './calendarTime';
import type {CalendarExportItem,CalendarReminderChoice,CalendarReminderSelection} from './CalendarExportItems';

/** One explicit clock applies on each item's own confirmed date. Existing
 * individual choices, including no reminder, remain authoritative by default. */
export function CalendarAllDayReminders({items,choice,disabled,onApply,onClose,onPending}:{
  items:CalendarExportItem[];choice:CalendarReminderChoice;disabled:boolean;
  onApply:(selections:CalendarReminderSelection[])=>void;onClose:()=>void;onPending?:(delta:1|-1)=>void;
}){
  const [clock,setClock]=useState(''),[zone,setZone]=useState<CalendarTimeDraft['zone']>('local'),[offset,setOffset]=useState('+00:00'),[replace,setReplace]=useState(false);
  const dialog=useRef<HTMLDialogElement|null>(null);
  useEffect(()=>{onPending?.(1);dialog.current?.showModal();return()=>{onPending?.(-1);};},[]);
  const all=items.filter(item=>item.status==='allDay'&&item.uid);
  const candidates=all.filter(item=>replace||!choice.calendarReminders?.some(selection=>selection.uid===item.uid));
  const rows=candidates.map(item=>({item,result:confirmedCalendarTime({expected:'',date:(item.deadline??'').replace(/前$/,''),time:clock,timed:true,zone,offset,before:false})}));
  const unique=new Set(all.map(item=>item.uid)).size===all.length;
  const ready=unique&&rows.length>0&&rows.every(row=>row.result.ok);
  const zoneName=Intl.DateTimeFormat().resolvedOptions().timeZone||'本机时区';
  return <dialog ref={dialog} aria-label="全天事项统一提醒" onCancel={event=>{event.preventDefault();onClose();}}
    style={{width:'min(92vw,32rem)',maxHeight:'85vh',overflow:'auto',boxSizing:'border-box',padding:24,border:'1px solid #c7d3c9',borderRadius:16}}>
    <h3>全天事项，在各自当天同一时刻提醒</h3>
    <p>只填一次时刻，按每项已确认的日期分别提醒。事项仍是全天日程，截止日期和原文保持。</p>
    <label style={{display:'block',marginBottom:12}}>当天提醒时刻<input type="time" aria-label="全天统一提醒时刻" value={clock} disabled={disabled} onChange={event=>setClock(event.target.value)}/></label>
    <label style={{display:'block',marginBottom:12}}>时区<select aria-label="全天统一提醒时区" value={zone} disabled={disabled} onChange={event=>setZone(event.target.value as CalendarTimeDraft['zone'])}>
      <option value="local">本机时区：{zoneName==='Asia/Shanghai'?'北京时间（Asia/Shanghai）':zoneName}</option><option value="offset">明确的 UTC 偏移</option>
    </select></label>
    {zone==='offset'?<label style={{display:'block',marginBottom:12}}>UTC 偏移<input aria-label="全天统一提醒 UTC 偏移" value={offset} disabled={disabled} placeholder="+08:00" onChange={event=>setOffset(event.target.value)}/></label>:null}
    <label><input type="checkbox" aria-label="替换全天事项已有提醒" checked={replace} disabled={disabled} onChange={event=>setReplace(event.target.checked)}/> 替换全天事项已有的单独提醒设置</label>
    <p className="ct-step-meta">默认保留已有的单独设置，包括“不提醒”。本次应用后仍可逐项修改。</p>
    {!unique?<p role="alert">事项标识有重复，请取消后重新核对，尚未应用。</p>:null}
    <ul aria-label="全天统一提醒应用预览">{rows.map(({item,result},index)=><li key={`${item.uid}:${index}`} style={{marginBottom:8,overflowWrap:'anywhere'}}>
      <strong>{item.title}</strong><br/>全天日期：{readableCalendarTime(item.deadline??'')}<br/>
      {result.ok?`提醒：${readableCalendarTime(result.value)}`:result.error}
    </li>)}</ul>
    {!rows.length?<p role="status">全天事项均已有单独设置，当前会保留原设置。</p>:null}
    <p className="ct-step-meta">这项选择用于本次日历文件，保存并导入后由接收日历负责提醒。</p>
    <div className="ct-button-row"><button type="button" className="ct-action ct-action-primary" disabled={disabled||!ready} onClick={()=>{
      if(!ready)return;
      const selections:CalendarReminderSelection[]=rows.flatMap(({item,result})=>result.ok?[{uid:item.uid!,reminder:{kind:'at' as const,at:result.value}}]:[]);
      if(selections.length===rows.length){onApply(selections);onClose();}
    }}>应用到这{rows.length}项全天事项</button><button type="button" className="ct-action" onClick={onClose}>取消</button></div>
  </dialog>;
}
