import { useEffect,useMemo, useState } from 'react';

import { cleanHesitations } from '../../../packages/ui/src/transcriptReading';
import {TranscriptFind} from '../../../packages/ui/src/TranscriptFind';
import type {TranscriptLookup} from '../../../packages/ui/src/transcriptMatching';

export function TranscriptReader({text,searchRequest,lookup,onReturnLookup}:{text:string;searchRequest?:TranscriptLookup|null;lookup?:TranscriptLookup|null;onReturnLookup?:()=>void}) {
 const [mode,setMode]=useState<'clean'|'original'>(searchRequest?'original':'clean');
 useEffect(()=>{if(searchRequest)setMode('original');},[searchRequest?.id]);
 useEffect(()=>{if(lookup)setMode('original');},[lookup?.id]);
 const cleaned=useMemo(()=>cleanHesitations(text),[text]);
 const reading=mode==='clean'?cleaned.text:text;
 return <div className="transcript-reader"><div className="transcript-reader-toolbar"><div className="transcript-reader-switch" role="group" aria-label="转写阅读方式"><button type="button" aria-pressed={mode==='clean'} onClick={()=>setMode('clean')}>精简阅读</button><button type="button" aria-pressed={mode==='original'} onClick={()=>setMode('original')}>原始转写</button></div><span>{mode==='clean'&&cleaned.removed?`已略去 ${cleaned.removed} 个语气字`:mode==='original'?'识别原文':'未发现可清理的语气字'}</span></div>{mode==='clean'&&cleaned.removed>0&&<p className="transcript-reader-note">仅在阅读时略去“嗯、呃”，不改动原文；简短回应也可能被略去，请对照原始转写。</p>}<TranscriptFind texts={[reading]} searchRequest={searchRequest} lookup={lookup} onReturn={onReturnLookup}>{highlight=><p className="transcript">{highlight(reading,0)}</p>}</TranscriptFind></div>;
}
