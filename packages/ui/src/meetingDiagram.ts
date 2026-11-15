import {topicReadingParts} from './MeetingTopic';

/** Split only explicit peer statements. Words, conditions and attribution stay literal. */
export function meetingJudgmentFragments(text:string):string[]{
 const pairs:Record<string,string>={'（':'）','(':')','[':']','【':'】','“':'”','「':'」','『':'』'},stack:string[]=[],parts:string[]=[];let start=0;
 for(const code of [34,39]){const quote=String.fromCharCode(code);pairs[quote]=quote;}
 for(let i=0;i<text.length;i++){
  const char=text[i];
  if((text.charCodeAt(i)===34||text.charCodeAt(i)===39)&&text.charCodeAt(i-1)===92)continue;
  if(stack.at(-1)===char)stack.pop();else if(pairs[char])stack.push(pairs[char]);
  if(!stack.length&&'；;'.includes(char)){
   const next=text.slice(i+1).trimStart();
   if(/^(?:有(?:嘉宾|企业|机构|专家|生产企业)|另(?:有|一)|一(?:方|家)|其他|部分|该(?:嘉宾|企业|机构)|企业)/.test(next)){
    parts.push(text.slice(start,i+1));start=i+1;
   }
  }
 }
 parts.push(text.slice(start));
 return parts;
}

/** Source fragments only. The tree expresses containment, never inferred causality. */
export function meetingDiagramParts(text:string,anchor?:string):{title:string|null;points:string[]}{
 if(/^(?:待核对|待确认|建议|提议|如果|除非|只有|仅当|若|即使)/.test(text.trim()))return {title:null,points:[text]};
 const parsed=topicReadingParts(text);
 if(!parsed.title)return {title:null,points:[text]};
 function split(source:string,separators:string):string[]{
  const pairs:Record<string,string>={'（':'）','(':')','[':']','【':'】','“':'”','「':'」','『':'』'},stack:string[]=[],result:string[]=[];let start=0;
  for(let i=0;i<source.length;i++){
   const char=source[i];
   if(stack.at(-1)===char)stack.pop();else if(pairs[char])stack.push(pairs[char]);
   if(!stack.length&&separators.includes(char)){const part=source.slice(start,i+1).trim();if(part)result.push(part);start=i+1;}
  }
  const last=source.slice(start).trim();if(last)result.push(last);
  return result;
 }
 // A saved bullet can mix subjects. Keep its clauses as peers when the saved
 // keyword is outside the leading clause, rather than making that clause a parent.
 const mixed=!!anchor&&!parsed.title.includes(anchor),body=mixed?text:parsed.body;
 const points=split(body,'，；;').flatMap(clause=>{
  const entries=split(clause,'、');
  // Keep short named entities and ambiguous enumerations together.
  return entries.length>1&&entries.every(entry=>Array.from(entry.replace(/[、，；;。\s]/g,'')).length>=4)?entries:[clause];
 });
 return {title:mixed?null:parsed.title,points:points.length?points:[body||text]};
}
