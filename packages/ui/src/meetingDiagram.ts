import {topicReadingParts} from './MeetingTopic';

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
