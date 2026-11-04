import { splitShortMinutesEvidence } from '../../../packages/ui/src/briefMinutes';

type EvidenceDetail = {transcript:string;before:string|null;minutesChanged:boolean;transcriptUnreadable?:boolean;beforeUnreadable?:boolean};
export type TimedOriginal = {available:boolean;original:boolean;windows?:{text:string;startMs:number;endMs:number}[]};
export type EvidenceEntry = {label:string;text:string;quote:string};

/** Only expose the backend's known, source-validated evidence format. */
export function splitMobileEvidence(markdown:string,detail:EvidenceDetail):{overview:string;entries:EvidenceEntry[]}|null {
  // Older Android WebViews may not have matchAll; fall back to the complete,
  // unmodified minutes instead of failing to render the recording.
  if(detail.transcriptUnreadable||!detail.transcript||typeof markdown.matchAll!=='function')return null;
  const parsed=splitShortMinutesEvidence(markdown,detail.transcript);
  if(!parsed)return null;
  const entries:EvidenceEntry[]=[];
  for(const block of parsed.evidence.trimEnd().split(/\r?\n\r?\n/)) {
    const match=/^- (摘要|决定|事项|问题)：([^\r\n]+)\r?\n- 原话：“([^\r\n]+)”$/.exec(block);
    if(!match)return null;
    entries.push({label:match[1],text:match[2],quote:match[3]});
  }
  return {overview:parsed.overview,entries};
}

function occurrenceCount(text:string,quote:string):number {
  let count=0,position=0;
  while((position=text.indexOf(quote,position))!==-1){count++;if(count>1)return count;position++;}
  return count;
}

// The generated evidence may replace a source line break with a space. Do not
// normalize punctuation or wording: they can change the meaning of a quote.
const withoutWhitespace=(s:string)=>s.replace(/\s/g,'');
export function uniqueMobileQuote(source:string,quote:string):boolean {
  const needle=withoutWhitespace(quote);
  return Array.from(needle).length>=4 && occurrenceCount(withoutWhitespace(source),needle)===1;
}

/** A quote can point to a time only when the saved source and the timing agree uniquely. */
export function uniqueMobileEvidenceWindow(detail:EvidenceDetail,timing:TimedOriginal,quote:string):number|null {
  if(detail.minutesChanged||detail.transcriptUnreadable||detail.beforeUnreadable||!timing.available||Array.from(quote).length<4)return null;
  const source=timing.original?detail.before:detail.transcript;
  if(source===null||(!timing.original&&detail.before!==null)||!uniqueMobileQuote(source,quote)||!uniqueMobileQuote(detail.transcript,quote))return null;
  if(!Array.isArray(timing.windows))return null;
  const needle=withoutWhitespace(quote);
  let found:number|null=null;
  for(let i=0;i<timing.windows.length;i++){
    const w=timing.windows[i];
    if(typeof w.text!=='string')return null;
    const count=occurrenceCount(withoutWhitespace(w.text),needle);
    if(count===0)continue;
    if(count!==1||found!==null||!Number.isSafeInteger(w.startMs)||!Number.isSafeInteger(w.endMs)||w.startMs<0||w.endMs<=w.startMs)return null;
    found=i;
  }
  if(found!==null)return found;

  // A sentence may cross an ASR window boundary. Only join windows when they
  // reconstruct the entire saved source, ignoring whitespace (the backend may
  // insert line breaks between windows). This avoids guessing from a partial or
  // stale timing index, or attributing a repeated phrase to the wrong time.
  const compact=withoutWhitespace,sourceText=compact(source);
  if(!needle||occurrenceCount(sourceText,needle)!==1)return null;
  let joined='',previousEnd=-1;
  const starts:number[]=[];
  for(const w of timing.windows){
    if(typeof w.text!=='string'||!Number.isSafeInteger(w.startMs)||!Number.isSafeInteger(w.endMs)||w.startMs<0||w.endMs<=w.startMs||w.startMs<previousEnd)return null;
    starts.push(joined.length);joined+=compact(w.text);previousEnd=w.endMs;
  }
  if(joined!==sourceText||occurrenceCount(joined,needle)!==1)return null;
  const offset=joined.indexOf(needle);
  for(let i=starts.length-1;i>=0;i--){
    if(starts[i]<=offset && compact(timing.windows[i].text).length>0)return i;
  }
  return null;
}
