/** Local human context. These values are never inferred meeting decisions. */
export type ManualNoteKind='note'|'followup';
type EvidenceIdentity={
 id:string;
 name:string;
 sourceSha256:string;
 quote:string;
};
export type ManualNoteEvidence=EvidenceIdentity&(
 {kind:'document';documentId:string;extractionSha256:string;sectionId:string;sectionLabel:string;row?:number}|
 {kind:'transcript';documentId?:never;extractionSha256?:never;sectionId?:never;sectionLabel?:never;row?:never}
);
/** The owner is checked before attaching; it is not persisted as a library token. */
export type ManualEvidenceDraft={contextId:string;evidence:ManualNoteEvidence};
export const MANUAL_CONTEXT_LIMITS={references:16,quoteUtf16:4000,totalQuotesUtf16:16000,nameUtf16:200,sectionUtf16:160} as const;

export type ManualChecklistItem={line:number;markerOffset:number;checked:boolean;text:string};
/** Offsets refer to the unchanged UTF-16 source, including emoji and CRLF. */
export function manualChecklist(text:string):ManualChecklistItem[]{
 const items:ManualChecklistItem[]=[];let offset=0,line=0;
 for(const raw of text.match(/[^\n]*\n|[^\n]+$/g)??[]){
  const body=raw.replace(/\r?\n$/,''),match=/^(\s*[-*]\s+\[)([ xX])(\]\s+)(.+)$/.exec(body);
  if(match&&match[4].trim())items.push({line,markerOffset:offset+match[1].length,checked:match[2].toLowerCase()==='x',text:match[4]});
  offset+=raw.length;line++;
 }
 return items;
}
/** Reject a stale click instead of toggling a different sentence after an edit. */
export function toggleManualChecklist(current:string,expected:string,markerOffset:number,checked:boolean):string|null{
 if(current!==expected||!Number.isSafeInteger(markerOffset))return null;
 const item=manualChecklist(current).find(item=>item.markerOffset===markerOffset);
 if(!item)return null;
 return current.slice(0,markerOffset)+(checked?'x':' ')+current.slice(markerOffset+1);
}
/** A clearly labelled excerpt; the complete source is retained separately. */
export function manualQuotePreview(text:string,maxUtf16=MANUAL_CONTEXT_LIMITS.quoteUtf16):string{
 if(!Number.isSafeInteger(maxUtf16)||maxUtf16<1)return '';
 let end=Math.min(text.length,maxUtf16);
 if(end<text.length&&end>0&&/[\uD800-\uDBFF]/.test(text[end-1])&&/[\uDC00-\uDFFF]/.test(text[end]))end--;
 return text.slice(0,end);
}
/** Canonical literal row quote, also verified by each native note store. */
export function manualTableRowQuote(row:{row:number;cells:Array<{column:string;text:string}>}):string{
 return row.cells.map(cell=>cell.column+row.row+'\t'+cell.text).join('\n');
}
