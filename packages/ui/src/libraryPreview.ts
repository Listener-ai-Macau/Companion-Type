import {nativeActionParts} from './actionMetadata';
import {readableCalendarTime} from './calendarTime';
import {companionReviewedTranscript,companionSessionHasFinalTranscript} from '@companion-type/core';
import type {CompanionV1HostSession} from '../../core/src/companionV1';

type Preview={text:string;label?:string;target?:'source'|'result'};

function readablePreview(text:string):string {
  return text.split(/\r?\n/).map(line=>{
    const parts=nativeActionParts(line);
    if(!parts.metadata.length)return line;
    return parts.body+"（"+parts.metadata.map(field=>`${field.key==='due'?'注明时间':'负责人'}：${field.key==='due'?readableCalendarTime(field.value):field.value}`).join("；")+"）";
  }).join("\n");
}
type Candidate={text:string;label?:string;target?:'result'};

function excerpt(text:string,query=''):string {
  const compact=(value:string)=>value.replace(/\s+/g,' ').trim();
  const folded=text.toLocaleLowerCase();
  const match=query?folded.indexOf(query):-1;
  let offset=match;
  // Locale case conversion can expand a character. Convert the match back to
  // an original-text offset before clipping; never slice inside a surrogate.
  if(match>=0&&folded.length!==text.length){
    let raw=0,lower=0;
    for(const char of text){if(lower>=match)break;raw+=char.length;lower+=char.toLocaleLowerCase().length;}
    offset=raw;
  }
  if(offset<0){const chars=Array.from(compact(text));return chars.slice(0,96).join('')+(chars.length>96?'…':'');}
  if(text.includes('\n')){
    const start=text.lastIndexOf('\n',offset-1)+1,end=text.indexOf('\n',offset);
    const line=text.slice(start,end<0?text.length:end).trim();
    if(line.toLocaleLowerCase().includes(query)){
      const plain=line.replace(/^(?:[-*+]\s+(?:\[[ xX]\]\s+)?|#{1,6}\s+)/,'');
      // Prefer the matching line itself over unrelated adjacent tasks. Keep
      // literal formatting when it is what the user searched for.
      return excerpt(plain.toLocaleLowerCase().includes(query)?plain:line,query);
    }
  }
  const chars=Array.from(text),position=Array.from(text.slice(0,offset)).length,start=Math.max(0,position-24);
  return(start?'…':'')+compact(chars.slice(start,start+96).join(''))+(start+96<chars.length?'…':'');
}

/** Reading-only projection. The existing full-text filter remains authoritative:
 * no search result, source text, saved document or timestamp is created here. */
export function libraryPreview(session:CompanionV1HostSession,rawQuery:string):Preview {
  const reviewed=companionReviewedTranscript(session);
  const originalLabel=companionSessionHasFinalTranscript(session)?undefined:'片段';
  const query=rawQuery.trim().toLocaleLowerCase();
  if(!query)return{text:excerpt(reviewed),label:originalLabel};
  const candidates:Candidate[]=[
    ...(session.meetingNotes??[]).flatMap(note=>[{text:note.text,label:note.kind==='followup'?'人工跟进':'补充'},...(note.references??[]).map(reference=>({text:reference.name+'\n'+reference.quote,label:'人工引用'}))]),
    {text:reviewed,label:originalLabel},
    ...(session.transcriptText!==reviewed?[{text:session.transcriptText,label:'原始转写'}]:[]),
  ];
  const sourceCandidates=[...candidates];
  const modes=session.meetingMode==='onlineLive'?['onlineLive','offlineStore']as const:['offlineStore','onlineLive']as const;
  for(const mode of modes){
    const result=session.minutesByMode?.[mode];
    if(result?.markdown)candidates.push({text:result.markdown,target:result.source==='userAuthored'?'result':undefined,label:result.source==='userAuthored'?'手写清单'
      :result.quality==='draft'?'整理草稿':mode==='onlineLive'?'在线整理':'整理'});
  }
  if(session.minutes?.markdown)candidates.push({text:session.minutes.markdown,target:String(session.minutes.source)==='userAuthored'?'result':undefined,
    label:String(session.minutes.source)==='userAuthored'?'手写清单':session.minutes.quality==='draft'?'整理草稿':'整理'});
  if(session.organization?.folder)candidates.push({text:session.organization.folder,label:'文件夹'});
  for(const tag of session.organization?.tags??[])candidates.push({text:tag,label:'标签'});
  // A saved handwritten list is the authored destination, even when its words
  // also occur in the source. Other source/note matches keep their old route.
  const match=candidates.find(candidate=>candidate.target==='result'&&candidate.text.toLocaleLowerCase().includes(query))
    ??candidates.find(candidate=>candidate.text.toLocaleLowerCase().includes(query));
  // A title match already appears in the card heading. Other unusual matches
  // spanning indexed fields retain the ordinary transcript preview.
  const shown=match&&/^(?:手写清单|整理草稿|在线整理|整理)$/.test(match.label??'')?readablePreview(match.text):match?.text;
  // Keep literal matches discoverable when the query itself names stored syntax.
  return match?{text:excerpt(shown?.toLocaleLowerCase().includes(query)?shown:match.text,query),label:match.label,target:match.target??(sourceCandidates.includes(match)?'source':undefined)}:{text:excerpt(reviewed),label:originalLabel};
}

/** Resume existing saved work; never fabricate an edit date or mutate history. */
export function latestSavedResult(sessions:CompanionV1HostSession[]) {
  let latest:{session:CompanionV1HostSession;at:string;manual:boolean}|null=null;
  for(const session of sessions){
    if(session.organization?.trashedAt||session.status==='recording')continue;
    const mode=session.meetingMode;
    const result=session.minutesByMode?.[mode]??session.minutes;
    if(!result?.markdown.trim())continue;
    // Native manual saves use epoch-millisecond strings; provider results and
    // exportedAt use ISO. Decode both existing representations, without
    // rewriting stored data or inventing a new edit timestamp.
    const dates=[result.generatedAt,session.exportedAt].flatMap(value=>{
      if(!value)return[];
      const ms=/^\d+$/.test(value)?Number(value):Date.parse(value);
      return Number.isFinite(ms)&&Number.isFinite(new Date(ms).getTime())?[new Date(ms).toISOString()]:[];
    });
    const at=dates.sort((a,b)=>Date.parse(b)-Date.parse(a))[0];
    if(at&&(!latest||Date.parse(at)>Date.parse(latest.at)))latest={session,at,manual:String(result.source)==='userAuthored'};
  }
  return latest;
}
