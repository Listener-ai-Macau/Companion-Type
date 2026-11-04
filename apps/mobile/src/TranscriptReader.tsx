import { useMemo, useState } from 'react';

import { cleanHesitations } from '../../../packages/ui/src/transcriptReading';

export function TranscriptReader({text}:{text:string}) {
 const [mode,setMode]=useState<'clean'|'original'>('clean');
 const cleaned=useMemo(()=>cleanHesitations(text),[text]);
 return <div className="transcript-reader"><div className="transcript-reader-toolbar"><div className="transcript-reader-switch" role="group" aria-label="转写阅读方式"><button type="button" aria-pressed={mode==='clean'} onClick={()=>setMode('clean')}>精简阅读</button><button type="button" aria-pressed={mode==='original'} onClick={()=>setMode('original')}>原始转写</button></div><span>{mode==='clean'&&cleaned.removed?`已略去 ${cleaned.removed} 个语气字`:mode==='original'?'识别原文':'未发现可清理的语气字'}</span></div>{mode==='clean'&&cleaned.removed>0&&<p className="transcript-reader-note">仅在阅读时略去“嗯、呃”，不改动原文；简短回应也可能被略去，请对照原始转写。</p>}<p className="transcript">{mode==='clean'?cleaned.text:text}</p></div>;
}
