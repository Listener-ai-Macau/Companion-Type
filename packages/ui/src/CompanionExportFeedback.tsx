import { useEffect, useRef, useState } from 'react';
import { CompanionChecklistHandoff } from './CompanionChecklistHandoff';

export interface CompanionExportFeedbackValue {
  message: string;
  format?: string;
  hasWarning?: boolean;
  kind?: 'saved' | 'cancelled' | 'pending' | 'error';
  path?: string;
  calendarOpenToken?: string;
}

export function exportFileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

function CalendarOpen({token,open}:{token:string;open:(token:string)=>Promise<void>}) {
  const [state,setState]=useState<'ready'|'opening'|'requested'|'error'>('ready');
  const [error,setError]=useState('');const pending=useRef(false),alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const start=async()=>{
    if(pending.current)return;pending.current=true;setState('opening');setError('');
    try {await open(token);if(alive.current)setState('requested');}
    catch(reason){if(alive.current){setError(reason instanceof Error?reason.message:String(reason));setState('error');}}
    finally{pending.current=false;}
  };
  return <div>
    <button type="button" className="ct-action" disabled={state==='opening'} onClick={()=>void start()}>
      {state==='opening'?'正在打开日历文件…':state==='requested'?'再次打开日历文件':'打开日历文件'}
    </button>
    {state==='requested'?<p className="ct-step-meta">已请求默认应用打开这份文件。请在接收应用中确认导入，并核对日期和提醒；再次导入可能产生重复日程。</p>:null}
    {state==='error'?<p className="ct-step-warn" role="alert">{error}</p>:null}
  </div>;
}

export function CompanionExportFeedback({ feedback, className='ct-export-result',onOpenSavedCalendar }: {
  feedback: CompanionExportFeedbackValue; className?: string;onOpenSavedCalendar?:(token:string)=>Promise<void>;
}) {
  const classes = new Set(className.split(/\s+/).filter(Boolean));
  if (feedback.hasWarning) {
    classes.delete('ct-step-ok');
    classes.add('ct-step-warn');
  }
  return <div className={[...classes].join(' ')} role={feedback.kind === 'error' ? 'alert' : 'status'}>
    <span>{feedback.message}</span>
    {feedback.kind==='saved'&&feedback.calendarOpenToken&&onOpenSavedCalendar
      &&(feedback.format==='calendar'||feedback.format?.startsWith('calendarreminder'))
      ?<CalendarOpen key={feedback.calendarOpenToken} token={feedback.calendarOpenToken} open={onOpenSavedCalendar}/>:null}
    {feedback.kind==='saved'&&feedback.path&&(feedback.format==='calendar'||feedback.format?.startsWith('calendarreminder'))?<p className="ct-step-meta">1. 文件已保存 → 2. 在常用日历中导入该文件 → 3. 打开日程核对日期与提醒。</p>:null}
    {feedback.kind === 'saved' && feedback.path && (feedback.format === 'todo' || feedback.format === 'todotxt' || feedback.format === 'ics' || feedback.format === 'calendar' || feedback.format?.startsWith('calendarreminder'))
      ? <CompanionChecklistHandoff format={feedback.format?.startsWith('calendarreminder')?'calendar':feedback.format as 'todo'|'todotxt'|'ics'|'calendar'}/> : null}
    {feedback.kind === 'saved' && feedback.path ? <details>
      <summary>查看保存位置</summary>
      <p style={{ overflowWrap: 'anywhere' }}>{feedback.path}</p>
    </details> : null}
  </div>;
}
