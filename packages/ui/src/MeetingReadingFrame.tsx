import {useEffect,useLayoutEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {meetingSectionTitles} from './meetingOutline';
import {isSourceOnlyMinutesDraft,meetingHeadingForDisplay} from './meetingReading';
import {ArrowLeft,BookOpen,GitBranch,List,ListTodo,Users,ChevronDown} from 'lucide-react';
import {MeetingMapView} from './MeetingMapView';
import {MeetingOverview} from './MeetingOverview';
import {MeetingSpeakers} from './MeetingSpeakers';
import {MeetingActions} from './MeetingActions';
import type {CompanionTranscriptSource} from '../../core/src/minutesSources';
import './meetingReadingFrame.css';
import './meetingVisual.css';

export function MeetingReadingFrame({markdown,title,sections=[],speakerSources=[],onOpenSpeakerSource,onLocateTranscript,decisionQuotes,questionQuotes,actionQuotes,actionSources,blocked=false,children}:{markdown:string;title?:string;sections?:readonly string[];speakerSources?:readonly CompanionTranscriptSource[];onOpenSpeakerSource?:(source:CompanionTranscriptSource)=>void;onLocateTranscript?:(text:string,returnId?:string)=>void;decisionQuotes?:ReadonlyMap<string,string[]>;questionQuotes?:ReadonlyMap<string,string[]>;actionQuotes?:ReadonlyMap<string,string[]>;actionSources?:ReadonlyMap<string,CompanionTranscriptSource[]>;blocked?:boolean;children:ReactNode}){
 const content=useRef<HTMLDivElement>(null);
 const outline=useRef<HTMLDetailsElement>(null);
 const viewControls=useRef<HTMLDivElement>(null);
 const sectionKey=sections.join('\n');
 const titles=useMemo(()=>sections.length?[...new Set(sections)]:meetingSectionTitles(markdown),[markdown,sectionKey]);
 const indexed=markdown.trim().length>=1600||titles.length>=7;
 const reviewPending=isSourceOnlyMinutesDraft(markdown);
 const initialView=reviewPending?'overview':'map';
 const [active,setActive]=useState<string|null>(null);
 const [view,setView]=useState<'overview'|'reading'|'map'|'speakers'|'actions'>(initialView);
 const [keypointView,setKeypointView]=useState<'overview'|'map'>(initialView);
 const returnView=useRef<Exclude<typeof view,'reading'>>(initialView);
 const sourceButton=useRef<HTMLElement|null>(null),restoreFocus=useRef(false);
 const keypoints=view==='map'||view==='overview';
 const viewLabels={overview:'重点列表',map:'重点图解',speakers:'发言人',actions:'待办'};
 function changeFormat(next:typeof keypointView){setKeypointView(next);setView(next);}
 useEffect(()=>{returnView.current=initialView;sourceButton.current=null;restoreFocus.current=false;setKeypointView(initialView);setView(initialView);},[markdown,title,initialView]);
 useLayoutEffect(()=>{if(!restoreFocus.current||view==='reading')return;restoreFocus.current=false;const target=sourceButton.current?.isConnected?sourceButton.current:viewControls.current?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]');target?.focus({preventScroll:true});target?.scrollIntoView({block:'nearest',behavior:'auto'});},[view]);
 function enterReading(){if(view!=='reading'){returnView.current=view;sourceButton.current=document.activeElement instanceof HTMLElement?document.activeElement:null;}setView('reading');}
 function returnToNotes(){restoreFocus.current=true;setView(returnView.current);}
 function read(){
  enterReading();
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
  enterReading();
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
  <div className="meeting-reading-start">
   <div className="meeting-reading-intro">
   {view!=='reading'?<div ref={viewControls} className="meeting-reading-views" role="group" aria-label="纪要视角">
    <button type="button" aria-pressed={keypoints} onClick={()=>setView(keypointView)}><BookOpen size={15} aria-hidden="true"/>重点</button>
    <button type="button" aria-pressed={view==='speakers'} onClick={()=>setView('speakers')}><Users size={15} aria-hidden="true"/>发言人</button>
    <button type="button" aria-pressed={view==='actions'} onClick={()=>setView('actions')}><ListTodo size={15} aria-hidden="true"/>待办</button>
   </div>:<span className="meeting-reading-label">完整纪要</span>}
   {keypoints&&<div className="meeting-reading-formats" role="group" aria-label="重点展示">
    <button type="button" aria-pressed={view==='map'} onClick={()=>changeFormat('map')}><GitBranch size={13} aria-hidden="true"/>图解</button>
    <button type="button" aria-pressed={view==='overview'} onClick={()=>changeFormat('overview')}><List size={13} aria-hidden="true"/>列表</button>
   </div>}
   {view==='reading'&&indexed&&titles.length>=2&&<details ref={outline} className="meeting-contents" onKeyDown={event=>{if(event.key==='Escape'){event.currentTarget.open=false;event.currentTarget.querySelector('summary')?.focus();}}}>
    <summary><List size={14} aria-hidden="true"/>目录<ChevronDown size={12} aria-hidden="true"/></summary>
    <nav className="meeting-outline" aria-label="会议目录">{titles.map((title,i)=><button type="button" key={i} aria-current={active===title?'location':undefined} onClick={()=>navigate(title)}>{meetingHeadingForDisplay(title)}</button>)}</nav>
   </details>}
   </div>
  </div>
  <div hidden={view!=='overview'}><MeetingOverview markdown={markdown} onLocate={navigate} onRead={read}/></div>
  <div className="meeting-graphic-surface" hidden={view!=='map'}><MeetingMapView markdown={markdown} title={title} onLocate={navigate} onRead={read}/></div>
  <div hidden={view!=='speakers'}><MeetingSpeakers markdown={markdown} sources={speakerSources} onOpenSource={onOpenSpeakerSource} blocked={blocked}/></div>
  <div hidden={view!=='actions'}><MeetingActions markdown={markdown} onLocate={navigate} onLocateTranscript={onLocateTranscript} onOpenSource={blocked?undefined:onOpenSpeakerSource} decisionQuotes={decisionQuotes} questionQuotes={questionQuotes} actionQuotes={actionQuotes} actionSources={actionSources} reviewPending={reviewPending}/></div>
  {view==='reading'&&<button type="button" className="meeting-reading-back" onClick={returnToNotes}><ArrowLeft size={14} aria-hidden="true"/>返回{viewLabels[returnView.current]}</button>}
  <div className="meeting-reading-content" ref={content} hidden={view!=='reading'}>{children}</div>
 </div>;
}
