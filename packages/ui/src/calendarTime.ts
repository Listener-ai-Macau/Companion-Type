export interface CalendarTimeDraft {
  expected:string;date:string;time:string;timed:boolean;zone:'local'|'offset';offset:string;before?:boolean;
}
export type CalendarTimeValue={ok:true;value:string;label:string}|{ok:false;error:string};
export function validCalendarDate(value:string):boolean {
  const m=value.match(/^(\d{4})-(\d{2})-(\d{2})$/);if(!m)return false;
  const y=Number(m[1]),month=Number(m[2]),day=Number(m[3]);
  const days=[31,y%4===0&&(y%100!==0||y%400===0)?29:28,31,30,31,30,31,31,30,31,30,31];
  return y>=1&&month>=1&&month<=12&&day>=1&&day<=days[month-1];
}
/** Reading only: keep the recorded wall clock and explicit UTC offset. Never
 * resolve prose or silently convert a saved arrangement to this computer's zone. */
export function readableCalendarTime(value:string):string {
  if(value.endsWith('前')){const base=value.slice(0,-1),readable=readableCalendarTime(base);if(readable!==base)return readable.includes('（UTC')?readable.replace('（UTC','前（UTC'):`${readable}前`;return value;}
  if(validCalendarDate(value))return `${value.slice(0,4)}年${Number(value.slice(5,7))}月${Number(value.slice(8,10))}日`;
  const m=value.match(/^(\d{4}-\d{2}-\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$/);
  if(!m||!validCalendarDate(m[1])||Number(m[2])>23||Number(m[3])>59||Number(m[4])>59)return value;
  const zone=/^[Zz]$/.test(m[6])?'+00:00':m[6];
  if(zone==='-00:00'||Number(zone.slice(1,3))>23||Number(zone.slice(4))>59)return value;
  const seconds=Number(m[4])||Number(m[5]??0)?`:${m[4]}${m[5]??''}`:'';
  return `${readableCalendarTime(m[1])} ${m[2]}:${m[3]}${seconds}（UTC${zone}）`;
}
export function seedCalendarTime(value:string):CalendarTimeDraft {
  // Prefill only a complete explicit year/month/day (optionally24-hour time).
  // It is a visible draft, not a saved conversion. Relative/partial dates,
  // alternatives, conditions and invalid dates are never resolved here.
  const before=value.endsWith('前'),base=before?value.slice(0,-1):value;
  const chinese=base.match(/^([0-9]{4})年\s*([0-9]{1,2})月\s*([0-9]{1,2})日(?:\s*([0-9]{1,2}):([0-9]{2}))?$/);
  if(chinese){
    const date=`${chinese[1]}-${chinese[2].padStart(2,'0')}-${chinese[3].padStart(2,'0')}`;
    const time=chinese[4]===undefined?'':`${chinese[4].padStart(2,'0')}:${chinese[5]}`;
    if(validCalendarDate(date)&&(!time||(Number(chinese[4])<=23&&Number(chinese[5])<=59))){
      return{expected:value,date,time,timed:!!time,zone:'local',offset:'+00:00',before};
    }
  }
  const m=base.match(/^(\d{4}-\d{2}-\d{2})(?:[Tt ](\d{2}:\d{2})(?::00(?:\.0+)?)?(?:[Zz]|[+-]\d{2}:\d{2})?)?$/);
  const offset=base.match(/(?:[Zz]|[+-]\d{2}:\d{2})$/)?.[0];
  return{expected:value,date:m&&validCalendarDate(m[1])?m[1]:'',time:m?.[2]??'',timed:!/^\d{4}-\d{2}-\d{2}$/.test(base),zone:offset?'offset':'local',offset:offset?(/[Zz]/.test(offset)?'+00:00':offset):'+00:00',before};
}
const pad=(n:number)=>String(n).padStart(2,'0');
function sameLocal(date:Date,y:number,m:number,d:number,h:number,min:number):boolean {
  return date.getFullYear()===y&&date.getMonth()===m-1&&date.getDate()===d&&date.getHours()===h&&date.getMinutes()===min;
}
/** Only called for an explicitly visible user confirmation. Free text is never
 * parsed as a relative date or silently assigned the computer's timezone. */
export function confirmedCalendarTime(draft:CalendarTimeDraft):CalendarTimeValue {
  if(!validCalendarDate(draft.date))return{ok:false,error:'请选择有效日期。'};
  if(!draft.timed)return{ok:true,value:draft.date+(draft.before?'前':''),label:`${draft.date}${draft.before?'前':''}（仅日期）`};
  const clock=draft.time.match(/^(\d{2}):(\d{2})$/);if(!clock||Number(clock[1])>23||Number(clock[2])>59)return{ok:false,error:'请选择有效时间。'};
  const[y,m,d]=draft.date.split('-').map(Number),h=Number(clock[1]),min=Number(clock[2]);let offset=draft.offset;
  if(draft.zone==='local'){
    const date=new Date(0);date.setFullYear(y,m-1,d);date.setHours(h,min,0,0);
    if(!sameLocal(date,y,m,d,h,min))return{ok:false,error:'这个时刻在本机时区不存在，请选择其他时间或明确的 UTC 偏移。'};
    // Reject repeated local times instead of silently choosing either side of
    // a daylight-saving transition. An explicit offset remains available.
    for(let delta=-180;delta<=180;delta+=15){
      if(delta&&sameLocal(new Date(date.getTime()+delta*60_000),y,m,d,h,min))return{ok:false,error:'这个本机时刻对应两个时间，请选择明确的 UTC 偏移后确认。'};
    }
    const minutes=-date.getTimezoneOffset(),abs=Math.abs(minutes);offset=`${minutes>=0?'+':'-'}${pad(Math.floor(abs/60))}:${pad(abs%60)}`;
    if(Date.parse(`${draft.date}T${draft.time}:00${offset}`)!==date.getTime())return{ok:false,error:'本机时区不能明确表示这个时刻，请选择明确的 UTC 偏移。'};
  }
  const zone=offset.match(/^([+-])(\d{2}):(\d{2})$/);
  if(!zone||Number(zone[2])>23||Number(zone[3])>59||offset==='-00:00')return{ok:false,error:'请填写明确的 UTC 偏移，如 +08:00；零时区使用 +00:00。'};
  const value=`${draft.date}T${draft.time}:00${offset}`,instant=new Date(value);
  if(!Number.isFinite(instant.getTime())||instant.getUTCFullYear()<1||instant.getUTCFullYear()>9999)return{ok:false,error:'这个时刻超出了日历可用范围。'};
  return{ok:true,value:value+(draft.before?'前':''),label:`${draft.date} ${draft.time}${draft.before?'前':''}（UTC${offset}）`};
}
