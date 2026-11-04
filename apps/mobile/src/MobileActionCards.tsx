import type {ReactNode} from 'react';
import {Clock3,UserRound,Pencil,Search} from 'lucide-react';
import {mobileActionCards} from './mobileActionReading';
import {readableCalendarTime} from '../../../packages/ui/src/calendarTime';
import {mobileActionId,mobileActionButtonId,type MobileActionTarget} from './mobileActionEditing';
export function MobileActionCards({text,fallback,sectionTitle='Action Items',sectionOccurrence=0,itemOffset=0,manualIds=[],busy=false,onEdit,onToggle,onFind}:{text:string;fallback:ReactNode;sectionTitle?:string;sectionOccurrence?:number;itemOffset?:number;manualIds?:readonly string[];busy?:boolean;onEdit?:(target:MobileActionTarget)=>void;onToggle?:(target:MobileActionTarget,completed:boolean)=>void;onFind?:(target:MobileActionTarget,body:string)=>void}){
 const items=mobileActionCards(text);
 if(!items)return <>{fallback}</>;
 if(!items.length)return <p className="hint">这份纪要尚未提取到明确的行动事项。</p>;
 return <div className="mobile-action-cards">{items.map((item,index)=>{const target={sectionTitle,sectionOccurrence,itemIndex:itemOffset+index,original:item.original};return <article key={index} className="mobile-action-card">
  <div className="mobile-action-top">{onToggle?<label className="mobile-action-check"><input type="checkbox" checked={item.checked} disabled={busy} aria-label={`${item.checked?'恢复为待办':'标记完成'}：${item.body}`} onChange={event=>onToggle(target,event.target.checked)}/><span>事项</span></label>:<span>事项</span>}<small>{item.checked?'已标记完成':item.pending?'待核对':'待跟进'}{manualIds.includes(mobileActionId(target))?' · 人工修改':''}</small></div>
  <p>{item.body}</p><div className="mobile-action-fields">
   <span><UserRound size={13} aria-hidden="true"/>{item.owner?`负责人：${item.owner}`:'负责人待确认'}</span>
   <span><Clock3 size={13} aria-hidden="true"/>{item.due?`时间：${readableCalendarTime(item.due)}`:'时间未明确'}</span>
  </div>
  {(onEdit||onFind)&&<div className="mobile-action-tools">{onFind&&<button type="button" disabled={busy} onClick={()=>onFind(target,item.body)}><Search size={13}/>查找原文核对</button>}{onEdit&&<button type="button" id={mobileActionButtonId(target)} disabled={busy} onClick={()=>onEdit(target)}><Pencil size={13}/>修改事项</button>}</div>}
 </article>;})}</div>;
}
