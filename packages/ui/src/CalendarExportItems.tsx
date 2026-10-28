import {readableCalendarTime} from './calendarTime';

/** These rows come from the same native preparation as the reviewed file hash. */
export type CalendarExportItem={text:string;title:string;deadline:string|null;status:'timed'|'allDay'|'unconfirmed'|'completed'};
export type CalendarReminderChoice={remindAtTime?:boolean;reminderFormat?:'calendarreminder'|'calendarreminder30'|'calendarreminder60'};
export function CalendarExportItems({items,choice,disabled,onEdit}:{
  items:CalendarExportItem[];choice:CalendarReminderChoice;disabled:boolean;onEdit?:(index:number)=>void;
}){
  const included=items.filter(item=>item.status==='timed'||item.status==='allDay');
  const alarms=choice.remindAtTime?included.filter(item=>item.status==='timed').length:0;
  const reminder=choice.reminderFormat==='calendarreminder'?'在已确认的时刻':choice.reminderFormat==='calendarreminder60'?'提前1小时':'提前30分钟';
  return <section aria-label="逐项日历预览">
    <p><strong>将导出{included.length}项日程：{alarms}项附提醒，{included.length-alarms}项不提醒。</strong></p>
    <ul>{items.map((item,index)=><li key={index} style={{marginBottom:12,overflowWrap:'anywhere'}}>
      <strong>{item.title}</strong><br/>
      {item.status==='completed'?'已完成，本次不导出':item.status==='unconfirmed'?`时间尚未确认，本次不导出${item.deadline?`：${item.deadline}`:''}`:
        `${readableCalendarTime(item.deadline??'')} · ${item.status==='allDay'?'全天日程，不提醒':choice.remindAtTime?`提醒：${reminder}`:'不提醒'}`}
      {onEdit&&item.status!=='completed'?<><br/><button type="button" className="ct-text-button" disabled={disabled}
        aria-label={`日历事项 ${index+1} ${item.status==='allDay'?'补充具体时刻':'修改日历时间'}`}
        onClick={()=>onEdit(index)}>{item.status==='allDay'?'补充具体时刻':item.status==='unconfirmed'?'确认日期和时刻':'修改日历时间'}</button></>:null}
    </li>)}</ul>
    <p className="ct-step-meta">已导入的日程不会自动更新；重复导入可能新增日程。改期后可在“查看已保存的日历副本”复制原名称，找到已有日程再修改。</p>
  </section>;
}
