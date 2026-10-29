import type {CompanionV1HostSession,CompanionV1MeetingMode} from '@companion-type/core';
import type {CalendarExportItem,CalendarSlotSelection} from './CalendarExportItems';

/** Only the latest actually saved receipt for this mode and privacy epoch. */
export function retainCalendarSlots(session:CompanionV1HostSession,mode:CompanionV1MeetingMode,items:CalendarExportItem[]){
  const copy=session.calendarCopies?.find(c=>c.meetingMode===mode&&c.privacyEpoch===(session.calendarCopyEpoch??0));
  if(!copy)return undefined;
  const matches=(session.calendarSlotCopies??[]).filter(s=>s.meetingMode===mode&&s.privacyEpoch===copy.privacyEpoch&&s.contentHash===copy.contentHash);
  if(matches.length!==1)return undefined;
  const source=matches[0].selections;
  const included=items.filter(item=>item.status==='timed'||item.status==='allDay');
  const counts=(ids:(string|undefined)[])=>ids.reduce((map,uid)=>uid?map.set(uid,(map.get(uid)??0)+1):map,new Map<string,number>());
  const oldCounts=counts(source.map(s=>s.uid)),newCounts=counts(included.map(i=>i.uid));
  const selections:CalendarSlotSelection[]=source.filter(s=>oldCounts.get(s.uid)===1&&newCounts.get(s.uid)===1).map(s=>({uid:s.uid,slot:{...s.slot}}));
  return {fileName:copy.fileName,selections,notCarried:source.length-selections.length};
}
