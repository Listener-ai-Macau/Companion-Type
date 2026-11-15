import {useId,useMemo,useState} from 'react';
import {ArrowUpRight,BookOpen,CheckCheck,ChevronDown,GitBranch,ListTodo,MessageCircleQuestion} from 'lucide-react';
import {meetingReaderModel,type MeetingReaderGroup} from './meetingReaderModel';
import {meetingDiagramParts} from './meetingDiagram';
import {meetingGlanceExcerpt,meetingGlanceLabels} from './meetingGlance';
import {MeetingTopicBrief} from './MeetingTopicBrief';
import './meetingMap.css';

function ResultBranch({group,onLocate}:{group:MeetingReaderGroup;onLocate?:(section:string,text?:string)=>void}){
 const Icon={decisions:CheckCheck,actions:ListTodo,questions:MessageCircleQuestion,discussionQuestions:MessageCircleQuestion}[group.id];
 return <section className={'meeting-map-result meeting-map-result-'+group.id} aria-label={group.label}>
  <h4><Icon size={15} aria-hidden="true"/>{group.label}</h4>
  <ul>{group.items.map((item,i)=>{const preview=meetingGlanceExcerpt(item.body,90);return <li key={i}><details>
   <summary>{item.qualifier&&<small className="meeting-map-qualifier">{item.qualifier}</small>}<span>{preview.text}{preview.clipped?'…':''}</span><ChevronDown size={13} aria-hidden="true"/></summary>
   <p>{item.body}</p>{onLocate&&<button type="button" onClick={()=>onLocate(item.section,item.text)}>原文<ArrowUpRight size={12} aria-hidden="true"/></button>}
  </details></li>;})}</ul>
 </section>;
}

/** The same saved meeting, rendered as a top-to-bottom hierarchy. */
export function MeetingMapView({markdown,title='会议纪要',onLocate,onRead,composition='diagram'}:{markdown:string;title?:string;onLocate?:(section:string,text?:string)=>void;onRead?:()=>void;composition?:'diagram'|'overview'}){
 const model=useMemo(()=>meetingReaderModel(markdown),[markdown]);
 const labels=useMemo(()=>meetingGlanceLabels(markdown,model.topics),[markdown,model]);
 const nodes=useMemo(()=>model.topics.map(topic=>({...topic,...meetingDiagramParts(topic.text,labels.get(topic.id))})),[model,labels]);
 const hasResults=model.groups.some(g=>g.id!=='discussionQuestions');
 const questionBased=model.structured&&model.topics.every(topic=>/[?？]$/.test(topic.label.trim()));
 const unitLabel=model.topicLabel==='分组'?'分组':'要点';
 const initiallyOpen=()=>new Set(nodes.slice(0,6).map(node=>node.id));
 const [selection,setSelection]=useState<{source:string;ids:ReadonlySet<string>}>(()=>({source:markdown,ids:initiallyOpen()})),id=useId();
 const expanded=selection.source===markdown?selection.ids:initiallyOpen();
 function toggle(key:string,open:boolean){setSelection(previous=>{const ids=new Set(previous.source===markdown?previous.ids:initiallyOpen());if(ids.has(key)===open)return previous;if(open)ids.add(key);else ids.delete(key);return {source:markdown,ids};});}
 if(model.outlineUnavailable)return <section className="meeting-map" aria-label="会议图解"><p className="meeting-topic-unavailable">主题整理尚未完成</p>{onRead&&<button type="button" className="meeting-map-read" onClick={onRead}><BookOpen size={15}/>查看完整纪要<ArrowUpRight size={13}/></button>}</section>;
 return <section className={'meeting-map meeting-diagram'+(model.structured?' meeting-map-structured':'')+(composition==='overview'?' meeting-map-overview':'')+(hasResults?' meeting-map-has-results':'')} aria-label={composition==='overview'?'主题与观点总览':'会议图解'}>
  {!model.structured&&<div className="meeting-map-tools"><span>{nodes.length} {unitLabel==='分组'?'个分组':'条要点'}</span><div><button type="button" disabled={!nodes.length||expanded.size===nodes.length} onClick={()=>setSelection({source:markdown,ids:new Set(nodes.map(node=>node.id))})}>展开全部</button><button type="button" disabled={!expanded.size} onClick={()=>setSelection({source:markdown,ids:new Set()})}>收起</button></div></div>}
  <div className="meeting-map-canvas">
   <div className={'meeting-map-origin'+(model.structured?' meeting-map-purpose':'')}>{!model.structured&&<GitBranch size={19} aria-hidden="true"/>}<div>{model.structured?<div className="meeting-map-purpose-heading"><strong>会议概览</strong><span>{nodes.length} 个{questionBased?'问题':'主题'}</span></div>:<strong>{title}</strong>}{model.purpose&&<p>{model.purpose}</p>}</div></div>
   {nodes.length>0&&<div className="meeting-map-topic-group">{model.structured?(composition==='overview'&&<div className="meeting-map-column-headings" aria-hidden="true"><span>{questionBased?'讨论的问题':'讨论主题'}</span><span>主要观点</span></div>):<div className="meeting-map-group-label">{unitLabel==='分组'?'内容分组':'讨论要点'}</div>}<ol className={'meeting-map-branches'+(model.structured?' meeting-map-organized':'')} aria-label={model.structured?(questionBased?'讨论的问题':'讨论主题'):unitLabel==='分组'?'内容分组':'讨论要点'}>
    {nodes.map((node,index)=><li key={node.id} data-source-text={node.text}>
     {model.structured?<MeetingTopicBrief topic={model.topics[index]} onLocate={onLocate} graphic/>:<details open={expanded.has(node.id)} onToggle={event=>{if(event.currentTarget===event.target)toggle(node.id,event.currentTarget.open);}}>
      <summary aria-controls={id+node.id}><span className="meeting-map-topic-number" aria-hidden="true">{String(index+1).padStart(2,'0')}</span><span className="meeting-map-topic-title">{node.title||unitLabel+' '+(index+1)}</span><ChevronDown size={14} aria-hidden="true"/></summary>
      <div className="meeting-map-topic-content" id={id+node.id}>
       <ul className="meeting-map-points" aria-label={unitLabel+' '+(index+1)+' 内容'}>{node.points.map((point,i)=><li key={i}><span>{point}</span></li>)}</ul>
       {onLocate&&<button type="button" aria-label={'查看'+unitLabel+' '+(index+1)+' 上下文'} onClick={()=>onLocate(node.section,node.text)}>原文<ArrowUpRight size={12} aria-hidden="true"/></button>}
      </div>
     </details>}
    </li>)}
   </ol></div>}
   {hasResults&&<div className="meeting-map-result-group"><div className="meeting-map-group-label">会议事项</div><div className="meeting-map-results">{model.groups.filter(g=>g.id!=='discussionQuestions').map(group=><ResultBranch key={group.id} group={group} onLocate={onLocate}/>)}</div></div>}
   {model.groups.filter(g=>g.id==='discussionQuestions').map(group=><details key={group.id} className="meeting-map-discussed"><summary>会中提问 · {group.items.length}<ChevronDown size={12}/></summary><ResultBranch group={group} onLocate={onLocate}/></details>)}
  </div>
  {onRead&&<button type="button" className="meeting-map-read" onClick={onRead}><BookOpen size={15} aria-hidden="true"/>完整纪要<ArrowUpRight size={13} aria-hidden="true"/></button>}
 </section>;
}
