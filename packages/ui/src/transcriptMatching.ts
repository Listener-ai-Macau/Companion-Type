export type TranscriptMatch={row:number;start:number;end:number};
/** Literal, Unicode-safe matches. Original text, speaker and timing never change. */
export function transcriptMatches(texts:readonly string[],query:string):TranscriptMatch[] {
 const term=query.trim();if(!term)return [];
 const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const pattern=new RegExp(escaped,'giu');
 return texts.flatMap((text,row)=>Array.from(text.matchAll(pattern),match=>({row,start:match.index!,end:match.index!+match[0].length})));
}
