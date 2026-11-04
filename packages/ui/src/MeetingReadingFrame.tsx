import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {ArrowUpRight,CheckCheck,ListTodo,MessageCircle,TextQuote} from 'lucide-react';
import {meetingOutline,meetingSectionTitles} from './meetingOutline';
import {meetingHeadingForDisplay} from './meetingReading';
import './meetingReadingFrame.css';

const icons={summary:TextQuote,decisions:CheckCheck,actions:ListTodo,questions:MessageCircle};
export function MeetingReadingFrame({markdown,sections=[],children}:{markdown:string;sections?:readonly string[];children:ReactNode}){
 const content=useRef<HTMLDivElement>(null);
 const items=useMemo(()=>meetingOutline(markdown),[markdown]);
 const sectionKey=sections.join('\n');
 const titles=useMemo(()=>sections.length?[...new Set(sections)]:meetingSectionTitles(markdown),[markdown,sectionKey]);
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
 return <div className={`meeting-reading-frame${items.length>=2||titles.length>=2?' meeting-reading-indexed':''}`}>
  {(items.length>=2||titles.length>=2)&&<aside className="meeting-reading-sidebar"><nav className="meeting-outline" aria-label="会议速览">
   <div className="meeting-outline-heading"><span>本场会议</span><small>内容导航</small></div>
   {items.length>=2&&<div className="meeting-outline-grid">{items.map(item=>{const Icon=icons[item.kind];return <button type="button" key={item.kind}
    className={`meeting-outline-card meeting-outline-${item.kind}`} onClick={()=>navigate(item.title)} aria-current={active===item.title?'location':undefined} aria-label={`${item.label}，${item.count} 条，${item.hint}`}>
    <span className="meeting-outline-label"><Icon size={16} aria-hidden="true"/>{item.label}<ArrowUpRight size={13} aria-hidden="true"/></span>
    <span className="meeting-outline-number">{item.count}<small>条</small></span><span className="meeting-outline-hint">{item.hint}</span>
   </button>;})}</div>}
   {titles.length>=2&&<details className="meeting-outline-sections" open={items.length<2?true:undefined}><summary>查看全部章节</summary><div>{titles.map((title,i)=><button type="button" key={i} aria-current={active===title?'location':undefined} onClick={()=>navigate(title)}>{meetingHeadingForDisplay(title)}</button>)}</div></details>}
  </nav></aside>}
  <div className="meeting-reading-content" ref={content}>{children}</div>
 </div>;
}
