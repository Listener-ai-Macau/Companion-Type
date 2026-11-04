import type {ReactNode} from 'react';
import {Clock3,UserRound} from 'lucide-react';
import {mobileActionCards} from './mobileActionReading';
import {readableCalendarTime} from '../../../packages/ui/src/calendarTime';
export function MobileActionCards({text,fallback}:{text:string;fallback:ReactNode}){
 const items=mobileActionCards(text);
 if(!items)return <>{fallback}</>;
 if(!items.length)return <p className="hint">这份纪要尚未提取到明确的行动事项。</p>;
 return <div className="mobile-action-cards">{items.map((item,index)=><article key={index} className="mobile-action-card">
  <div className="mobile-action-top"><span>事项</span><small>{item.checked?'已标记完成':'待核对'}</small></div>
  <p>{item.body}</p><div className="mobile-action-fields">
   <span><UserRound size={13} aria-hidden="true"/>{item.owner?`负责人：${item.owner}`:'负责人待确认'}</span>
   <span><Clock3 size={13} aria-hidden="true"/>{item.due?`时间：${readableCalendarTime(item.due)}`:'时间未明确'}</span>
  </div>
 </article>)}</div>;
}
