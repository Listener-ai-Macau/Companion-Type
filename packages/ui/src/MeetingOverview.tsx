import {useId,useMemo,useRef,useState} from 'react';
import {ArrowUpRight,BookOpen,ChevronDown} from 'lucide-react';
import type {MeetingMapTopic} from './meetingMap';
import {meetingGlanceExcerpt,meetingGlanceLabels} from './meetingGlance';
import {meetingReaderModel,type MeetingReaderGroup,type MeetingReaderItem} from './meetingReaderModel';
import './meetingOverview.css';

function Excerpt({source,limit,preferClause=false}:{source:string;limit:number;preferClause?:boolean}){
 const excerpt=meetingGlanceExcerpt(source,limit,preferClause);
 return <>{excerpt.text}{excerpt.clipped&&<span aria-label="展开查看完整内容">…</span>}</>;
}
type Locate=(section:string,text?:string)=>void;
function OutcomeItem({item,onLocate}:{item:MeetingReaderItem;onLocate:Locate}){
 return <details className="meeting-reader-item" data-source-text={item.text}>
  <summary><span className="meeting-reader-item-body">{item.qualifier&&<small className="meeting-glance-qualifier">{item.qualifier}</small>}<span className="meeting-reader-preview"><Excerpt source={item.body} limit={34} preferClause/></span><span className="meeting-reader-full">{item.body}</span></span><ChevronDown size={14} aria-hidden="true"/></summary>
  <button type="button" className="meeting-reader-source" onClick={()=>onLocate(item.section,item.text)}>查看上下文<ArrowUpRight size={13} aria-hidden="true"/></button>
 </details>;
}
function Outcome({group,onLocate}:{group:MeetingReaderGroup;onLocate:Locate}){
 const render=(item:MeetingReaderItem,index:number)=><OutcomeItem key={item.section+'\n'+item.text+'\n'+index} item={item} onLocate={onLocate}/>;
 const visible=group.id==='questions'?1:2;
 return <section className={'meeting-overview-outcome meeting-reader-'+group.id} aria-label={group.label}>
  <h3>{group.label}</h3>
  <div>{group.items.slice(0,visible).map(render)}</div>
  {group.items.length>visible&&<details className="meeting-reader-more"><summary>其他 {group.items.length-visible} 项<ChevronDown size={12} aria-hidden="true"/></summary><div>{group.items.slice(visible).map(render)}</div></details>}
 </section>;
}

/** A source-driven reading surface. Complete saved content is retained on demand. */
export function MeetingOverview({markdown,onLocate,onRead}:{markdown:string;onLocate:Locate;onRead:()=>void}){
 const model=useMemo(()=>meetingReaderModel(markdown),[markdown]);
 const labels=useMemo(()=>meetingGlanceLabels(markdown,model.topics),[markdown,model]);
 const [selection,setSelection]=useState<{source:string;id:string|null}>({source:markdown,id:null});
 const current=selection.source===markdown?model.topics.find(topic=>topic.id===selection.id):undefined;
 const buttons=useRef(new Map<string,HTMLButtonElement>()),detail=useRef<HTMLDivElement>(null),id=useId();
 const close=()=>{setSelection({source:markdown,id:null});if(current)buttons.current.get(current.id)?.focus();};
 const select=(topic:MeetingMapTopic)=>{const open=current?.id!==topic.id;setSelection({source:markdown,id:open?topic.id:null});if(open)window.requestAnimationFrame(()=>detail.current?.scrollIntoView({block:'nearest',behavior:'auto'}));};
 const topics=(items:MeetingMapTopic[],offset=0)=>items.map((topic,i)=>{
  const open=current?.id===topic.id,label=labels.get(topic.id)??topic.label,region=id+'-'+topic.id;
  return <li key={topic.id}>
   <button type="button" ref={node=>{if(node)buttons.current.set(topic.id,node);else buttons.current.delete(topic.id);}} aria-expanded={open} aria-controls={region} onClick={()=>select(topic)}>
    <span className="meeting-overview-number" aria-hidden="true">{String(i+offset+1).padStart(2,'0')}</span><span className="meeting-overview-topic-label"><span className="meeting-reader-topic-title"><Excerpt source={label} limit={22}/></span>{topic.text.startsWith(label)&&<small className="meeting-reader-topic-preview"><Excerpt source={topic.text.slice(label.length).trim()} limit={32} preferClause/></small>}</span><ChevronDown size={14} aria-hidden="true"/>
   </button>
   {open&&<div className="meeting-overview-detail" ref={detail} id={region} role="region" aria-label={label+'详情'} onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();close();}}}>
    <p>{topic.text}</p><button type="button" onClick={()=>onLocate(topic.section,topic.text)}>查看上下文<ArrowUpRight size={13} aria-hidden="true"/></button>
   </div>}
  </li>;
 });
 return <section className="meeting-overview meeting-reader" aria-label="会议一览">
  {model.groups.length>0&&<div className="meeting-reader-groups">{model.groups.map(group=><Outcome key={group.id} group={group} onLocate={onLocate}/>)}</div>}
  {model.topics.length>0&&<div className="meeting-reader-discussion">
   <div className="meeting-overview-heading"><h3>讨论脉络</h3></div>
   <ol className="meeting-overview-topics" aria-label="讨论议题">{topics(model.topics.slice(0,6))}</ol>
   {model.topics.length>6&&<details className="meeting-glance-more"><summary>其他 {model.topics.length-6} 个议题<ChevronDown size={13} aria-hidden="true"/></summary><ol className="meeting-overview-topics">{topics(model.topics.slice(6),6)}</ol></details>}
  </div>}
  <button type="button" className="meeting-overview-read" onClick={onRead}><BookOpen size={15} aria-hidden="true"/><span>完整纪要</span><ArrowUpRight size={14} aria-hidden="true"/></button>
 </section>;
}
