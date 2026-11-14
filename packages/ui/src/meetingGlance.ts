import {minutesOutline,type MeetingMapTopic} from './meetingMap';
import {splitGeneratedMeetingMetadata} from './meetingReading';
/** Display excerpts only: no model call, rewrite, inferred priority or new fact. */
export function meetingGlanceExcerpt(source:string,limit:number,preferClause=false):{text:string;clipped:boolean}{
 const plain=source.replace(/\*\*([^*]+)\*\*/g,'$1').replace(/\s+/g,' ').trim();
 if(preferClause&&!/^(?:如果|除非|只有|仅当|若|在.+(?:前提|条件)|即使)/.test(plain)){
  const first=/^([^：:，,。；;]{8,36})[：:，,。；;]/.exec(plain);
  if(first&&Array.from(first[1]).length<=limit)return {text:first[1],clipped:first[1]!==plain};
 }
 const points=Array.from(plain);
 return {text:points.slice(0,limit).join(''),clipped:points.length>limit};
}
export function meetingGlanceQualifier(source:string):{qualifier:string;body:string}{
 const found=/^(待核对|待确认|建议|提议)[:：]\s*/.exec(source);
 return found?{qualifier:found[1],body:source.slice(found[0].length)}:{qualifier:'',body:source};
}
/** Short navigation labels reuse authored keywords present in that exact topic. */
export function meetingGlanceLabels(markdown:string,topics:readonly MeetingMapTopic[]):Map<string,string>{
 const keywords:string[]=[];
 const visit=(nodes:ReturnType<typeof minutesOutline>['children'])=>nodes.forEach(node=>{
  if(['Keywords','关键词'].includes(node.title)){
   let fence:{character:string;length:number}|null=null;
   for(const line of node.body){
    const marker=/^\s*(`{3,}|~{3,})(.*)$/.exec(line);
    if(marker){if(!fence)fence={character:marker[1][0],length:marker[1].length};else if(marker[1][0]===fence.character&&marker[1].length>=fence.length&&!marker[2].trim())fence=null;continue;}
    if(fence)continue;
    for(const token of line.split(/[,，、]/)){
     const word=token.replace(/^\s*[-*+]\s+/,'').replace(/\*\*([^*]+)\*\*/g,'$1').trim();
     if(Array.from(word).length>=2&&Array.from(word).length<=12&&!keywords.includes(word))keywords.push(word);
    }
   }
  }
  visit(node.children);
 });
 visit(minutesOutline(splitGeneratedMeetingMetadata(markdown).body).children);
 const used=new Set<string>(),labels=new Map<string,string>();
 for(const topic of topics){
  const matches=keywords.filter(word=>{
   const text=topic.text.toLocaleLowerCase(),key=word.toLocaleLowerCase();let at=text.indexOf(key);
   while(at>=0){if(!/[a-z0-9]/i.test(key)||(!/[a-z0-9]/i.test(text[at-1]??'')&&!/[a-z0-9]/i.test(text[at+key.length]??'')))return true;at=text.indexOf(key,at+1);}return false;
  });
  matches.sort((a,b)=>Array.from(b).length-Array.from(a).length);
  const label=matches.find(word=>!used.has(word))??matches[0];
  if(label){used.add(label);labels.set(topic.id,label);}
 }
 return labels;
}
