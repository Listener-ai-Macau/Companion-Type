import type {CompanionV1HostSession} from '../../core/src/companionV1';

// Calendar filters follow the user's local day, not UTC or an inferred file/ID
// date. Unknown recording times remain unknown.
export function recordingLocalDay(session:Pick<CompanionV1HostSession,'startedAt'>):string|null {
 if(!session.startedAt)return null;
 const date=new Date(session.startedAt);
 if(!Number.isFinite(date.getTime()))return null;
 return `${String(date.getFullYear()).padStart(4,'0')}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
}
export function recordingInDates(session:Pick<CompanionV1HostSession,'startedAt'>,from='',to=''):boolean {
 if(!from&&!to)return true;
 if(from&&to&&from>to)return false;
 const day=recordingLocalDay(session);
 return day!==null&&(!from||day>=from)&&(!to||day<=to);
}
