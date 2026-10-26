import {companionReviewedTranscript,companionSessionHasFinalTranscript} from '@companion-type/core';
import type {CompanionV1HostSession} from '../../core/src/companionV1';

type Preview={text:string;label?:string};
type Candidate={text:string;label?:string};

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
    ...(session.meetingNotes??[]).map(note=>({text:note.text,label:'补充'})),
    {text:reviewed,label:originalLabel},
    ...(session.transcriptText!==reviewed?[{text:session.transcriptText,label:'原始转写'}]:[]),
  ];
  const modes=session.meetingMode==='onlineLive'?['onlineLive','offlineStore']as const:['offlineStore','onlineLive']as const;
  for(const mode of modes){
    const result=session.minutesByMode?.[mode];
    if(result?.markdown)candidates.push({text:result.markdown,label:result.source==='userAuthored'?'手写清单'
      :result.quality==='draft'?'整理草稿':mode==='onlineLive'?'在线整理':'整理'});
  }
  if(session.minutes?.markdown)candidates.push({text:session.minutes.markdown,
    label:String(session.minutes.source)==='userAuthored'?'手写清单':session.minutes.quality==='draft'?'整理草稿':'整理'});
  if(session.organization?.folder)candidates.push({text:session.organization.folder,label:'文件夹'});
  for(const tag of session.organization?.tags??[])candidates.push({text:tag,label:'标签'});
  const match=candidates.find(candidate=>candidate.text.toLocaleLowerCase().includes(query));
  // A title match already appears in the card heading. Other unusual matches
  // spanning indexed fields retain the ordinary transcript preview.
  return match?{text:excerpt(match.text,query),label:match.label}:{text:excerpt(reviewed),label:originalLabel};
}
