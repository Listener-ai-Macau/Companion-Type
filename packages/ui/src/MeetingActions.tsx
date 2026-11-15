import {useMemo} from 'react';
import {ArrowUpRight,CheckCheck,ListTodo,MessageCircleQuestion} from 'lucide-react';
import {meetingReaderModel} from './meetingReaderModel';

/** The saved decisions and arrangements, with their original qualifications. */
export function MeetingActions({markdown,onLocate}:{markdown:string;onLocate:(section:string,text?:string)=>void}){
 const groups=useMemo(()=>meetingReaderModel(markdown).groups.filter(group=>group.id!=='discussionQuestions'),[markdown]);
 const icons={decisions:CheckCheck,actions:ListTodo,questions:MessageCircleQuestion,discussionQuestions:MessageCircleQuestion};
 return <section className="meeting-actions" aria-label="决策与待办">
  {!groups.some(group=>group.id==='actions')&&<p className="meeting-actions-empty"><ListTodo size={17} aria-hidden="true"/>这份纪要没有记录明确待办</p>}
  {groups.map(group=>{const Icon=icons[group.id];return <section className="meeting-action-group" key={group.id} aria-label={group.label}>
   <h3><Icon size={16} aria-hidden="true"/>{group.label}<span>{group.items.length}</span></h3>
   <ul>{group.items.map((item,index)=><li key={index}>
    <div>{item.qualifier&&<span className="meeting-action-qualifier">{item.qualifier}</span>}<p>{item.body}</p></div>
    <button type="button" className="meeting-action-source" onClick={()=>onLocate(item.section,item.text)}>原文<ArrowUpRight size={13} aria-hidden="true"/></button>
   </li>)}</ul>
  </section>;})}
 </section>;
}
