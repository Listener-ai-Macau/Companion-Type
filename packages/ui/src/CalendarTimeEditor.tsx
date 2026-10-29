import {useEffect,useRef,useState} from 'react';
import {confirmedCalendarTime,seedCalendarTime,readableCalendarTime,type CalendarTimeDraft} from './calendarTime';

export function CalendarTimeEditor({value,label,disabled,onConfirm,onPending,openRequestKey,openWithTime,scope='item',compact=false}:{
  value:string;label:string;disabled:boolean;onConfirm:(value:string)=>void;onPending?:(delta:1|-1)=>void;openRequestKey?:string;openWithTime?:boolean;scope?:'item'|'common';compact?:boolean;
}){
  const[draft,setDraft]=useState<CalendarTimeDraft|null>(null),dialog=useRef<HTMLDialogElement|null>(null),activePending=useRef<typeof onPending>(undefined);
  const open=!!draft,lastRequested=useRef<string|undefined>(undefined);
  const begin=()=>{if(disabled||draft||activePending.current)return;activePending.current=onPending;onPending?.(1);const seeded=seedCalendarTime(value);setDraft(openWithTime?{...seeded,timed:true}:scope==='common'&&!seeded.date?{...seeded,timed:false}:seeded);};
  useEffect(()=>{if(openRequestKey&&lastRequested.current!==openRequestKey){lastRequested.current=openRequestKey;begin();}},[openRequestKey]);
  const finishPending=()=>{const callback=activePending.current;activePending.current=undefined;callback?.(-1);};
  useEffect(()=>()=>finishPending(),[]);
  useEffect(()=>{if(open&&!dialog.current?.open)dialog.current?.showModal();},[open]);
  const close=()=>{dialog.current?.close();setDraft(null);finishPending();};
  const result=draft?confirmedCalendarTime(draft):null,stale=!!draft&&draft.expected!==value;
  const zoneName=Intl.DateTimeFormat().resolvedOptions().timeZone||'本机时区';
  const patch=(change:Partial<CalendarTimeDraft>)=>setDraft(current=>current?{...current,...change}:current);
  return <>
    <button type="button" className="ct-text-button" disabled={disabled} aria-label={`${label} 确认日历时间`}
      onClick={begin}>{scope==='common'?'确认共同日历日期':compact?'修改截止时间':'确认日历时间'}</button>
    <small className="ct-step-meta" style={{display:'block'}}>{scope==='common'?'一次确认日期或时刻，再应用到多项；不会自动创建日历或提醒。':'只确认本项日期，不会自动创建日历或提醒。'}</small>
    {draft?<dialog ref={dialog} aria-label={`${label} 日历时间`} onCancel={event=>{event.preventDefault();event.stopPropagation?.();close();}} onClose={event=>{event.stopPropagation?.();setDraft(null);finishPending();}}
      style={{width:'min(92vw,28rem)',maxHeight:'85vh',overflow:'auto',boxSizing:'border-box',padding:24,border:'1px solid #c7d3c9',borderRadius:16}}>
      <h3>{compact?'修改这一项的截止时间':'确认日历时间'}</h3>
      {draft.expected?<p className="ct-step-meta" style={{overflowWrap:'anywhere'}}>原时间：{readableCalendarTime(draft.expected)}</p>:null}
      <p className="ct-step-meta">{scope==='common'?'这里只更新共同时间草稿；返回后核对应用范围，再保存清单。原始文字不改。':'这会更新本项清单的时间，原话仍保留。导入日历后需核对截止时间与提醒。'}</p>
      <label style={{display:'block',marginBottom:12}}>日期<input aria-label={`${label} 日历日期`} type="date" min="0001-01-01" max="9999-12-31" value={draft.date} disabled={disabled}
        style={{display:'block',width:'100%',boxSizing:'border-box'}} onChange={event=>patch({date:event.target.value})}/></label>
      <label style={{display:'block',marginBottom:12}}><input type="checkbox" aria-label={`${label} 指定时刻`} checked={draft.timed} disabled={disabled} onChange={event=>patch({timed:event.target.checked})}/> 指定时刻</label>
      {draft.timed?<>
        <label style={{display:'block',marginBottom:12}}>时间（请明确选择）<input type="time" aria-label={`${label} 日历时刻`} value={draft.time} disabled={disabled}
          style={{display:'block',width:'100%',boxSizing:'border-box'}} onChange={event=>patch({time:event.target.value})}/></label>
        <label style={{display:'block',marginBottom:12}}>时区<select aria-label={`${label} 日历时区`} value={draft.zone} disabled={disabled}
          style={{display:'block',width:'100%',boxSizing:'border-box'}} onChange={event=>patch({zone:event.target.value as 'local'|'offset'})}>
          <option value="local">本机时区：{zoneName==='Asia/Shanghai'?'北京时间（Asia/Shanghai）':zoneName}</option><option value="offset">明确的 UTC 偏移</option>
        </select></label>
        {draft.zone==='offset'?<label style={{display:'block',marginBottom:12}}>UTC 偏移<input aria-label={`${label} UTC 偏移`} value={draft.offset} disabled={disabled} placeholder="+08:00"
          style={{display:'block',width:'100%',boxSizing:'border-box'}} onChange={event=>patch({offset:event.target.value})}/></label>:null}
      </>:null}
      <label style={{display:'block',marginBottom:12}}><input type="checkbox" aria-label={`${label} 在此时间之前完成`} checked={!!draft.before} disabled={disabled} onChange={event=>patch({before:event.target.checked})}/> 在此时间之前完成</label>
      {stale?<p className="ct-step-warn" role="alert">这项时间已变化，请取消后重新确认；旧输入未被覆盖。</p>
        :result?.ok?<p role="status">日历截止：{result.label}</p>:<p className="ct-step-meta" role="status">{result&&!result.ok?result.error:''}</p>}
      <p className="ct-step-meta">这里只确认导出用的截止时间，不会自动创建日历或提醒。</p>
      <div className="ct-button-row"><button type="button" className="ct-action ct-action-primary" disabled={disabled||stale||!result?.ok}
        onClick={()=>{if(result?.ok&&!stale){onConfirm(result.value);close();}}}>{compact?'确认这个截止时间':'使用此日历时间'}</button>
        <button type="button" className="ct-action" onClick={close}>取消</button></div>
    </dialog>:null}
  </>;
}
