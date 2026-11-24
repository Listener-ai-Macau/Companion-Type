import {useMemo} from 'react';
import {ArrowUpRight,CheckCheck,ListTodo,MessageCircleQuestion} from 'lucide-react';
import {meetingReaderModel} from './meetingReaderModel';

/** The saved decisions and arrangements, with their original qualifications. */
export function MeetingActions({markdown,onLocate,onLocateTranscript,reviewPending=false}:{markdown:string;onLocate:(section:string,text?:string)=>void;onLocateTranscript?:(text:string)=>void;reviewPending?:boolean}){
 const model=useMemo(()=>meetingReaderModel(markdown),[markdown]);
 const groups=model.groups.filter(group=>group.id!=='discussionQuestions');
 const requirements=reviewPending?model.sections.find(section=>section.title==='执行要求（待复核）'):undefined;
 const icons={decisions:CheckCheck,actions:ListTodo,questions:MessageCircleQuestion,discussionQuestions:MessageCircleQuestion};
 return <section className="meeting-actions" aria-label="决策与待办">
  {reviewPending?<p className="meeting-actions-empty"><ListTodo size={17} aria-hidden="true"/>待办复核未完成。完整纪要中的补充仍保留在正文。</p>
   :!groups.some(group=>group.id==='actions')&&<p className="meeting-actions-empty"><ListTodo size={17} aria-hidden="true"/>这份纪要没有记录明确待办</p>}
  {requirements?.items.length?<section className="meeting-action-group" aria-label={requirements.title}>
   <h3><MessageCircleQuestion size={16} aria-hidden="true"/>{requirements.title}</h3>
   <ul>{requirements.items.map((line,index)=><li key={index}>
    <div><p>{line}</p></div>
    <button type="button" className="meeting-action-source" onClick={()=>onLocateTranscript?onLocateTranscript(line):onLocate(requirements.title,line)}>{onLocateTranscript?'查看转写上下文':'查看片段'}<ArrowUpRight size={13} aria-hidden="true"/></button>
   </li>)}</ul>
  </section>:null}
  {groups.map(group=>{const Icon=icons[group.id];return <section className="meeting-action-group" key={group.id} aria-label={group.label}>
   <h3><Icon size={16} aria-hidden="true"/>{group.label}<span>{group.items.length}</span></h3>
   <ul>{group.items.map((item,index)=><li key={index}>
    <div>{item.qualifier&&<span className="meeting-action-qualifier">{item.qualifier}</span>}<p>{item.body}</p></div>
    <button type="button" className="meeting-action-source" onClick={()=>onLocate(item.section,item.text)}>原文<ArrowUpRight size={13} aria-hidden="true"/></button>
   </li>)}</ul>
  </section>;})}
 </section>;
}
