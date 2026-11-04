import type {CompanionCalendarCopy,CompanionCalendarSlotCopy} from '@companion-type/core';
import {readableCalendarTime} from './calendarTime';

/** Do not guess a time block from a title, position, or mismatched receipt. */
export function savedSlotFor(copy:CompanionCalendarCopy,uid:string,slots:CompanionCalendarSlotCopy[]|undefined){
  if(copy.entries.filter(e=>e.uid===uid).length!==1)return undefined;
  const matches=(slots??[]).filter(s=>s.privacyEpoch===copy.privacyEpoch&&s.meetingMode===copy.meetingMode&&s.contentHash===copy.contentHash);
  if(matches.length!==1)return undefined;
  const selection=matches[0].selections.filter(s=>s.uid===uid);
  return selection.length===1?selection[0].slot:undefined;
}
export const readableSlot=(slot:{start:string;end:string})=>`${readableCalendarTime(slot.start)} 至 ${readableCalendarTime(slot.end)}`;
