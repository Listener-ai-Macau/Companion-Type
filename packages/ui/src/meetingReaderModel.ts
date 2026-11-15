import {meetingMapModel,type MeetingMapSection} from './meetingMap';
import {meetingGlanceQualifier} from './meetingGlance';

export type MeetingReaderItem={text:string;body:string;qualifier:string;section:string};
export type MeetingReaderGroup={id:'decisions'|'questions'|'actions';label:string;items:MeetingReaderItem[]};

/** Presentation of saved content only. No new summary, suggestion, or service call. */
export function meetingReaderModel(markdown:string){
 const model=meetingMapModel(markdown);
 const items=(section?:MeetingMapSection):MeetingReaderItem[]=>(section?.items??[]).map(text=>{
  const parsed=meetingGlanceQualifier(text);
  return {text,body:parsed.body,qualifier:parsed.qualifier||(/(?:需|待)(?:核对|确认)/.test(section!.title)?'待核对':''),section:section!.title};
 });
 const decisions=items(model.decisions),pending=decisions.filter(item=>item.qualifier);
 const groups:MeetingReaderGroup[]=[
  {id:'decisions',label:'讨论结论',items:decisions.filter(item=>!item.qualifier)},
  {id:'questions',label:'待确认',items:[...items(model.questions),...pending]},
  {id:'actions',label:'后续安排',items:items(model.actions)},
 ];
 return {...model,groups:groups.filter(group=>group.items.length)};
}
