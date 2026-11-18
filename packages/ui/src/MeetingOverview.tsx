import {useId,useMemo,useRef,useState,type ReactNode} from 'react';
import {ArrowUpRight,BookOpen,CheckCheck,ChevronDown,GitBranch,ListTodo,MessageCircleQuestion,X} from 'lucide-react';
import {meetingMapModel,type MeetingMapSection,type MeetingMapTopic} from './meetingMap';
import {meetingGlanceExcerpt,meetingGlanceQualifier,meetingGlanceLabels} from './meetingGlance';
import './meetingOverview.css';

function Excerpt({source,limit,preferClause=false}:{source:string;limit:number;preferClause?:boolean}){
 const excerpt=meetingGlanceExcerpt(source,limit,preferClause);
 return <>{excerpt.text}{excerpt.clipped&&<span aria-label="摘录，展开查看完整内容">…</span>}</>;
}
function Outcome({label,section,icon,onLocate,previewCount=1}:{label:string;section?:MeetingMapSection;icon:ReactNode;onLocate:(section:string)=>void;previewCount?:number}){
 const items=section?.items??[];
 if(!items.length)return <div className="meeting-glance-empty-result">{icon}<span>{label}</span><small>纪要未列出{label==='行动事项'?'事项':label==='讨论结论'?'结论':'问题'}</small></div>;
 return <details className="meeting-overview-outcome">
  <summary><span className="meeting-glance-label">{icon}{label}<span>摘录</span><ChevronDown size={13} aria-hidden="true"/></span>
   <span className="meeting-glance-previews">{items.slice(0,previewCount).map((item,index)=>{const source=meetingGlanceQualifier(item);return <span key={index}>{source.qualifier&&<small className="meeting-glance-qualifier">{source.qualifier}</small>}<Excerpt source={source.body} limit={label==='待确认'?22:30} preferClause/></span>;})}</span>
   {items.length>previewCount&&<small>另有 {items.length-previewCount} 条</small>}
  </summary>
  <div className="meeting-glance-full"><ul>{items.map((text,index)=><li key={index}>{text}</li>)}</ul><button type="button" onClick={()=>onLocate(section!.title)}>在完整纪要中查看<ArrowUpRight size={13} aria-hidden="true"/></button></div>
 </details>;
}

/** The first layer is a brief index; complete source appears only on request. */
export function MeetingOverview({markdown,onLocate,onRead}:{markdown:string;onLocate:(section:string,text?:string)=>void;onRead:()=>void}){
 const model=useMemo(()=>meetingMapModel(markdown),[markdown]);
 const labels=useMemo(()=>meetingGlanceLabels(markdown,model.topics),[markdown,model]);
 const [selection,setSelection]=useState<{source:string;id:string|null}>({source:markdown,id:null});
 const current=selection.source===markdown?model.topics.find(topic=>topic.id===selection.id):undefined;
 const buttons=useRef(new Map<string,HTMLButtonElement>()),detail=useRef<HTMLDivElement>(null),id=useId();
 const close=()=>{setSelection({source:markdown,id:null});if(current)buttons.current.get(current.id)?.focus();};
 const select=(topic:MeetingMapTopic)=>{const open=current?.id!==topic.id;setSelection({source:markdown,id:open?topic.id:null});if(open)window.requestAnimationFrame(()=>detail.current?.scrollIntoView({block:'nearest',behavior:'auto'}));};
 const topics=(items:MeetingMapTopic[],offset=0)=>items.map((topic,i)=><li key={topic.id}>
  <button type="button" ref={node=>{if(node)buttons.current.set(topic.id,node);else buttons.current.delete(topic.id);}} aria-expanded={current?.id===topic.id} aria-controls={id} aria-label={topic.label} title={topic.label} onClick={()=>select(topic)}>
   <span className="meeting-overview-number" aria-hidden="true">{String(i+offset+1).padStart(2,'0')}</span><span className="meeting-overview-topic-label"><Excerpt source={labels.get(topic.id)??topic.label} limit={16}/></span><ChevronDown size={13} aria-hidden="true"/>
  </button>
 </li>);
 return <section className="meeting-overview" aria-label="会议一览">
  {model.purpose&&<p className="meeting-overview-purpose">{model.purpose}</p>}
  <div className="meeting-overview-outcomes" aria-label="结论与后续安排">
   <Outcome label="讨论结论" section={model.decisions} icon={<CheckCheck size={16} aria-hidden="true"/>} onLocate={onLocate}/>
   <Outcome label="待确认" section={model.questions} icon={<MessageCircleQuestion size={16} aria-hidden="true"/>} onLocate={onLocate} previewCount={2}/>
  </div>
  <div className="meeting-glance-actions"><Outcome label="行动事项" section={model.actions} icon={<ListTodo size={16} aria-hidden="true"/>} onLocate={onLocate}/></div>
  <div className="meeting-overview-heading"><h3><GitBranch size={15} aria-hidden="true"/>主题索引</h3><span>{model.topics.length?`${model.topics.length} 个${model.topicLabel}`:'暂无主题分组'}</span></div>
  {model.topics.length?<>
   <ol className="meeting-overview-topics" aria-label="选择讨论主题">{topics(model.topics.slice(0,6))}</ol>
   {model.topics.length>6&&<details className="meeting-glance-more"><summary>其余 {model.topics.length-6} 个{model.topicLabel}<ChevronDown size={13} aria-hidden="true"/></summary><ol className="meeting-overview-topics">{topics(model.topics.slice(6),6)}</ol></details>}
   <div className="meeting-overview-detail" ref={detail} id={id} hidden={!current} role="region" aria-label="所选主题的纪要原文" onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();close();}}}>
    {current&&<><div><span>主题 {String(model.topics.indexOf(current)+1).padStart(2,'0')} · 纪要原文</span><button type="button" aria-label="关闭主题原文" onClick={close}><X size={15}/></button></div><p>{current.text}</p><button type="button" onClick={()=>current.sourceSection?onLocate(current.sourceSection):onLocate(current.section,current.text)}>{current.sourceSection?"查看原话":"纪要位置"}<ArrowUpRight size={13} aria-hidden="true"/></button></>}
   </div>
  </>:<div className="meeting-overview-empty"><BookOpen size={20} aria-hidden="true"/><p>这份纪要还没有主题分组，先看完整内容。</p></div>}
  <button type="button" className="meeting-overview-read" onClick={onRead}><BookOpen size={16} aria-hidden="true"/><span>阅读完整纪要</span><ArrowUpRight size={15} aria-hidden="true"/></button>
 </section>;
}
