import {useId,useMemo,useState,type ReactNode} from 'react';
import {ArrowUpRight,BookOpen,CheckCheck,ChevronDown,GitBranch,ListTodo,MessageCircleQuestion} from 'lucide-react';
import {meetingMapModel,type MeetingMapSection} from './meetingMap';
import './meetingOverview.css';

function Outcome({label,section,icon,onLocate}:{label:string;section?:MeetingMapSection;icon:ReactNode;onLocate:(section:string)=>void}){
 return <details className="meeting-overview-outcome">
  <summary>{icon}<span>{label}<small>{section?.items.length?`${section.items.length} 条`:'未列出'}</small></span><ChevronDown size={14} aria-hidden="true"/></summary>
  <div>{section?.items.length?<><ul>{section.items.map((text,index)=><li key={index}>{text}</li>)}</ul><button type="button" onClick={()=>onLocate(section.title)}>在完整纪要中查看<ArrowUpRight size={13} aria-hidden="true"/></button></>:<p>这份纪要未列出{label}。</p>}</div>
 </details>;
}

/** A navigation view of saved content. Selection never changes the note or generates facts. */
export function MeetingOverview({markdown,onLocate,onRead}:{markdown:string;onLocate:(section:string,text?:string)=>void;onRead:()=>void}){
 const model=useMemo(()=>meetingMapModel(markdown),[markdown]);
 const [selection,setSelection]=useState({source:markdown,id:model.topics[0]?.id});
 const current=model.topics.find(topic=>topic.id===(selection.source===markdown?selection.id:undefined))??model.topics[0];
 const id=useId(),index=current?model.topics.indexOf(current):0;
 return <section className="meeting-overview" aria-label="会议一览">
  <div className="meeting-overview-outcomes" aria-label="结论与后续安排">
   <Outcome label="讨论结论" section={model.decisions} icon={<CheckCheck size={18} aria-hidden="true"/>} onLocate={onLocate}/>
   <Outcome label="行动事项" section={model.actions} icon={<ListTodo size={18} aria-hidden="true"/>} onLocate={onLocate}/>
   <Outcome label="待确认" section={model.questions} icon={<MessageCircleQuestion size={18} aria-hidden="true"/>} onLocate={onLocate}/>
  </div>
  <div className="meeting-overview-heading"><h3><GitBranch size={17} aria-hidden="true"/>讨论脉络</h3><span>{model.topics.length?`${model.topics.length} 个${model.topicLabel}`:'暂无主题分组'}</span></div>
  {model.topics.length?<>
   <ol className="meeting-overview-topics" aria-label="选择讨论主题">{model.topics.map((topic,i)=><li key={topic.id}>
    <button type="button" aria-pressed={current?.id===topic.id} aria-controls={id} title={topic.label} onClick={()=>setSelection({source:markdown,id:topic.id})}>
     <span className="meeting-overview-number" aria-hidden="true">{String(i+1).padStart(2,'0')}</span><span className="meeting-overview-topic-label">{topic.label}</span><ChevronDown size={14} aria-hidden="true"/>
    </button>
   </li>)}</ol>
   <div className="meeting-overview-detail" id={id} role="region" aria-label="所选主题的纪要原文" aria-live="polite">
    <div><span>主题 {String(index+1).padStart(2,'0')} · 纪要原文</span><button type="button" onClick={()=>onLocate(current.section,current.text)}>纪要位置<ArrowUpRight size={13} aria-hidden="true"/></button></div>
    <p>{current.text}</p>
   </div>
  </>:<div className="meeting-overview-empty"><BookOpen size={24} aria-hidden="true"/><p>这份纪要还没有主题分组，先看完整内容。</p></div>}
  <button type="button" className="meeting-overview-read" onClick={onRead}><BookOpen size={16} aria-hidden="true"/><span>阅读完整纪要</span><ArrowUpRight size={15} aria-hidden="true"/></button>
 </section>;
}
