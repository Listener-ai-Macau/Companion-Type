import {useId,useMemo} from 'react';
import {ArrowUpRight,CheckCheck,ListTodo,MessageCircleQuestion} from 'lucide-react';
import type {CompanionTranscriptSource} from '../../core/src/minutesSources';
import {nativeActionParts} from './actionMetadata';
import {meetingReaderModel} from './meetingReaderModel';

/** The saved decisions and arrangements, with their original qualifications. */
export function MeetingActions({markdown,onLocate,onLocateTranscript,onOpenSource,decisionQuotes,questionQuotes,actionQuotes,actionSources,reviewPending=false}:{markdown:string;onLocate:(section:string,text?:string)=>void;onLocateTranscript?:(text:string,returnId?:string)=>void;onOpenSource?:(source:CompanionTranscriptSource)=>void;decisionQuotes?:ReadonlyMap<string,string[]>;questionQuotes?:ReadonlyMap<string,string[]>;actionQuotes?:ReadonlyMap<string,string[]>;actionSources?:ReadonlyMap<string,CompanionTranscriptSource[]>;reviewPending?:boolean}){
 const sourceId=useId();
 const model=useMemo(()=>meetingReaderModel(markdown),[markdown]);
 const groups=model.groups.filter(group=>group.id!=='discussionQuestions');
 const requirements=reviewPending?model.sections.find(section=>section.title==='执行要求（待复核）'):undefined;
 const icons={decisions:CheckCheck,actions:ListTodo,questions:MessageCircleQuestion,discussionQuestions:MessageCircleQuestion};
 return <section className="meeting-actions" aria-label="决策与待办">
  {reviewPending?<p className="meeting-actions-empty"><ListTodo size={17} aria-hidden="true"/>待办复核未完成。完整纪要中的补充仍保留在正文。</p>
   :!groups.some(group=>group.id==='actions')&&<p className="meeting-actions-empty"><ListTodo size={17} aria-hidden="true"/>这份纪要没有记录明确待办</p>}
  {requirements?.items.length?<section className="meeting-action-group" aria-label={requirements.title}>
   <h3><MessageCircleQuestion size={16} aria-hidden="true"/>{requirements.title}</h3>
   <ul>{requirements.items.map((line,index)=><li key={index}>
    <div><p>{line}</p></div>
    <button type="button" className="meeting-action-source" onClick={()=>onLocateTranscript?onLocateTranscript(line):onLocate(requirements.title,line)}>{onLocateTranscript?'查看转写上下文':'查看片段'}<ArrowUpRight size={13} aria-hidden="true"/></button>
   </li>)}</ul>
  </section>:null}
  {groups.map(group=>{const Icon=icons[group.id];return <section className="meeting-action-group" key={group.id} aria-label={group.label}>
   <h3><Icon size={16} aria-hidden="true"/>{group.label}<span>{group.items.length}</span></h3>
   <ul>{group.items.map((item,index)=>{
    const decision=item.section===model.decisions?.title;
    const question=item.section===model.questions?.title;
    const action=item.section===model.actions?.title && !item.qualifier && (actionQuotes||actionSources)
      ? nativeActionParts(item.text):undefined;
    const actionBody=action?.body.trim();
    const uniqueAction=actionBody && model.actions?.items.filter(line=>nativeActionParts(line).body.trim()===actionBody).length===1;
    const quotes=decision?decisionQuotes?.get(item.text.trim()):question?questionQuotes?.get(item.text.trim())
      :uniqueAction?actionQuotes?.get(actionBody):undefined;
    const quote=!reviewPending&&onLocateTranscript
      ? quotes?.find(original=>!action||action.metadata.every(field=>original.includes(field.value.trim())))
      :undefined;
    const source=!reviewPending&&uniqueAction&&onOpenSource
      ? actionSources?.get(actionBody)?.find(original=>action?.metadata.every(field=>original.text.includes(field.value.trim())))
      :undefined;
    const returnId=`${sourceId}-${group.id}-${index}`;
    return <li key={index}>
     <div>{item.qualifier&&<span className="meeting-action-qualifier">{item.qualifier}</span>}<p>{item.body}</p></div>
     <button type="button" id={returnId} className="meeting-action-source"
       onClick={()=>{
         if(quote&&onLocateTranscript)onLocateTranscript(quote,returnId);
         else if(source&&onOpenSource)onOpenSource(source);
         else onLocate(item.section,item.text);
       }}>
       {quote?'查看转写':source?'核对原文':decision||question?'查看纪要':'原文'}<ArrowUpRight size={13} aria-hidden="true"/>
     </button>
    </li>;
   })}</ul>
  </section>;})}
 </section>;
}
