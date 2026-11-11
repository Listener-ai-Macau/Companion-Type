import {useId,useRef,type ReactNode} from 'react';
import {FileText,MessageSquare,NotebookPen} from 'lucide-react';
import './meetingReferenceWorkspace.css';

export type ReferenceView='notes'|'documents'|'assistant';
type Props={id?:string;view:ReferenceView;onViewChange:(view:ReferenceView)=>void;notes:ReactNode;documents?:ReactNode;assistant?:ReactNode};

/** Presentation only: changing the reading pane never discards a mounted draft. */
export function MeetingReferenceWorkspace({id,view,onViewChange,notes,documents,assistant}:Props){
 const uid=useId(),tabs=useRef<HTMLDivElement>(null);
 const panes=[{key:'notes' as const,label:'便签与图片',icon:NotebookPen,body:notes},{key:'documents' as const,label:'补充文档',icon:FileText,body:documents},{key:'assistant' as const,label:'AI 助手',icon:MessageSquare,body:assistant}].filter(p=>p.body!==null&&p.body!==undefined&&p.body!==false);
 if(!panes.length)return null;
 const active=panes.some(p=>p.key===view)?view:panes[0]?.key;
 return <section id={id} className="meeting-reference-workspace" aria-label="会议补充资料">
  <div className="reference-workspace-heading"><h3>会议资料</h3><p>添加补充、查阅来源，或继续提问。</p></div>
  <div className="reference-workspace-tabs" ref={tabs} role="tablist" aria-label="补充资料查看方式" onKeyDown={event=>{
   const index=panes.findIndex(p=>p.key===active);let next=index;
   if(event.key==='ArrowRight')next=(index+1)%panes.length;else if(event.key==='ArrowLeft')next=(index+panes.length-1)%panes.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=panes.length-1;else return;
   event.preventDefault();onViewChange(panes[next].key);tabs.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  }}>{panes.map(p=><button type="button" role="tab" key={p.key} id={uid+'-tab-'+p.key} aria-controls={uid+'-panel-'+p.key} aria-selected={active===p.key} tabIndex={active===p.key?0:-1} onClick={()=>onViewChange(p.key)}><p.icon size={16} aria-hidden="true"/><span>{p.label}</span></button>)}</div>
  {panes.map(p=><div key={p.key} id={uid+'-panel-'+p.key} className="reference-workspace-panel" role="tabpanel" aria-labelledby={uid+'-tab-'+p.key} hidden={active!==p.key}>{p.body}</div>)}
 </section>;
}
