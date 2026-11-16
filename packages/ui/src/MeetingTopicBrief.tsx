import {useId,useState} from 'react';
import {ArrowUpRight,ChevronDown,MessageSquare} from 'lucide-react';
import type {MeetingMapTopic} from './meetingMap';
import {meetingJudgmentFragments} from './meetingDiagram';

/** Renders saved generation and program-bound source excerpts; presence of a source is not a semantic accuracy certificate. */
export function MeetingTopicBrief({topic,onLocate,graphic=false}:{topic:MeetingMapTopic;onLocate?:(section:string,text?:string)=>void;graphic?:boolean}){
 const id=useId(),identity=topic.id+'\n'+topic.text,[expandedFor,setExpandedFor]=useState<string|null>(null),expanded=expandedFor===identity;
 const hasSource=!!(onLocate&&topic.sourceSection&&topic.sourceText),hasDetails=!!topic.details?.length;
 const judgments=graphic?(topic.points?.map(p=>p.text)??meetingJudgmentFragments(topic.takeaway??'')):[];
 return <article className={'meeting-topic-brief'+(graphic?' meeting-topic-tree':'')+(judgments.length>1?' meeting-topic-peers':'')} data-source-text={topic.text}>
  <header className="meeting-topic-title-node"><h3>{graphic&&<span className="meeting-topic-symbol" aria-hidden="true"><MessageSquare size={14}/></span>}<span className="meeting-topic-label">{topic.label}</span></h3><div className="meeting-topic-controls">
   {hasSource&&<button type="button" className="meeting-topic-source" aria-label={'查看'+topic.label+'原文'} onClick={()=>onLocate!(topic.sourceSection!,topic.sourceText)}>原文<ArrowUpRight size={12} aria-hidden="true"/></button>}
   {hasDetails&&<button type="button" className="meeting-topic-toggle" aria-label={(expanded?'收起':'展开')+topic.label+'详情'} aria-expanded={expanded} aria-controls={id} onClick={()=>setExpandedFor(expanded?null:identity)}><span>{expanded?'收起':'补充'}</span><ChevronDown size={12} aria-hidden="true"/></button>}</div>
  </header>
  <div className="meeting-topic-branch-body">
  {graphic?<ul className="meeting-topic-judgments meeting-topic-takeaway" aria-label="主要判断" data-fragments={judgments.length}>{judgments.map((text,index)=><li className={topic.points?.[index]?'meeting-point-typed':undefined} key={index}>{topic.points?.[index]&&<small className={'meeting-point-kind'+(topic.points[index].kind==='观点'?' meeting-point-kind-general':'')}>{topic.points[index].kind}</small>}<span>{text}</span></li>)}</ul>:<p className="meeting-topic-takeaway">{topic.takeaway}</p>}
  {hasDetails&&<div id={id} className="meeting-topic-support" hidden={!expanded}>
   {!!topic.details?.length&&<ul>{topic.details.map((text,index)=><li key={index}>{text}</li>)}</ul>}
  </div>}
  </div>
 </article>;
}
