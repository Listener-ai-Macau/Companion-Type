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

export type CalendarOpenResult = {status:'requested'} | {status:'choose_application';applications:{id:string;label:string}[]};
export type OpenSavedCalendar = (token:string,choiceId?:string,chooseApplication?:boolean)=>Promise<CalendarOpenResult>;

function CalendarOpen({token,open}:{token:string;open:OpenSavedCalendar}) {
  const [state,setState]=useState<'ready'|'opening'|'choosing'|'requested'|'cancelled'|'error'>('ready');
  const [applications,setApplications]=useState<{id:string;label:string}[]>([]);
  const [error,setError]=useState('');const pending=useRef(false),alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const start=async(choiceId?:string,chooseApplication=false)=>{
    if(pending.current)return;pending.current=true;setState('opening');setError('');
    try {
      const result=await open(token,choiceId,chooseApplication);
      if(alive.current){
        if(result.status==='choose_application'){setApplications(result.applications);setState('choosing');}
        else{setApplications([]);setState('requested');}
      }
    }catch(reason){if(alive.current){setError(reason instanceof Error?reason.message:String(reason));setState('error');}}
    finally{pending.current=false;}
  };
  return <div>
    <p><strong>{state==='requested'?'已请求打开文件 → 下一步：在日历中确认导入':'下一步：打开文件 → 在日历中确认导入'}</strong></p>
    <button type="button" className="ct-action" disabled={state==='opening'} onClick={()=>void start(undefined,applications.length>0)}>
      {state==='opening'?'正在打开日历文件…':state==='requested'?'再次打开日历文件':applications.length?'重新读取应用列表':'打开日历文件'}
    </button>
    {!applications.length?<button type="button" className="ct-link" disabled={state==='opening'} onClick={()=>void start(undefined,true)}>选择应用打开</button>:null}
    {applications.length?<div role="group" aria-label="选择接收日历文件的应用">
      <p className="ct-step-meta">选择接收这份文件的日历应用。本次选择不会更改 Windows 默认应用。</p>
      <div className="ct-action-row">{applications.map(app=><button key={app.id} type="button" className="ct-action" disabled={state==='opening'} onClick={()=>void start(app.id)}>{app.label}</button>)}
        <button type="button" className="ct-link" disabled={state==='opening'} onClick={()=>{setApplications([]);setError('');setState('cancelled');}}>暂不打开</button>
      </div>
    </div>:null}
    {state==='requested'?<p className="ct-step-meta">已请求应用打开这份文件。请在接收应用中确认导入，并核对日期和提醒；再次导入可能产生重复日程。</p>:null}
    {state==='cancelled'?<p className="ct-step-meta">已取消选择应用。文件仍已保存，可再次打开或在常用日历中导入。</p>:null}
    {state==='error'?<p className="ct-step-warn" role="alert">{error}</p>:null}
  </div>;
}

export function CompanionExportFeedback({ feedback, className='ct-export-result',onOpenSavedCalendar }: {
  feedback: CompanionExportFeedbackValue; className?: string;onOpenSavedCalendar?:OpenSavedCalendar;
}) {
  const classes = new Set(className.split(/\s+/).filter(Boolean));
  if (feedback.hasWarning) {
    classes.delete('ct-step-ok');
    classes.add('ct-step-warn');
  }
  return <div className={[...classes].join(' ')} role={feedback.kind === 'error' ? 'alert' : 'status'}>
    <span>{feedback.kind==='saved'&&feedback.path&&(feedback.format==='calendar'||feedback.format?.startsWith('calendarreminder'))?<strong>{feedback.message}</strong>:feedback.message}</span>
    {feedback.kind==='saved'&&feedback.calendarOpenToken&&onOpenSavedCalendar
      &&(feedback.format==='calendar'||feedback.format?.startsWith('calendarreminder'))
      ?<CalendarOpen key={feedback.calendarOpenToken} token={feedback.calendarOpenToken} open={onOpenSavedCalendar}/>:null}
    {feedback.kind==='saved'&&feedback.path&&(feedback.format==='calendar'||feedback.format?.startsWith('calendarreminder'))?<p className="ct-step-meta">{feedback.calendarOpenToken&&onOpenSavedCalendar?'导入后，请打开日程核对日期与提醒。':'下一步：在常用日历中导入该文件，再打开日程核对日期与提醒。'}可展开已保存的日历副本，对照每项设置。</p>:null}
    {feedback.kind === 'saved' && feedback.path && (feedback.format === 'todo' || feedback.format === 'todotxt' || feedback.format === 'ics' || feedback.format === 'calendar' || feedback.format?.startsWith('calendarreminder'))
      ? <CompanionChecklistHandoff format={feedback.format?.startsWith('calendarreminder')?'calendar':feedback.format as 'todo'|'todotxt'|'ics'|'calendar'}/> : null}
    {feedback.kind === 'saved' && feedback.path ? <details>
      <summary>查看保存位置</summary>
      <p style={{ overflowWrap: 'anywhere' }}>{feedback.path}</p>
    </details> : null}
  </div>;
}
