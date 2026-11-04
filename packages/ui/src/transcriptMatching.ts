export type TranscriptMatch={row:number;start:number;end:number};
export type TranscriptLookup={id:string;text:string};
/** Literal, Unicode-safe matches. Original text, speaker and timing never change. */
export function transcriptMatches(texts:readonly string[],query:string):TranscriptMatch[] {
 const term=query.trim();if(!term)return [];
 const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const pattern=new RegExp(escaped,'giu');
 return texts.flatMap((text,row)=>Array.from(text.matchAll(pattern),match=>({row,start:match.index!,end:match.index!+match[0].length})));
}

/** Lexical suggestions only: every offered term must literally exist in both texts. */
export function transcriptLookupTerms(texts:readonly string[],summary:string):Array<{term:string;count:number}> {
 const Constructor=(Intl as unknown as {Segmenter?:new(locale:string,options:{granularity:string})=>{segment(text:string):Iterable<{segment:string;isWordLike?:boolean}>}}).Segmenter;
 if(!Constructor)return [];
 const ignored=new Set(['待核对','核对','负责人','未指定','未明确','时间','会议','相关','内容','进行','要求','确认','建议','负责','安排','讨论','事项','尽快','完成','准备','明确','包括','需要']);
 const terms=[...new Set([...new Constructor('zh',{granularity:'word'}).segment(summary)].filter(item=>item.isWordLike).map(item=>item.segment))]
  .filter(term=>term.length>=2&&term.length<=20&&!ignored.has(term));
 return terms.map(term=>({term,count:transcriptMatches(texts,term).length})).filter(item=>item.count>0)
  .sort((a,b)=>b.term.length-a.term.length||a.count-b.count).slice(0,8);
}
