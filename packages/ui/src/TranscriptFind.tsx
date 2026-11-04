import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {ChevronDown,ChevronUp,Search,X} from 'lucide-react';
import {transcriptMatches} from './transcriptMatching';
import './transcriptFind.css';

/** Search is a reading projection; callbacks, source objects and saved text are untouched. */
export function TranscriptFind({texts,children}:{texts:readonly string[];children:(highlight:(text:string,row:number)=>ReactNode)=>ReactNode}) {
 const [query,setQuery]=useState('');const [index,setIndex]=useState(0);
 const root=useRef<HTMLDivElement>(null);const input=useRef<HTMLInputElement>(null);
 const matches=useMemo(()=>transcriptMatches(texts,query),[texts,query]);
 const current=matches.length?Math.min(index,matches.length-1):-1;
 const byRow=useMemo(()=>{
  const result=new Map<number,Array<{start:number;end:number;index:number}>>();
  matches.forEach((match,i)=>{const row=result.get(match.row)??[];row.push({...match,index:i});result.set(match.row,row);});
  return result;
 },[matches]);
 useEffect(()=>{
  if(!query.trim()||current<0)return;
  const frame=window.requestAnimationFrame(()=>root.current?.querySelector<HTMLElement>('mark[data-find-current]')?.scrollIntoView({block:'center',behavior:'instant'}));
  return()=>window.cancelAnimationFrame(frame);
 },[query,current]);
 function move(delta:number){if(matches.length)setIndex((current+delta+matches.length)%matches.length);}
 function highlight(text:string,row:number):ReactNode {
  const found=byRow.get(row);if(!found)return text;
  const pieces:ReactNode[]=[];let offset=0;
  for(const match of found){pieces.push(text.slice(offset,match.start));pieces.push(<mark key={match.start} data-find-current={match.index===current?'true':undefined}>{text.slice(match.start,match.end)}</mark>);offset=match.end;}
  pieces.push(text.slice(offset));return pieces;
 }
 return <div className="transcript-find" ref={root}>
  <div className="transcript-find-toolbar" role="search" aria-label="查找转写内容">
   <label className="transcript-find-field"><Search size={16} aria-hidden="true"/><span className="transcript-find-sr">查找转写关键词</span><input ref={input} type="search" placeholder="查找这场会议的原文" maxLength={120} value={query} onChange={e=>{setQuery(e.target.value);setIndex(0);}} onKeyDown={e=>{
    if(e.key==='Enter'){e.preventDefault();move(e.shiftKey?-1:1);}
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();setQuery('');setIndex(0);}
   }}/></label>
   {query&&<><span className="transcript-find-count" role="status" aria-live="polite" aria-atomic="true">{matches.length?`${current+1} / ${matches.length}`:'未找到'}</span><div className="transcript-find-actions"><button type="button" aria-label="上一个匹配" disabled={!matches.length} onClick={()=>move(-1)}><ChevronUp size={17}/></button><button type="button" aria-label="下一个匹配" disabled={!matches.length} onClick={()=>move(1)}><ChevronDown size={17}/></button><button type="button" aria-label="清除查找" onClick={()=>{setQuery('');setIndex(0);input.current?.focus();}}><X size={16}/></button></div></>}
  </div>
  {children(highlight)}
 </div>;
}
