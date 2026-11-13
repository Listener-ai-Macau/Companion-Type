import {useId,type ReactNode} from 'react';
import './meetingReferenceWorkspace.css';

export type ReferenceView='notes'|'documents'|'assistant';
type Props={id?:string;view:ReferenceView;onViewChange:(view:ReferenceView)=>void;notes:ReactNode;documents?:ReactNode;assistant?:ReactNode};

/** Presentation only: changing the reading pane never discards a mounted draft. */
export function MeetingReferenceWorkspace({id,view,onViewChange,notes,documents,assistant}:Props){
 const uid=useId();
 const panes=[{key:'notes' as const,label:'笔记',body:notes},{key:'documents' as const,label:'文档',body:documents},{key:'assistant' as const,label:'提问',body:assistant}].filter(p=>p.body!==null&&p.body!==undefined&&p.body!==false);
 if(!panes.length)return null;
 const active=panes.some(p=>p.key===view)?view:panes[0]?.key;
 return <section id={id} className="meeting-reference-workspace" aria-label="会议补充资料">
  <nav className="reference-workspace-tools" aria-label="笔记工具">
   {active!=='notes'&&<button type="button" onClick={()=>onViewChange('notes')}>← 返回笔记</button>}
   {panes.filter(p=>p.key!=='notes'&&p.key!==active).map(p=><button type="button" key={p.key} aria-controls={uid+'-panel-'+p.key} onClick={()=>onViewChange(p.key)}>{p.label==='文档'?'添加或查看文档':'问这条录音'}</button>)}
  </nav>
  {panes.map(p=><div key={p.key} id={uid+'-panel-'+p.key} className="reference-workspace-panel" role="region" aria-label={p.label} hidden={active!==p.key}>{p.body}</div>)}
 </section>;
}
