import {useMemo} from 'react';
import {ArrowUpRight,BookOpen,ChevronDown} from 'lucide-react';
import {meetingGlanceExcerpt} from './meetingGlance';
import {topicReadingParts} from './MeetingTopic';
import {meetingReaderModel,type MeetingReaderGroup,type MeetingReaderItem} from './meetingReaderModel';
import './meetingOverview.css';

type Locate=(section:string,text?:string)=>void;
/** Emphasize an exact source prefix; this does not produce a new heading or fact. */
function SourceText({text}:{text:string}){
 const prefix=topicReadingParts(text).title;
 return <>{prefix?<><strong>{prefix}</strong>{text.slice(prefix.length)}</>:text}</>;
}
function OutcomeItem({item,onLocate}:{item:MeetingReaderItem;onLocate:Locate}){
 const preview=meetingGlanceExcerpt(item.body,78);
 return <details className="meeting-reader-item" data-source-text={item.text}>
  <summary><span className="meeting-reader-item-body">{item.qualifier&&<small className="meeting-glance-qualifier">{item.qualifier}</small>}<span className="meeting-reader-preview">{preview.text}{preview.clipped?'…':''}</span><span className="meeting-reader-full">{item.body}</span></span><ChevronDown size={13} aria-hidden="true"/></summary>
  <button type="button" className="meeting-reader-source" onClick={()=>onLocate(item.section,item.text)}>查看上下文<ArrowUpRight size={13} aria-hidden="true"/></button>
 </details>;
}
function Outcome({group,onLocate}:{group:MeetingReaderGroup;onLocate:Locate}){
 const visible=2;
 const render=(item:MeetingReaderItem,index:number)=><OutcomeItem key={item.section+'\n'+index} item={item} onLocate={onLocate}/>;
 return <section className={'meeting-overview-outcome meeting-reader-'+group.id} aria-label={group.label}>
  <h3><span className="meeting-reader-outcome-mark" aria-hidden="true"/>{group.label}</h3>
  <div>{group.items.slice(0,visible).map(render)}</div>
  {group.items.length>visible&&<details className="meeting-reader-more"><summary>其他 {group.items.length-visible} 项<ChevronDown size={12} aria-hidden="true"/></summary><div>{group.items.slice(visible).map(render)}</div></details>}
 </section>;
}

/** Readable saved notes first, with outcomes alongside. No service call or content rewrite. */
export function MeetingOverview({markdown,onLocate,onRead}:{markdown:string;onLocate:Locate;onRead:()=>void}){
 const model=useMemo(()=>meetingReaderModel(markdown),[markdown]);
 const topics=(offset:number,count?:number)=>model.topics.slice(offset,count===undefined?undefined:offset+count).map((topic,index)=>{
  const excerpt=meetingGlanceExcerpt(topic.text,180);
  return <li key={topic.id} data-source-text={topic.text}>
   <span className="meeting-overview-number" aria-hidden="true">{String(offset+index+1).padStart(2,'0')}</span>
   <div className="meeting-reader-topic-content">
    {excerpt.clipped?<details className="meeting-reader-long-topic"><summary><span className="meeting-reader-long-preview"><SourceText text={excerpt.text}/>…</span><span className="meeting-reader-long-close">收起内容</span><ChevronDown size={13} aria-hidden="true"/></summary><p>{topic.text}</p></details>:<p className="meeting-reader-topic-text"><SourceText text={topic.text}/></p>}
    <button type="button" className="meeting-reader-context" aria-label={'查看议题 '+(offset+index+1)+' 上下文'} onClick={()=>onLocate(topic.section,topic.text)}>原文<ArrowUpRight size={12} aria-hidden="true"/></button>
   </div>
  </li>;
 });
 return <section className={'meeting-overview meeting-reader'+(model.groups.length?' meeting-reader-has-outcomes':'')} aria-label="会议一览">
  <div className="meeting-reader-discussion">
   {model.topics.length>0&&<>
    <ol className="meeting-overview-topics" aria-label="会议重点">{topics(0,6)}</ol>
    {model.topics.length>6&&<details className="meeting-glance-more"><summary>其他 {model.topics.length-6} 个议题<ChevronDown size={13} aria-hidden="true"/></summary><ol className="meeting-overview-topics" start={7}>{topics(6)}</ol></details>}
   </>}
   <button type="button" className="meeting-overview-read" onClick={onRead}><BookOpen size={15} aria-hidden="true"/><span>完整纪要</span><ArrowUpRight size={14} aria-hidden="true"/></button>
  </div>
  {model.groups.length>0&&<aside className="meeting-reader-groups" aria-label="会议结果">{[...model.groups].sort((a,b)=>['decisions','actions','questions'].indexOf(a.id)-['decisions','actions','questions'].indexOf(b.id)).map(group=><Outcome key={group.id} group={group} onLocate={onLocate}/>)}</aside>}
 </section>;
}
