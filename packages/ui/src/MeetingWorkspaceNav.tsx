import {useRef} from 'react';
import {FileText,Headphones,NotebookPen,Send} from 'lucide-react';
import './meetingWorkspace.css';

export type MeetingPane='result'|'source'|'materials'|'handoff';
export function meetingPaneForTarget(id:string):MeetingPane{
 if(id==='ct-meeting-export'||id==='ct-meeting-other-export')return 'handoff';
 if(['ct-recording-notes','ct-recording-references','ct-document-context','ct-meeting-qa'].includes(id))return 'materials';
 if(['ct-recording-text','ct-recording-text-review','ct-meeting-templates','ct-recording-playback'].includes(id))return 'source';
 return 'result';
}
const panes=[
 {id:'result' as const,label:'纪要',icon:FileText},
 {id:'source' as const,label:'文字',icon:Headphones},
 {id:'materials' as const,label:'补充',icon:NotebookPen},
 {id:'handoff' as const,label:'导出',icon:Send},
];
export function MeetingWorkspaceNav({value,onChange,dirty,notesCount}:{value:MeetingPane;onChange:(pane:MeetingPane)=>void;dirty:Partial<Record<MeetingPane,boolean>>;notesCount:number}){
 const nav=useRef<HTMLElement>(null);
 return <nav className="ct-meeting-navigation" ref={nav} aria-label="会议工作区" onKeyDown={event=>{
  const current=panes.findIndex(p=>p.id===value);let next=current;
  if(event.key==='ArrowRight')next=(current+1)%panes.length;
  else if(event.key==='ArrowLeft')next=(current+panes.length-1)%panes.length;
  else if(event.key==='Home')next=0;else if(event.key==='End')next=panes.length-1;else return;
  event.preventDefault();onChange(panes[next].id);nav.current?.querySelectorAll<HTMLButtonElement>('button')[next]?.focus();
 }}>
  {panes.map(p=><button type="button" key={p.id} className={p.id==='handoff'?'ct-meeting-export-trigger':undefined} aria-current={value===p.id?'page':undefined} onClick={()=>onChange(p.id)}>
   <p.icon size={17} aria-hidden="true"/><span>{p.label}</span>
   {dirty[p.id]?<small className="ct-pane-dirty" aria-label="有未保存的修改">未保存</small>:p.id==='materials'&&notesCount>0?<small className="ct-pane-count">{notesCount}</small>:null}
  </button>)}
 </nav>;
}
