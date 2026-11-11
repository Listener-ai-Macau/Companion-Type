import {useMemo,useRef,useState} from 'react';
import {type ManualEvidenceDraft} from '../../core/src/manualNoteContext';
import {transcriptMatches} from './transcriptMatching';

function literalParts(text:string){
 const parts:Array<{start:number;end:number;text:string}>=[];let start=0;
 while(start<text.length){
  let end=Math.min(start+420,text.length);
  if(end<text.length&&/[\uD800-\uDBFF]/.test(text[end-1])&&/[\uDC00-\uDFFF]/.test(text[end]))end--;
  if(end<text.length){const candidate=text.slice(start,end),breakAt=Math.max(candidate.lastIndexOf('\n'),candidate.lastIndexOf('。'),candidate.lastIndexOf('！'),candidate.lastIndexOf('？'));if(breakAt>180)end=start+breakAt+1;}
  parts.push({start,end,text:text.slice(start,end)});start=end;
 }
 return parts.filter(part=>part.text.trim());
}
export function TranscriptQuoteCapture({contextId,text,busy,onQuote}:{contextId:string;text:string;busy?:boolean;onQuote:(draft:ManualEvidenceDraft)=>void}){
 const [quote,setQuote]=useState(''),[open,setOpen]=useState(false),[error,setError]=useState(''),[working,setWorking]=useState(false),[query,setQuery]=useState(''),[page,setPage]=useState(0);
 const selection=useRef('');
 const parts=useMemo(()=>literalParts(text),[text]);
 const choices=useMemo(()=>query.trim()?transcriptMatches([text],query.trim()).slice(0,60).map(match=>{
  let start=Math.max(0,match.start-120),end=Math.min(text.length,Math.max(start+420,match.end));
  if(start>0&&/[\uDC00-\uDFFF]/.test(text[start])&&/[\uD800-\uDBFF]/.test(text[start-1]))start--;
  if(end<text.length&&/[\uD800-\uDBFF]/.test(text[end-1])&&/[\uDC00-\uDFFF]/.test(text[end]))end--;
  return {start,end,text:text.slice(start,end)};
 }):parts,[text,query,parts]);
 const pages=Math.max(1,Math.ceil(choices.length/3)),current=Math.min(page,pages-1);
 async function capture(literal:string){
  if(!literal.trim()||!text.includes(literal)){setError('请引用当前原始转写中连续的一段文字；精简阅读省略的字词需要补回。');return;}
  if(literal.length>4000){setError('一次最多引用4000字符，请缩短所选片段；完整转写保留。');return;}
  setWorking(true);setError('');try{
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)),hash=[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
   onQuote({contextId,evidence:{id:crypto.randomUUID(),kind:'transcript',name:'会议转写',quote:literal,sourceSha256:hash}});setQuote('');setOpen(false);
  }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setWorking(false);}
 }
 return <div className="manual-source-picker"><button type="button" className="manual-quote-action" disabled={busy||working}
  onPointerDown={()=>{selection.current=window.getSelection()?.toString()??'';}}
  onClick={()=>{const selected=selection.current||window.getSelection()?.toString()||'';selection.current='';if(selected&&text.includes(selected))void capture(selected);else{setQuote('');setPage(0);setQuery('');setOpen(true);setError('');}}}>引用转写到备注</button>
  {open&&<section className="manual-quote-picker" aria-label="选择转写原文">
   <div className="manual-quote-heading"><strong>选择原文，留作依据</strong><button type="button" className="manual-quote-action" disabled={working} onClick={()=>setOpen(false)}>取消引用</button></div>
   <p>下面保留原文原字，可直接选一段；长按选中文字后点“引用转写到备注”，也能只引用所选文字。</p>
   <label className="manual-quote-search">查找原文<input type="search" aria-label="查找可引用的原文" value={query} maxLength={120} disabled={busy||working} onChange={event=>{setQuery(event.target.value);setPage(0);}}/></label>
   {!choices.length&&<p role="status">没有找到这段原文。可以更换关键词，或展开下方输入指定原文。</p>}
   <div className="manual-quote-options">{choices.slice(current*3,current*3+3).map((part,index)=><article key={part.start+':'+part.end}><blockquote>{part.text}</blockquote><button type="button" className="manual-quote-action" aria-label={'引用原文片段 '+(current*3+index+1)} disabled={busy||working} onClick={()=>void capture(part.text)}>引用此段到备注</button></article>)}</div>
   {pages>1&&<nav className="manual-quote-pages" aria-label="原文片段翻页"><button type="button" disabled={busy||working||current===0} onClick={()=>setPage(current-1)}>上一组</button><span>{current+1} / {pages}</span><button type="button" disabled={busy||working||current+1>=pages} onClick={()=>setPage(current+1)}>下一组</button></nav>}
   <details className="manual-quote-exact"><summary>输入指定的原文片段</summary><textarea aria-label="引用的转写原文" maxLength={4000} value={quote} disabled={busy||working} onChange={event=>setQuote(event.target.value)}/><button type="button" className="manual-quote-action" disabled={busy||working||!quote.trim()} onClick={()=>void capture(quote)}>加入备注草稿</button></details>
  </section>}
  {error&&<p role="alert">{error}</p>}
 </div>;
}
