import {useId,useMemo,useState,type ReactNode,type CSSProperties} from 'react';
import {ArrowUpRight,CheckCheck,ChevronDown,GitBranch,ListTodo,MessageCircleQuestion} from 'lucide-react';
import {meetingMapModel,type MeetingMapSection} from './meetingMap';
import './meetingMap.css';

function MapSection({label,section,icon,onLocate}:{label:string;section:MeetingMapSection;icon:ReactNode;onLocate?:(section:string,text?:string)=>void}){
 return <details className="meeting-map-outcome"><summary>{icon}<span>{label}</span><small>{section.items.length||'—'}</small><ChevronDown size={14} aria-hidden="true"/></summary>
  {section.items.length?<div className="meeting-map-outcome-content">{section.items.map((item,i)=><p key={i}>{item}</p>)}{onLocate&&<button type="button" onClick={()=>onLocate(section.title)}>在纪要中查看<ArrowUpRight size={13}/></button>}</div>:<p className="meeting-map-no-items">这份纪要未列出{label}。</p>}
 </details>;
}
/** A view of the saved note, with exact full wording behind every topic. */
export function MeetingMapView({markdown,title='会议脉络',onLocate}:{markdown:string;title?:string;onLocate?:(section:string,text?:string)=>void}){
 const model=useMemo(()=>meetingMapModel(markdown),[markdown]);
 const [selection,setSelection]=useState<{source:string;ids:ReadonlySet<string>}>({source:markdown,ids:new Set()});
 const expanded=selection.source===markdown?selection.ids:new Set<string>(),id=useId();
 const toggle=(key:string,open:boolean)=>setSelection(previous=>{
  const next=new Set(previous.source===markdown?previous.ids:[]);
  if(next.has(key)===open)return previous;
  if(open)next.add(key);else next.delete(key);return {source:markdown,ids:next};
 });
 return <section className="meeting-map" aria-label="会议思维导图">
  <div className="meeting-map-tools"><p><span className="meeting-map-live-dot" aria-hidden="true"/>{model.topics.length} 个主题 · 点开查看内容</p><div>
   <button type="button" disabled={!model.topics.length||expanded.size===model.topics.length} onClick={()=>setSelection({source:markdown,ids:new Set(model.topics.map(t=>t.id))})}>展开全部</button>
   <button type="button" disabled={!expanded.size} onClick={()=>setSelection({source:markdown,ids:new Set()})}>收起</button>
  </div></div>
  <div className="meeting-map-canvas">
   <div className="meeting-map-origin"><span className="meeting-map-origin-icon"><GitBranch size={20} aria-hidden="true"/></span><div><small>会议主题</small><strong>{title}</strong></div></div>
   {model.topics.length?<ol className="meeting-map-branches">{model.topics.map((topic,i)=><li key={topic.id} style={{'--map-branch':i%3} as CSSProperties}>
    <details open={expanded.has(topic.id)} onToggle={event=>{if(event.currentTarget===event.target)toggle(topic.id,event.currentTarget.open);}}>
     <summary aria-controls={id+topic.id}><span className="meeting-map-topic-number">{String(i+1).padStart(2,'0')}</span><span className="meeting-map-topic-title">{topic.label}</span><ChevronDown size={15} aria-hidden="true"/></summary>
     <div className="meeting-map-topic-content" id={id+topic.id}><p>{topic.text}</p>{onLocate&&<button type="button" onClick={()=>onLocate(topic.section,topic.text)}>查看纪要上下文<ArrowUpRight size={13}/></button>}</div>
    </details>
   </li>)}</ol>:<div className="meeting-map-empty"><strong>这份纪要还没有主题分组</strong><p>可以先阅读完整纪要；有标题或要点后，会在这里显示结构。</p></div>}
  </div>
  {(model.decisions||model.actions||model.questions)&&<div className="meeting-map-outcomes" aria-label="会议结论与跟进">
   {model.decisions&&<MapSection label="讨论结论" section={model.decisions} icon={<CheckCheck size={16}/>} onLocate={onLocate}/>}
   {model.actions&&<MapSection label="行动事项" section={model.actions} icon={<ListTodo size={16}/>} onLocate={onLocate}/>}
   {model.questions&&<MapSection label="待确认" section={model.questions} icon={<MessageCircleQuestion size={16}/>} onLocate={onLocate}/>}
  </div>}
  <p className="meeting-map-caption">来自已保存纪要 · 保留原有表述，内容可回到纪要核对</p>
 </section>;
}
