import {useState} from 'react';
import {readableCalendarTime} from './calendarTime';
import {CalendarReminderEditor} from './CalendarReminderEditor';
import {CalendarAllDayReminders} from './CalendarAllDayReminders';

export type CalendarAlarm={kind:'none'}|{kind:'before';minutes:0|30|60|1440}|{kind:'at';at:string};
export type CalendarReminderSelection={uid:string;reminder:CalendarAlarm};
/** Native rows identify the exact source item used by the reviewed file. */
export type CalendarExportItem={uid?:string;text:string;title:string;deadline:string|null;status:'timed'|'allDay'|'unconfirmed'|'completed';reminder?:CalendarAlarm};
export type CalendarReminderChoice={remindAtTime?:boolean;reminderFormat?:'calendarreminder'|'calendarreminder30'|'calendarreminder60';calendarReminders?:CalendarReminderSelection[]};
export function effectiveCalendarAlarm(item:CalendarExportItem,choice:CalendarReminderChoice):CalendarAlarm {
  return choice.calendarReminders?.find(s=>s.uid===item.uid)?.reminder??(choice.remindAtTime&&item.status==='timed'?{kind:'before',minutes:choice.reminderFormat==='calendarreminder'?0:choice.reminderFormat==='calendarreminder60'?60:30}:{kind:'none'});
}
export function calendarAlarmLabel(alarm:CalendarAlarm):string {
  return alarm.kind==='none'?'不提醒':alarm.kind==='at'?`提醒：${readableCalendarTime(alarm.at)}`:alarm.minutes===0?'提醒：在截止时刻':alarm.minutes===60?'提醒：提前1小时':alarm.minutes===1440?'提醒：提前1天':`提醒：提前${alarm.minutes}分钟`;
}
export function CalendarExportItems({items,choice,disabled,onEdit,onReminder,onReminders,onPending}:{
  items:CalendarExportItem[];choice:CalendarReminderChoice;disabled:boolean;onEdit?:(index:number)=>void;
  onReminder?:(uid:string,reminder:CalendarAlarm|null)=>void;onReminders?:(selections:CalendarReminderSelection[])=>void;onPending?:(delta:1|-1)=>void;
}){
  const[editing,setEditing]=useState<number|null>(null);
  const[allDayEditing,setAllDayEditing]=useState(false);
  const included=items.filter(item=>item.status==='timed'||item.status==='allDay');
  const alarms=included.filter(item=>effectiveCalendarAlarm(item,choice).kind!=='none').length;
  return <section aria-label="逐项日历预览">
    <p><strong>将导出{included.length}项日程：{alarms}项附提醒，{included.length-alarms}项不提醒。</strong></p>
    {onReminders&&items.some(item=>item.status==='allDay'&&item.uid)?<button type="button" className="ct-text-button" disabled={disabled} onClick={()=>setAllDayEditing(true)}>全天事项：一次设置当天提醒时刻</button>:null}
    {allDayEditing&&onReminders?<CalendarAllDayReminders key={JSON.stringify([items.filter(item=>item.status==='allDay').map(item=>[item.uid,item.text,item.deadline]),choice.calendarReminders])}
      items={items} choice={choice} disabled={disabled} onApply={onReminders} onClose={()=>setAllDayEditing(false)} onPending={onPending}/>:null}
    <ul>{items.map((item,index)=>{
      const alarm=effectiveCalendarAlarm(item,choice),override=choice.calendarReminders?.find(s=>s.uid===item.uid)?.reminder;
      return <li key={item.uid??index} style={{marginBottom:12,overflowWrap:'anywhere'}}>
        <strong>{item.title}</strong><br/>
        {item.status==='completed'?'已完成，本次不导出':item.status==='unconfirmed'?`时间尚未确认，本次不导出${item.deadline?`：${item.deadline}`:''}`:
          `清单截止：${readableCalendarTime(item.deadline??'')}${item.status==='allDay'?' · 全天日程':''} · ${calendarAlarmLabel(alarm)}`}
        {item.status==='timed'?<p className="ct-step-meta">按截止时刻导出，不预设执行时长。{alarm.kind==='before'&&alarm.minutes===0&&/前|截止|before|by\b/i.test(item.deadline??'')?'当前在截止时才提醒；需要预留准备时间时，可选择提前提醒。':''}</p>:null}
        {onReminder&&item.uid&&(item.status==='allDay'||item.status==='timed')?<label style={{display:'block',marginTop:8}}>本项提醒 <select aria-label={`日历事项 ${index+1} 提醒`} disabled={disabled}
          value={!override?'default':override.kind==='before'?String(override.minutes):override.kind}
          onChange={event=>{const value=event.currentTarget.value;if(value==='at'){setEditing(index);return;}
            onReminder(item.uid!,value==='default'?null:value==='none'?{kind:'none'}:{kind:'before',minutes:Number(value) as 0|30|60|1440});}}>
          <option value="default">{item.status==='timed'&&choice.remindAtTime?`统一设置：${calendarAlarmLabel(effectiveCalendarAlarm(item,{...choice,calendarReminders:undefined}))}`:'不提醒（默认）'}</option><option value="none">不提醒</option>
          {item.status==='timed'?<><option value="0">在截止时刻</option><option value="30">提前30分钟</option><option value="60">提前1小时</option><option value="1440">提前1天</option></>:null}
          <option value="at">指定提醒日期和时刻…</option>
        </select>{override?.kind==='at'?<button type="button" className="ct-text-button" disabled={disabled} onClick={()=>setEditing(index)}>修改提醒时刻</button>:null}</label>:null}
        {onEdit&&item.status!=='completed'?<><br/><button type="button" className="ct-text-button" disabled={disabled}
          aria-label={`日历事项 ${index+1} ${item.status==='allDay'?'补充清单截止时刻':item.status==='unconfirmed'?'确认清单截止日期和时刻':'修改清单截止时间'}`}
          onClick={()=>onEdit(index)}>{item.status==='allDay'?'补充清单截止时刻':item.status==='unconfirmed'?'确认清单截止日期和时刻':'修改清单截止时间'}</button></>:null}
        {editing===index&&item.uid&&onReminder?<CalendarReminderEditor key={item.uid} deadline={item.deadline??''} initial={override?.kind==='at'?override.at:undefined}
          label={`日历事项 ${index+1}`} disabled={disabled} onConfirm={at=>onReminder(item.uid!,{kind:'at',at})} onClose={()=>setEditing(null)} onPending={onPending}/>:null}
      </li>;
    })}</ul>
    <details className="ct-calendar-import-notes"><summary>导入与改期注意事项</summary>
    <p className="ct-step-meta">已导入的日程不会自动更新；重复导入可能新增日程。改期后可在“查看已保存的日历副本”复制原名称，找到已有日程再修改。</p>
    <p className="ct-step-meta">导入后找不到日程时，请把接收日历的日期范围切到对应截止日，或扩大列表的显示范围。</p>
    <p className="ct-step-meta">接收日历首次使用时，可能需要先关闭欢迎页、启用本地日历或完成导入向导。保存文件后，请在接收日历逐项核对名称、日期和提醒。</p></details>
  </section>;
}
