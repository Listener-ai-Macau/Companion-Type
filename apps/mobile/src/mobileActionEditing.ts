import {nativeActionParts} from '../../../packages/ui/src/actionMetadata';
export type MobileActionTarget={sectionTitle:string;sectionOccurrence:number;itemIndex:number;original:string};
export type MobileActionDraft={body:string;owner:string;due:string;completed:boolean;confirmed:boolean};
export function mobileActionId(target:Pick<MobileActionTarget,'sectionTitle'|'sectionOccurrence'|'itemIndex'>){return JSON.stringify([target.sectionTitle,target.sectionOccurrence,target.itemIndex]);}
export function mobileActionButtonId(target:Pick<MobileActionTarget,'sectionTitle'|'sectionOccurrence'|'itemIndex'>){return 'mobile-action-'+encodeURIComponent(mobileActionId(target));}
export function actionDraft(original:string):MobileActionDraft {
 const completed=/^\[x\]\s+/i.test(original),value=original.replace(/^\[[ xX]\]\s+/,''),parts=nativeActionParts(value);
 return {body:parts.body.replace(/^待核对[：:]\s*/,''),owner:parts.metadata.find(x=>x.key==='owner')?.value??'',due:parts.metadata.find(x=>x.key==='due')?.value??'',completed,confirmed:!/^待核对[：:]\s*/.test(parts.body)};
}
/** Replace only the explicitly selected list line. Duplicate tasks and CRLF remain unambiguous. */
export function editMobileAction(markdown:string,target:MobileActionTarget,draft:MobileActionDraft):string {
 const body=draft.body.trim(),owner=draft.owner.trim(),due=draft.due.trim();
 if(!body||body.length>3000||/[\r\n]/.test(body))throw new Error('事项内容请填写为一行，最多 3000 字。');
 if(owner.length>80||due.length>120||/[\r\n()]/.test(owner+due))throw new Error('负责人和时间请用单行文字，不要使用英文括号。');
 const suffix=[owner?`owner: ${owner}`:'',due?`due: ${due}`:''].filter(Boolean).join(', ');
 const plain=(draft.confirmed?'':'待核对：')+body+(suffix?` (${suffix})`:'');
 const roundTrip=nativeActionParts(plain);
 if((roundTrip.metadata.find(x=>x.key==='owner')?.value??'')!==owner||(roundTrip.metadata.find(x=>x.key==='due')?.value??'')!==due)throw new Error('负责人或时间中的标点有歧义，请改用中文标点。');
 let fence:{char:string;length:number}|null=null,current:string|null=null,occurrence=-1,item=-1;
 const counts=new Map<string,number>();
 for(const match of markdown.matchAll(/[^\r\n]*(?:\r\n|\n|\r|$)/g)){
  if(!match[0])continue;const raw=match[0].replace(/[\r\n]+$/,''),marker=/^\s*(`{3,}|~{3,})(.*)$/.exec(raw);
  if(marker){if(!fence)fence={char:marker[1][0],length:marker[1].length};else if(marker[1][0]===fence.char&&marker[1].length>=fence.length&&!marker[2].trim())fence=null;continue;}
  if(fence)continue;
  const heading=/^##\s+(.+?)\s*$/.exec(raw);
  if(heading){current=heading[1];occurrence=counts.get(current)??0;counts.set(current,occurrence+1);item=-1;continue;}
  if(current!==target.sectionTitle||occurrence!==target.sectionOccurrence)continue;
  const bullet=/^([-*+]\s+)(\S.*)$/.exec(raw);if(!bullet||/^None captured[.。]?$/i.test(bullet[2]))continue;item++;
  if(item!==target.itemIndex)continue;
  if(bullet[2]!==target.original)throw new Error('当前事项已变化，请重新打开后核对，尚未覆盖任何内容。');
  const start=match.index!+bullet[1].length,end=match.index!+raw.length;
  return markdown.slice(0,start)+`[${draft.completed?'x':' '}] `+plain+markdown.slice(end);
 }
 throw new Error('当前事项位置已变化，请重新打开后核对。');
}
