import {useId,useState} from 'react';
import {ArrowUpRight,ChevronDown} from 'lucide-react';
import type {MeetingMapTopic} from './meetingMap';
import {meetingJudgmentFragments} from './meetingDiagram';

/** Keep the exact attribution visible without competing with the statement. */
function JudgmentText({text}:{text:string}){
 const attribution=/^(有嘉宾(?:认为|预计|提醒|提出)|一方企业|另一方企业|一家企业)/.exec(text)?.[0];
 return attribution?<><span className="meeting-topic-attribution">{attribution}</span>{text.slice(attribution.length)}</>:<>{text}</>;
}

/** Content is generated and source-checked by the minutes engine, never here. */
export function MeetingTopicBrief({topic,onLocate,graphic=false}:{topic:MeetingMapTopic;onLocate?:(section:string,text?:string)=>void;graphic?:boolean}){
 const id=useId(),identity=topic.id+'\n'+topic.text,[expandedFor,setExpandedFor]=useState<string|null>(null),expanded=expandedFor===identity;
 const hasSource=!!(onLocate&&topic.sourceSection&&topic.sourceText),hasDetails=!!topic.details?.length||hasSource;
 const judgments=graphic?meetingJudgmentFragments(topic.takeaway??''):[];
 return <article className={'meeting-topic-brief'+(graphic?' meeting-topic-tree':'')} data-source-text={topic.text}>
  <header className="meeting-topic-title-node"><h3>{topic.label}</h3>
   {hasDetails&&<button type="button" className="meeting-topic-toggle" aria-label={(expanded?'收起':'展开')+topic.label+'详情'} aria-expanded={expanded} aria-controls={id} onClick={()=>setExpandedFor(expanded?null:identity)}><span>{expanded?'收起':'详情'}</span><ChevronDown size={12} aria-hidden="true"/></button>}
  </header>
  {graphic?<ul className="meeting-topic-judgments meeting-topic-takeaway" aria-label="主要判断" data-fragments={judgments.length}>{judgments.map((text,index)=><li key={index}><span><JudgmentText text={text}/></span></li>)}</ul>:<p className="meeting-topic-takeaway"><JudgmentText text={topic.takeaway??''}/></p>}
  {hasDetails&&<div id={id} className="meeting-topic-support" hidden={!expanded}>
   {!!topic.details?.length&&<ul>{topic.details.map((text,index)=><li key={index}>{text}</li>)}</ul>}
   {hasSource&&<button type="button" onClick={()=>onLocate!(topic.sourceSection!,topic.sourceText)}>查看原话<ArrowUpRight size={12} aria-hidden="true"/></button>}
  </div>}
 </article>;
}
