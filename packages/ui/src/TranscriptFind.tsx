import {useEffect,useMemo,useRef,useState,type ReactNode} from 'react';
import {ChevronDown,ChevronUp,Search,X} from 'lucide-react';
import {transcriptMatches,transcriptLookupTerms,type TranscriptLookup} from './transcriptMatching';
import './transcriptFind.css';

/** Search is a reading projection; callbacks, source objects and saved text are untouched. */
export function TranscriptFind({texts,children,lookup,onReturn,searchRequest,lookupKind='minutes'}:{texts:readonly string[];children:(highlight:(text:string,row:number,offset?:number)=>ReactNode)=>ReactNode;lookupKind?:'minutes'|'note';lookup?:TranscriptLookup|null;onReturn?:()=>void;searchRequest?:TranscriptLookup|null}) {
 const [query,setQuery]=useState('');const [index,setIndex]=useState(0);
 const root=useRef<HTMLDivElement>(null);const input=useRef<HTMLInputElement>(null);
 const matches=useMemo(()=>transcriptMatches(texts,query),[texts,query]);
 const suggestions=useMemo(()=>lookup?transcriptLookupTerms(texts,lookup.text):[],[texts,lookup?.id]);
 useEffect(()=>{if(searchRequest){setQuery(searchRequest.text);setIndex(0);}},[searchRequest?.id]);
 useEffect(()=>{
  if(!lookup)return;setQuery('');setIndex(0);
  const frame=window.requestAnimationFrame(()=>{root.current?.scrollIntoView({block:'start',behavior:'instant'});input.current?.focus({preventScroll:true});});
  return()=>window.cancelAnimationFrame(frame);
 },[lookup?.id]);
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
 function highlight(text:string,row:number,offset=0):ReactNode {
  const found=byRow.get(row);if(!found)return text;
  const pieces:ReactNode[]=[];let cursor=0;
  for(const match of found){
   const start=Math.max(0,match.start-offset),end=Math.min(text.length,match.end-offset);
   if(start>=end)continue;
   pieces.push(text.slice(cursor,start));pieces.push(<mark key={match.start} data-find-current={match.index===current?'true':undefined}>{text.slice(start,end)}</mark>);cursor=end;
  }
  pieces.push(text.slice(cursor));return pieces;
 }
 return <div className="transcript-find" ref={root}>
  {lookup&&<section className="transcript-lookup" aria-label={lookupKind==='note'?'待核对的补充依据':'待核对的纪要内容'}><div className="transcript-lookup-heading"><strong>{lookupKind==='note'?'核对这条补充的原文依据':'这条纪要尚未匹配到原话'}</strong>{onReturn&&<button type="button" onClick={onReturn}>{lookupKind==='note'?'返回这条补充':'返回这条纪要'}</button>}</div><blockquote>{lookup.text}</blockquote><p>下面只做文字查找，不代表已核实这条纪要或定位到准确录音位置。请选择关键词，再结合上下文核对。</p>{suggestions.length>0?<div className="transcript-lookup-terms" role="group" aria-label="原文中出现的关键词">{suggestions.map(item=><button type="button" key={item.term} aria-pressed={query===item.term} onClick={()=>{setQuery(item.term);setIndex(0);}}>{item.term}<small>{item.count} 处</small></button>)}</div>:<p>没有可直接匹配的关键词，可在下方输入你记得的词句。</p>}</section>}
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
