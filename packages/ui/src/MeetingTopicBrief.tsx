import {ArrowUpRight,ChevronDown} from 'lucide-react';
import type {MeetingMapTopic} from './meetingMap';

/** Content is generated and source-checked by the minutes engine, never here. */
export function MeetingTopicBrief({topic,onLocate}:{topic:MeetingMapTopic;onLocate?:(section:string,text?:string)=>void}){
 return <article className="meeting-topic-brief" data-source-text={topic.text}>
  <h3>{topic.label}</h3>
  <p className="meeting-topic-takeaway">{topic.takeaway}</p>
  {(!!topic.details?.length||onLocate)&&<details className="meeting-topic-support">
   <summary>依据与补充<ChevronDown size={12} aria-hidden="true"/></summary>
   {!!topic.details?.length&&<ul>{topic.details.map((text,index)=><li key={index}>{text}</li>)}</ul>}
   {onLocate&&topic.sourceSection&&topic.sourceText&&<button type="button" onClick={()=>onLocate(topic.sourceSection!,topic.sourceText)}>查看原话<ArrowUpRight size={12} aria-hidden="true"/></button>}
  </details>}
 </article>;
}
