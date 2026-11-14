import {useMemo} from 'react';
import {ArrowUpRight,MessageSquare,Users} from 'lucide-react';
import type {CompanionTranscriptSource} from '../../core/src/minutesSources';
import {minutesOutline,meetingListItems} from './meetingMap';

type SpeakerGroup={key:string;label:string;items:Array<{text:string;source?:CompanionTranscriptSource}>;from:'transcript'|'minutes';summary?:string[]};
/** Only explicit source labels establish identity. Unknown fragments never form a person. */
export function meetingSpeakerGroups(markdown:string,sources:readonly CompanionTranscriptSource[]=[]):SpeakerGroup[]{
 const groups=new Map<string,SpeakerGroup>();
 for(const source of sources){
  const label=source.speakerLabel?.trim()||(source.speaker==null?'':'说话人'+(source.speaker+1));
  if(!label||/^(?:未分配说话人|说话人[?？])$/.test(label)||!source.text.trim())continue;
  const key=label,group=groups.get(key)??{key,label,items:[],from:'transcript'};
  group.items.push({text:source.text,source});groups.set(key,group);
 }
 // Older saved native notes carry an explicit labelled source section. Use its
 // existing attribution; never infer participants from ordinary summary prose.
 const visit=(nodes:ReturnType<typeof minutesOutline>['children'])=>nodes.forEach(node=>{
  if(!sources.length&&node.title==='讨论纪要(按说话人)'){
   for(const line of meetingListItems(node.body)){
    const match=/^\*\*([^*\r\n]+)\*\*[:：]\s*([\s\S]+)$/.exec(line);
    if(!match||/^(?:说话人[?？]|未分配说话人)$/.test(match[1]))continue;
    const key=match[1],group=groups.get(key)??{key,label:key,items:[],from:'minutes'};
    group.items.push({text:match[2]});groups.set(key,group);
   }
  }
  visit(node.children);
 });
 visit(minutesOutline(markdown).children);
 // A model may supply concise, explicitly attributed points in the saved
 // note. Attach them only to an already established label; never create a
 // participant merely because an ordinary summary mentions a name.
 const summaries=(nodes:ReturnType<typeof minutesOutline>['children'])=>nodes.forEach(node=>{
  if(node.title==='发言要点'){
   for(const line of meetingListItems(node.body)){
    const match=/^\*\*([^*\r\n]+)\*\*[:：]\s*([\s\S]+)$/.exec(line);
    const group=match&&groups.get(match[1]);
    if(group)group.summary=[...(group.summary??[]),match![2]];
   }
  }
  summaries(node.children);
 });
 summaries(minutesOutline(markdown).children);
 return [...groups.values()];
}
export function MeetingSpeakers({markdown,sources=[],onOpenSource,blocked=false}:{markdown:string;sources?:readonly CompanionTranscriptSource[];onOpenSource?:(source:CompanionTranscriptSource)=>void;blocked?:boolean}){
 const groups=useMemo(()=>meetingSpeakerGroups(markdown,sources),[markdown,sources]);
 return <section className="meeting-speakers" aria-label="谁说了什么">
  <div className="meeting-speakers-heading"><div><Users size={18} aria-hidden="true"/><h3>谁说了什么</h3></div><span>{groups.length?groups.length+' 个发言标签':'尚未区分发言人'}</span></div>
  {groups.length?<><p className="meeting-speakers-hint">有已保存的发言要点时优先展示；其余显示原话摘录。发言归属和整理内容可展开核对。</p><div className="meeting-speaker-list">{groups.map((group,i)=><article className="meeting-speaker-card" key={group.key}>
   <header><span className="meeting-speaker-avatar" aria-hidden="true">{String(i+1).padStart(2,'0')}</span><div><h4>{group.label.replace(/^说话人(\d+)$/,'发言人$1')}</h4><small>{group.from==='transcript'?group.items.length+' 段原话':'来自已保存纪要'}</small></div><MessageSquare size={15} aria-hidden="true"/></header>
   {group.summary?.length?<div className="meeting-speaker-points"><span>发言要点 · 来自纪要</span><ul>{group.summary.map((text,index)=><li key={index}>{text}</li>)}</ul></div>:<><span className="meeting-speaker-excerpt-label">原话摘录</span><div className="meeting-speaker-excerpt">{group.items.slice(0,2).map((item,index)=><blockquote key={index}>{item.text}</blockquote>)}</div></>}
   <details><summary>查看完整发言{group.items.length>1?' · '+group.items.length+' 段':''}</summary>{group.items.map((item,index)=><div className="meeting-speaker-utterance" key={index}><p>{item.text}</p>{item.source&&onOpenSource&&<button type="button" disabled={blocked} onClick={()=>onOpenSource(item.source!)}>{item.source.approximateTiming?'约 ':''}{Math.floor(item.source.startMs/60000)}:{String(Math.floor(item.source.startMs/1000)%60).padStart(2,'0')} · 查看原话<ArrowUpRight size={12}/></button>}</div>)}</details>
  </article>)}</div></>:<div className="meeting-speakers-empty"><span><Users size={25}/></span><strong>这份转写还没有区分发言人</strong><p>可以先按主题阅读。没有明确发言标签的内容，不会自动分给某个人。</p></div>}
 </section>;
}
