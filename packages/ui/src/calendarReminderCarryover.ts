import type {CompanionV1HostSession,CompanionV1MeetingMode} from '@companion-type/core';
import type {CalendarExportItem,CalendarReminderSelection} from './CalendarExportItems';
import {nativeActionParts} from './actionMetadata';

export type SavedCalendarReminders={fileName:string;selections:CalendarReminderSelection[]};

/** Only the row the user explicitly chose to edit can inherit a relative rule. */
export function carryRelativeReminderAfterSingleDeadlineEdit(
  selections:CalendarReminderSelection[]|undefined,
  change:{index:number;before:CalendarExportItem[]}|undefined,
  after:CalendarExportItem[],
):{selections:CalendarReminderSelection[]|undefined;carried:boolean;carriedKind?:'before'|'none';suggestedAbsolute?:{uid:string;at:string}} {
  const unchanged={selections,carried:false};
  if(!selections||!change||change.before.length!==after.length||change.index<0||change.index>=after.length)return unchanged;
  const old=change.before[change.index],now=after[change.index];
  if(!old.uid||!now.uid||old.uid===now.uid||!['timed','allDay'].includes(old.status)||!['timed','allDay'].includes(now.status)||!old.deadline||!now.deadline||old.deadline===now.deadline)return unchanged;
  if(change.before.filter(i=>i.uid===old.uid).length!==1||after.filter(i=>i.uid===now.uid).length!==1||selections.filter(s=>s.uid===old.uid).length!==1||selections.some(s=>s.uid===now.uid))return unchanged;
  if(change.before.some((item,i)=>i!==change.index&&(item.uid!==after[i].uid||item.text!==after[i].text||item.deadline!==after[i].deadline||item.status!==after[i].status)))return unchanged;
  const prior=nativeActionParts(old.text),current=nativeActionParts(now.text);
  const priorDue=prior.metadata.filter(m=>m.key==='due'),currentDue=current.metadata.filter(m=>m.key==='due');
  if(prior.body!==current.body||priorDue.length!==1||currentDue.length!==1||priorDue[0].value.trim()!==old.deadline||currentDue[0].value.trim()!==now.deadline||
    JSON.stringify(prior.metadata.filter(m=>m.key!=='due'))!==JSON.stringify(current.metadata.filter(m=>m.key!=='due')))return unchanged;
  const selected=selections.find(s=>s.uid===old.uid)!;
  // An absolute reminder may no longer be appropriate after changing the
  // deadline. Offer the exact prior instant; never apply or shift it silently.
  if(selected.reminder.kind==='at')return {...unchanged,suggestedAbsolute:{uid:now.uid,at:selected.reminder.at}};
  if(selected.reminder.kind!=='before'&&selected.reminder.kind!=='none')return unchanged;
  if(selected.reminder.kind==='before'&&(old.status!=='timed'||now.status!=='timed'))return unchanged;
  const newUid=now.uid;
  return {selections:selections.map(s=>s===selected?{uid:newUid,reminder:{...s.reminder}}:s),carried:true,carriedKind:selected.reminder.kind};
}

/** Read only an actual saved-file receipt in this record/mode/privacy epoch. */
export function lastSavedCalendarReminders(session:CompanionV1HostSession,mode:CompanionV1MeetingMode):SavedCalendarReminders|undefined {
  const copy=session.calendarCopies?.find(c=>c.meetingMode===mode&&c.privacyEpoch===(session.calendarCopyEpoch??0));
  if(!copy)return undefined;
  const selections:CalendarReminderSelection[]=[];
  for(const entry of copy.entries){
    if(!entry.uid)continue;
    if(entry.reminderAt&&entry.reminderMinutes==null)selections.push({uid:entry.uid,reminder:{kind:'at',at:entry.reminderAt}});
    else if(!entry.reminderAt&&entry.reminderMinutes==null)selections.push({uid:entry.uid,reminder:{kind:'none'}});
    else if(!entry.reminderAt&&[0,30,60,1440].includes(entry.reminderMinutes!))selections.push({uid:entry.uid,reminder:{kind:'before',minutes:entry.reminderMinutes!}});
  }
  return {fileName:copy.fileName,selections};
}

/** No title/index guessing: a changed date/text gets a new native UID. */
export function retainCalendarReminders(saved:SavedCalendarReminders|undefined,items:CalendarExportItem[]){
  if(!saved)return undefined;
  const included=items.filter(item=>item.status==='timed'||item.status==='allDay');
  const counts=(ids:(string|undefined)[])=>ids.reduce((map,uid)=>uid?map.set(uid,(map.get(uid)??0)+1):map,new Map<string,number>());
  const oldCounts=counts(saved.selections.map(s=>s.uid)),newCounts=counts(included.map(i=>i.uid));
  const selections=saved.selections.filter(s=>oldCounts.get(s.uid)===1&&newCounts.get(s.uid)===1)
    .map(s=>({...s,reminder:{...s.reminder}}));
  const retained=new Set(selections.map(s=>s.uid));
  const notCarriedAlarms=saved.selections.filter(s=>s.reminder.kind!=='none'&&!retained.has(s.uid)).length;
  return {fileName:saved.fileName,selections,notCarriedAlarms};
}

