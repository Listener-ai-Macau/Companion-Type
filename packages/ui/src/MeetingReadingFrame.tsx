import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {meetingSectionTitles} from './meetingOutline';
import {meetingHeadingForDisplay} from './meetingReading';
import {ArrowLeft,BookOpen,GitBranch,List,Users,ChevronDown} from 'lucide-react';
import {MeetingMapView} from './MeetingMapView';
import {MeetingOverview} from './MeetingOverview';
import {MeetingSpeakers} from './MeetingSpeakers';
import type {CompanionTranscriptSource} from '../../core/src/minutesSources';
import './meetingReadingFrame.css';
import './meetingVisual.css';

export function MeetingReadingFrame({markdown,title,sections=[],speakerSources=[],onOpenSpeakerSource,blocked=false,children}:{markdown:string;title?:string;sections?:readonly string[];speakerSources?:readonly CompanionTranscriptSource[];onOpenSpeakerSource?:(source:CompanionTranscriptSource)=>void;blocked?:boolean;children:ReactNode}){
 const content=useRef<HTMLDivElement>(null);
 const outline=useRef<HTMLDetailsElement>(null);
 const sectionKey=sections.join('\n');
 const titles=useMemo(()=>sections.length?[...new Set(sections)]:meetingSectionTitles(markdown),[markdown,sectionKey]);
 const indexed=markdown.trim().length>=1600||titles.length>=7;
 const [active,setActive]=useState<string|null>(null);
 const [view,setView]=useState<'overview'|'reading'|'map'|'speakers'>('overview');
 useEffect(()=>{setView('overview');},[markdown,title]);
 function read(){
  setView('reading');
  window.requestAnimationFrame(()=>{const first=content.current?.querySelector<HTMLElement>('[data-meeting-heading]')??content.current;if(first){first.tabIndex=-1;first.focus({preventScroll:true});content.current?.parentElement?.querySelector('.meeting-reading-start')?.scrollIntoView({block:'start',behavior:'auto'});}});
 }
 useEffect(()=>{
  const canvas=content.current;if(!canvas)return;
  let root:HTMLElement|Window=window;
  for(let parent=canvas.parentElement;parent;parent=parent.parentElement){
   if(/auto|scroll/.test(window.getComputedStyle(parent).overflowY)){root=parent;break;}
  }
  let frame=0;
  const update=()=>{
   frame=0;
   const top=root===window?88:(root as HTMLElement).getBoundingClientRect().top+88;
   const headings=Array.from(canvas.querySelectorAll<HTMLElement>('[data-meeting-heading]')).filter(el=>el.getClientRects().length);
   const current=headings.filter(el=>el.getBoundingClientRect().top<=top).at(-1)??headings[0];
   setActive(current?.getAttribute('data-meeting-heading')??null);
  };
  const schedule=()=>{if(!frame)frame=window.requestAnimationFrame(update);};
  schedule();root.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);
  canvas.addEventListener('toggle',schedule,true);
  return()=>{root.removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);canvas.removeEventListener('toggle',schedule,true);window.cancelAnimationFrame(frame);};
 },[markdown,view]);
 function navigate(title:string,text?:string){
  setView('reading');
  window.requestAnimationFrame(()=>{
  const target=Array.from(content.current?.querySelectorAll<HTMLElement>('[data-meeting-heading]')??[])
   .find(el=>el.getAttribute('data-meeting-heading')===title);
  if(!target)return;
  for(let ancestor=target.parentElement;ancestor&&ancestor!==content.current;ancestor=ancestor.parentElement)
   if(ancestor.tagName==='DETAILS')(ancestor as HTMLDetailsElement).open=true;
  const exactText=text?.replace(/\s+/g,' ').trim();
  const item=exactText?Array.from(content.current?.querySelectorAll<HTMLElement>('.ct-overview-topic,.ct-minutes-item,.minutes-item')??[]).find(el=>el.getAttribute('data-meeting-topic')===text||el.textContent?.replace(/\s+/g,' ').trim()===exactText):null;
  const destination=item??target;
  destination.tabIndex=-1;destination.focus({preventScroll:true});
  if(outline.current)outline.current.open=false;
  setActive(title);
  destination.scrollIntoView({block:'start',behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  });
 }
 return <div className={`meeting-reading-frame${indexed?' meeting-reading-indexed':''}`}>
  {titles.length>0&&<div className="meeting-reading-start">
   <div className="meeting-reading-intro"><div className="meeting-reading-views" role="group" aria-label="纪要查看方式">
    <button type="button" aria-pressed={view==='overview'||view==='reading'} onClick={()=>setView('overview')}><BookOpen size={14} aria-hidden="true"/>会议一览</button>
    <button type="button" aria-pressed={view==='map'} onClick={()=>setView('map')}><GitBranch size={14} aria-hidden="true"/>思维导图</button>
    <button type="button" aria-pressed={view==='speakers'} onClick={()=>setView('speakers')}><Users size={14} aria-hidden="true"/>按发言人</button>
   </div>
   {view==='reading'&&indexed&&titles.length>=2&&<details ref={outline} className="meeting-contents" onKeyDown={event=>{if(event.key==='Escape'){event.currentTarget.open=false;event.currentTarget.querySelector('summary')?.focus();}}}>
    <summary><List size={14} aria-hidden="true"/>目录<ChevronDown size={12} aria-hidden="true"/></summary>
    <nav className="meeting-outline" aria-label="会议目录">{titles.map((title,i)=><button type="button" key={i} aria-current={active===title?'location':undefined} onClick={()=>navigate(title)}>{meetingHeadingForDisplay(title)}</button>)}</nav>
   </details>}
   </div>
  </div>}
  {view==='overview'&&<MeetingOverview markdown={markdown} onLocate={navigate} onRead={read}/>}
  {view==='map'&&<MeetingMapView markdown={markdown} title={title} onLocate={navigate}/>}
  {view==='speakers'&&<MeetingSpeakers markdown={markdown} sources={speakerSources} onOpenSource={onOpenSpeakerSource} blocked={blocked}/>}
  {view==='reading'&&<button type="button" className="meeting-reading-back" onClick={()=>{setView('overview');window.requestAnimationFrame(()=>content.current?.parentElement?.querySelector<HTMLElement>('.meeting-reading-views>button')?.focus());}}><ArrowLeft size={14} aria-hidden="true"/>返回会议一览</button>}
  <div className="meeting-reading-content" ref={content} hidden={view!=='reading'}>{children}</div>
 </div>;
}
