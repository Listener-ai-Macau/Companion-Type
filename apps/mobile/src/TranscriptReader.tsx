import { useEffect,useMemo, useState } from 'react';

import { cleanHesitations, transcriptParagraphs } from '../../../packages/ui/src/transcriptReading';
import {TranscriptFind} from '../../../packages/ui/src/TranscriptFind';
import type {TranscriptLookup} from '../../../packages/ui/src/transcriptMatching';

export function TranscriptReader({text,searchRequest,lookup,onReturnLookup}:{text:string;searchRequest?:TranscriptLookup|null;lookup?:TranscriptLookup|null;onReturnLookup?:()=>void}) {
 const [mode,setMode]=useState<'clean'|'original'>('clean');
 useEffect(()=>{if(searchRequest)setMode('original');},[searchRequest?.id]);
 useEffect(()=>{if(lookup)setMode('original');},[lookup?.id]);
 const cleaned=useMemo(()=>cleanHesitations(text),[text]);
 const reading=mode==='clean'?cleaned.text:text;
 const paragraphs=useMemo(()=>{let cursor=0;return transcriptParagraphs(reading).map(body=>{const start=reading.indexOf(body,cursor);cursor=start+body.length;return {body,start};});},[reading]);
 return <div className="transcript-reader"><div className="transcript-reader-toolbar"><div className="transcript-reader-switch" role="group" aria-label="转写阅读方式"><button type="button" aria-pressed={mode==='clean'} onClick={()=>setMode('clean')}>流畅阅读</button><button type="button" aria-pressed={mode==='original'} onClick={()=>setMode('original')}>原始转写</button></div></div><TranscriptFind texts={[reading]} searchRequest={searchRequest} lookup={lookup} onReturn={onReturnLookup}>{highlight=><div className="transcript">{paragraphs.map((paragraph,index)=><p key={index}>{highlight(paragraph.body,0,paragraph.start)}</p>)}</div>}</TranscriptFind><details className="transcript-reading-options"><summary>阅读说明</summary><p className="transcript-reader-note">流畅阅读略去长句中的停顿和重复起头；简短回应、引号内原话及数字条件保留。原始转写和导出不变。</p></details></div>;
}
