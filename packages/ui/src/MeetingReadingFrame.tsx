import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {meetingSectionTitles} from './meetingOutline';
import {meetingHeadingForDisplay} from './meetingReading';
import './meetingReadingFrame.css';

export function MeetingReadingFrame({markdown,sections=[],children}:{markdown:string;sections?:readonly string[];children:ReactNode}){
 const content=useRef<HTMLDivElement>(null);
 const sectionKey=sections.join('\n');
 const titles=useMemo(()=>sections.length?[...new Set(sections)]:meetingSectionTitles(markdown),[markdown,sectionKey]);
 const indexed=markdown.trim().length>=1600||titles.length>=7;
 const [active,setActive]=useState<string|null>(null);
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
 },[markdown]);
 function navigate(title:string){
  const target=Array.from(content.current?.querySelectorAll<HTMLElement>('[data-meeting-heading]')??[])
   .find(el=>el.getAttribute('data-meeting-heading')===title);
  if(!target)return;
  for(let ancestor=target.parentElement;ancestor&&ancestor!==content.current;ancestor=ancestor.parentElement)
   if(ancestor.tagName==='DETAILS')(ancestor as HTMLDetailsElement).open=true;
  target.tabIndex=-1;target.focus({preventScroll:true});
  setActive(title);
  target.scrollIntoView({block:'start',behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
 }
 return <div className={`meeting-reading-frame${indexed?' meeting-reading-indexed':''}`}>
  {indexed&&titles.length>=2&&<aside className="meeting-reading-sidebar"><details className="meeting-outline-collapse"><summary>目录</summary><nav className="meeting-outline" aria-label="会议速览">
   {titles.map((title,i)=><button type="button" key={i} aria-current={active===title?'location':undefined} onClick={()=>navigate(title)}>{meetingHeadingForDisplay(title)}</button>)}
  </nav></details></aside>}
  <div className="meeting-reading-content" ref={content}>{children}</div>
 </div>;
}
