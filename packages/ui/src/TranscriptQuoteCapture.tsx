import {useState} from 'react';
import {manualQuotePreview,type ManualEvidenceDraft} from '../../core/src/manualNoteContext';
export function TranscriptQuoteCapture({contextId,text,busy,onQuote}:{contextId:string;text:string;busy?:boolean;onQuote:(draft:ManualEvidenceDraft)=>void}){
 const [quote,setQuote]=useState(''),[open,setOpen]=useState(false),[error,setError]=useState(''),[working,setWorking]=useState(false);
 async function capture(literal:string){
  if(!literal.trim()||!text.includes(literal)){setError('请引用当前原始转写中连续的一段文字；精简阅读省略的字词需要补回。');return;}
  if(literal.length>4000){setError('一次最多引用4000字符，请缩短所选片段；完整转写保留。');return;}
  setWorking(true);setError('');try{
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)),hash=[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
   onQuote({contextId,evidence:{id:crypto.randomUUID(),kind:'transcript',name:'会议转写',quote:literal,sourceSha256:hash}});setQuote('');setOpen(false);
  }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setWorking(false);}
 }
 return <div className="manual-source-picker"><button type="button" className="manual-quote-action" disabled={busy||working} onClick={()=>{const selected=window.getSelection()?.toString()??'';if(selected&&text.includes(selected))void capture(selected);else{setQuote(manualQuotePreview(selected));setOpen(true);setError('');}}}>引用转写到备注</button>{open&&<><p>从原始转写复制一段文字到下方，保存到备注后可返回依据。引文不会自动变成会议决定。</p><textarea aria-label="引用的转写原文" maxLength={4000} value={quote} disabled={busy||working} onChange={e=>setQuote(e.target.value)}/><button type="button" className="manual-quote-action" disabled={busy||working||!quote.trim()} onClick={()=>void capture(quote)}>加入备注草稿</button><button type="button" className="manual-quote-action" disabled={working} onClick={()=>setOpen(false)}>取消引用</button></>}{error&&<p role="alert">{error}</p>}</div>;
}
