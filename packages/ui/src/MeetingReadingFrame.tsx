import {useRef,type ReactNode} from 'react';
import {ArrowUpRight,CheckCheck,ListTodo,MessageCircle,TextQuote} from 'lucide-react';
import {meetingOutline} from './meetingOutline';
import {meetingHeadingForDisplay} from './meetingReading';
import './meetingReadingFrame.css';

const icons={summary:TextQuote,decisions:CheckCheck,actions:ListTodo,questions:MessageCircle};
export function MeetingReadingFrame({markdown,sections=[],children}:{markdown:string;sections?:readonly string[];children:ReactNode}){
 const content=useRef<HTMLDivElement>(null);const items=meetingOutline(markdown);
 function navigate(title:string){
  const target=Array.from(content.current?.querySelectorAll<HTMLElement>('[data-meeting-heading]')??[])
   .find(el=>el.getAttribute('data-meeting-heading')===title);
  if(!target)return;
  for(let ancestor=target.parentElement;ancestor&&ancestor!==content.current;ancestor=ancestor.parentElement)
   if(ancestor.tagName==='DETAILS')(ancestor as HTMLDetailsElement).open=true;
  target.tabIndex=-1;target.focus({preventScroll:true});
  target.scrollIntoView({block:'start',behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
 }
 return <div className="meeting-reading-frame">
  {(items.length>=2||sections.length>=2)&&<nav className="meeting-outline" aria-label="会议速览">
   <div className="meeting-outline-heading"><span>会议速览</span><small>点选查看对应内容</small></div>
   {items.length>=2&&<div className="meeting-outline-grid">{items.map(item=>{const Icon=icons[item.kind];return <button type="button" key={item.kind}
    className={`meeting-outline-card meeting-outline-${item.kind}`} onClick={()=>navigate(item.title)} aria-label={`${item.label}，${item.count} 条，${item.hint}`}>
    <span className="meeting-outline-label"><Icon size={16} aria-hidden="true"/>{item.label}<ArrowUpRight size={13} aria-hidden="true"/></span>
    <span className="meeting-outline-number">{item.count}<small>条</small></span><span className="meeting-outline-hint">{item.hint}</span>
   </button>;})}</div>}
   {sections.length>=2&&<details className="meeting-outline-sections" open={items.length<2?true:undefined}><summary>查看全部章节</summary><div>{sections.map((title,i)=><button type="button" key={i} onClick={()=>navigate(title)}>{meetingHeadingForDisplay(title)}</button>)}</div></details>}
  </nav>}
  <div className="meeting-reading-content" ref={content}>{children}</div>
 </div>;
}
