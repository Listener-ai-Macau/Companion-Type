/** Read-only view over saved items. Never derives commitments, dates or people. */
import {nativeActionParts} from './actionMetadata';
import {readableCalendarTime} from './calendarTime';
export type ReviewAction={id:string;text:string;completed:boolean;owner:string|null;due:string|null;needsReview:boolean};
export type ActionReviewFilter={query:string;owner:string;status:'all'|'open'|'done';missing:'all'|'owner'|'time'|'review'};
export const emptyActionReviewFilter:ActionReviewFilter={query:'',owner:'',status:'all',missing:'all'};
const searchable=(value:string)=>value.normalize('NFKC').toLowerCase();
export function savedActionReview(id:string,text:string,completed:boolean):ReviewAction{
 const parsed=nativeActionParts(text),needsReview=/^待核对[：:]\s*/.test(parsed.body);
 const due=parsed.metadata.find(field=>field.key==='due')?.value;
 return {id,text:needsReview?parsed.body.replace(/^待核对[：:]\s*/,''):parsed.body,completed,needsReview,
  owner:parsed.metadata.find(field=>field.key==='owner')?.value??null,due:due?readableCalendarTime(due):null};
}
export function actionReviewMatches(item:ReviewAction,filter:ActionReviewFilter):boolean{
 if(filter.owner&&item.owner?.trim()!==filter.owner)return false;
 if(filter.status==='open'&&item.completed||filter.status==='done'&&!item.completed)return false;
 if(filter.missing==='owner'&&item.owner?.trim()||filter.missing==='time'&&item.due?.trim()||filter.missing==='review'&&!item.needsReview)return false;
 const term=searchable(filter.query.trim());
 return !term||searchable([item.text,item.owner??'',item.due??''].join('\n')).includes(term);
}
export function actionReviewActive(filter:ActionReviewFilter):boolean{return !!(filter.query.trim()||filter.owner||filter.status!=='all'||filter.missing!=='all');}
export function actionFollowupText(items:readonly ReviewAction[],title:string):string{
 if(!items.length)return '';
 const groups=[{title:'待跟进',test:(item:ReviewAction)=>!item.completed&&!item.needsReview},{title:'待核对事项',test:(item:ReviewAction)=>!item.completed&&item.needsReview},{title:'已标记完成',test:(item:ReviewAction)=>item.completed}];
 return ['会议跟进草稿'+(title.trim()?' · '+title.trim():''),'根据当前筛选的已保存事项整理，请核对后使用。',...groups.flatMap(group=>{
  const rows=items.filter(group.test);if(!rows.length)return [];
  return [group.title,...rows.map((item,index)=>`${index+1}. ${item.text}\n   负责人：${item.owner?.trim()?item.owner:'待确认'}；时间：${item.due?.trim()?item.due:'未明确'}${item.needsReview&&item.completed?'\n   此项仍保留待核对标记。':''}`)];
 })].join('\n\n');
}
