import {useEffect,useRef,useState} from 'react';
import type {CompanionCalendarCopy,CompanionCalendarSlotCopy} from '@companion-type/core';
import {savedSlotFor,readableSlot} from './calendarSavedSlot';
import {calendarAlarmLabel,effectiveCalendarAlarm,type CalendarAlarm,type CalendarExportItem,type CalendarReminderChoice} from './CalendarExportItems';
import {readableCalendarTime} from './calendarTime';

const alarmText=(value:string)=>value.replace(/^提醒：/,'');
const oldAlarm=(entry:CompanionCalendarCopy['entries'][number])=>alarmText(calendarAlarmLabel(entry.reminderAt?{kind:'at',at:entry.reminderAt}:entry.reminderMinutes===null?{kind:'none'}:{kind:'before',minutes:entry.reminderMinutes}));
const currentTime=(item:CalendarExportItem,choice:CalendarReminderChoice)=>{const slot=choice.calendarSlots?.find(s=>s.uid===item.uid)?.slot;return item.status==='completed'?'已完成，本次不导出':item.status==='unconfirmed'?`时间尚未确认，本次不导出${item.deadline?`：${item.deadline}`:''}`:`${readableCalendarTime(item.deadline??'')}${item.status==='allDay'&&!slot?'（全天）':''}${slot?`；执行时段：${readableSlot(slot)}`:''}`;};
const currentAlarm=(item:CalendarExportItem,choice:CalendarReminderChoice)=>item.status==='completed'||item.status==='unconfirmed'?'本次不导出提醒':alarmText(calendarAlarmLabel(effectiveCalendarAlarm(item,choice)));

function ComparisonCopy({oldTitle,text}:{oldTitle:string;text:string}) {
  const [feedback,setFeedback]=useState<{message:string;text?:string}|null>(null);
  const request=useRef(0),alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const copy=async(value:string,nameOnly:boolean)=>{
    const id=++request.current;setFeedback(null);
    try{await navigator.clipboard.writeText(value);if(alive.current&&id===request.current)setFeedback({message:nameOnly?'已复制原日程名称，可在接收日历搜索。':'已复制改期对照，请在接收日历核对后修改。'});}
    catch{if(alive.current&&id===request.current)setFeedback({message:'无法直接复制，可选中下面的文字复制。',text:value});}
  };
  return <div>
    <div className="ct-action-row"><button type="button" className="ct-action" onClick={()=>void copy(oldTitle,true)}>复制原日程名称</button>
      <button type="button" className="ct-action" onClick={()=>void copy(text,false)}>复制改期对照</button></div>
    {feedback?<div role="status"><p>{feedback.message}</p>{feedback.text?<textarea readOnly aria-label="改期对照复制文字" value={feedback.text} onFocus={event=>event.currentTarget.select()} style={{width:'100%',minHeight:140,boxSizing:'border-box'}}/>:null}</div>:null}
  </div>;
}

/** Reading only. The user chooses both entries; names, positions and dates do
 * not establish identity or prove that an external calendar imported a file. */
export function CalendarCopyComparison({copies,items,choice,slotCopies,onUseReminder,disabled=false}:{copies:CompanionCalendarCopy[];items:CalendarExportItem[];choice:CalendarReminderChoice;slotCopies?:CompanionCalendarSlotCopy[];onUseReminder?:(uid:string,reminder:CalendarAlarm)=>void;disabled?:boolean}) {
  const [fileIndex,setFileIndex]=useState(0),[oldIndex,setOldIndex]=useState(''),[currentIndex,setCurrentIndex]=useState('');
  const copy=copies[fileIndex];if(!copy||!items.length)return null;
  const old=oldIndex===''?undefined:copy.entries[Number(oldIndex)],current=currentIndex===''?undefined:items[Number(currentIndex)];
  const reusable:CalendarAlarm|undefined=old&&current&&current.uid&&copy.entries.filter(entry=>entry.uid===old.uid).length===1&&items.filter(item=>item.uid===current.uid).length===1&&(current.status==='timed'||current.status==='allDay')
    ?old.reminderAt&&old.reminderMinutes==null?{kind:'at',at:old.reminderAt}
      :!old.reminderAt&&old.reminderMinutes==null?{kind:'none'}
      :!old.reminderAt&&old.reminderMinutes!=null&&[0,30,60,1440].includes(old.reminderMinutes)&&current.status==='timed'?{kind:'before',minutes:old.reminderMinutes}
      :undefined
    :undefined;
  const oldSlot=old?savedSlotFor(copy,old.uid,slotCopies):undefined;
  const when=new Date(copy.savedAt),saved=Number.isNaN(when.getTime())?'保存时间待核对':when.toLocaleString('zh-CN',{hour12:false});
  const comparison=old&&current?[`改期对照（请确认是同一事项）`,`原文件：${copy.fileName}\n保存时间：${saved}`,`原日程名称：${old.title}\n原时间：${readableCalendarTime(old.deadline)}${oldSlot?`\n原执行时段：${readableSlot(oldSlot)}`:''}\n原提醒：${oldAlarm(old)}`,`当前事项：${current.title}\n当前时间：${currentTime(current,choice)}\n当前提醒：${currentAlarm(current,choice)}`,'本对照未修改接收日历，也不能确认旧文件已导入。请找到原日程，核对后修改；重新导入可能产生重复。'].join('\n\n'):'';
  return <details className="ct-calendar-comparison">
    <summary>对照旧日程与本次日期、提醒</summary>
    <p className="ct-step-meta">如果以前导入过日历，选择当时的文件和要核对的两项。先确认是同一件事，再到接收日历修改原日程。</p>
    <label>对照文件<select aria-label="改期对照文件" value={fileIndex} onChange={event=>{setFileIndex(Number(event.currentTarget.value));setOldIndex('');setCurrentIndex('');}}>
      {copies.map((c,i)=><option key={`${c.fileSha256}:${c.savedAt}`} value={i}>{i===0?'最近保存':'上一份副本'}：{c.fileName} · {new Date(c.savedAt).toLocaleString('zh-CN',{hour12:false})}</option>)}
    </select></label>
    <p className="ct-step-meta">文件已保存；是否导入接收日历未知。</p>
    <div className="ct-calendar-comparison-columns">
      <section aria-label="原文件中的日程"><h4>原文件中的日程</h4>
        <select aria-label="要查找的原日程" value={oldIndex} onChange={event=>setOldIndex(event.currentTarget.value)}>
          <option value="">选择原日程…</option>{copy.entries.map((entry,i)=><option key={`${entry.uid}:${i}`} value={i}>{i+1}. {entry.title} · {readableCalendarTime(entry.deadline)}</option>)}
        </select>
        {old?<p><strong>{old.title}</strong><br/>原时间：{readableCalendarTime(old.deadline)}{oldSlot?<><br/>原执行时段：{readableSlot(oldSlot)}</>:null}<br/>原提醒：{oldAlarm(old)}</p>:null}
      </section>
      <section aria-label="当前预览中的事项"><h4>当前预览中的事项</h4>
        <select aria-label="要对照的当前事项" value={currentIndex} onChange={event=>setCurrentIndex(event.currentTarget.value)}>
          <option value="">选择当前事项…</option>{items.map((item,i)=><option key={`${item.uid??'no-uid'}:${i}`} value={i}>{i+1}. {item.title} · {currentTime(item,choice)}</option>)}
        </select>
        {current?<p><strong>{current.title}</strong><br/>当前时间：{currentTime(current,choice)}<br/>当前提醒：{currentAlarm(current,choice)}</p>:null}
      </section>
    </div>
    {old&&current?<><p className="ct-step-meta">这是你选出的两项对照，尚未修改接收日历。请核对名称、原日期和条件，避免改错事项。</p>
      {onUseReminder&&reusable&&current.uid?<><p className="ct-step-meta">确认是同一事项后，可以把上方原提醒用于本次日历。具体时刻不会随截止日期自动移动，请先核对。</p>
        <button type="button" className="ct-text-button" disabled={disabled} onClick={()=>onUseReminder(current.uid!,reusable)}>将原提醒用于当前事项</button></>:null}
      <ComparisonCopy key={comparison} oldTitle={old.title} text={comparison}/></>:null}
  </details>;
}
