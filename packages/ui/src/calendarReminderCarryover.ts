import type {CompanionV1HostSession,CompanionV1MeetingMode} from '@companion-type/core';
import type {CalendarExportItem,CalendarReminderSelection} from './CalendarExportItems';

export type SavedCalendarReminders={fileName:string;selections:CalendarReminderSelection[]};

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

