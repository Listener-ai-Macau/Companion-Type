/** Local listening preferences; native content/session identities, no audio. */
export const playbackSpeeds=[0.5,0.75,1,1.25,1.5,2];
export interface PlaybackMemory {version:1;position:number;duration:number;speed:number;completed:boolean}
interface ReadMemory {value:PlaybackMemory|null;failed:boolean;generation:string;epoch:string}
const key=(identity?:string)=>identity&&/^[a-f0-9]{64}$/.test(identity)?`companion.playback.v1:${identity}`:null;
const sessionKey=(id?:string)=>id&&id.length<=256?`companion.playback.v2:${encodeURIComponent(id)}`:null;
const RESET='companion.playback.reset';
const result=(value:PlaybackMemory|null,failed=false,generation='',epoch=''):ReadMemory=>({value,failed,generation,epoch});
export function loadPlaybackMemory(identity?:string,sessionId?:string):ReadMemory {
 const id=key(identity);if(!id)return result(null);
 try {
  const storage=window.localStorage;const epoch=storage.getItem(RESET)??'';const scoped=sessionKey(sessionId);
  const stored=scoped?storage.getItem(scoped):null;let value:PlaybackMemory;let generation='';
  if(stored!==null){const record=JSON.parse(stored);generation=record.generation??'';
   if(record.version!==2||record.identity!==identity)return result(null,false,generation,epoch);value=record.data;
  }else {if(scoped&&epoch)return result(null,false,generation,epoch);const raw=storage.getItem(id);if(!raw)return result(null,false,generation,epoch);value=JSON.parse(raw);}
  if(value?.version!==1||!Number.isFinite(value.position)||!Number.isFinite(value.duration)||value.duration<=0
    ||value.position<0||value.position>value.duration||!playbackSpeeds.includes(value.speed)||typeof value.completed!=='boolean')return result(null,false,generation,epoch);
  return result(value,false,generation,epoch);
 }catch{return result(null,true);}
}
export function savePlaybackMemory(identity:string|undefined,value:PlaybackMemory,sessionId?:string,generation='',epoch=''):boolean {
 const id=key(identity);if(!id)return true;
 try {
  const storage=window.localStorage;
  // A player unmounting after a successful cleanup must not resurrect progress.
  if((storage.getItem(RESET)??'')!==epoch)return true;
  const scoped=sessionKey(sessionId);
  if(scoped){let current='';try{current=JSON.parse(storage.getItem(scoped)??'null')?.generation??'';}catch{/* repair malformed preference */}
   if(current!==generation)return true;
   storage.setItem(scoped,JSON.stringify({version:2,identity,generation,data:value}));storage.removeItem(id);
  }else storage.setItem(id,JSON.stringify(value));return true;
 }catch{return false;}
}
/** A position-free marker blocks legacy fallback and writes from old players;
 * a fresh explicit listen can save a new position in the new generation. */
export function clearSessionPlaybackMemory(sessionId:string):boolean {
 const scoped=sessionKey(sessionId);if(!scoped)return false;
 try {const storage=window.localStorage;const old=storage.getItem(scoped);
  storage.setItem(scoped,JSON.stringify({version:2,cleared:true,generation:crypto.randomUUID()}));
  if(old){try{const legacy=key(JSON.parse(old).identity);if(legacy)storage.removeItem(legacy);}catch{/* cleared marker remains authoritative */}}
  return true;
 }catch{return false;}
}
export function clearPlaybackMemory():boolean {
 try {const storage=window.localStorage;storage.setItem(RESET,crypto.randomUUID());
  for(let i=storage.length-1;i>=0;i--){const id=storage.key(i);if(id?.startsWith('companion.playback.v1:')||id?.startsWith('companion.playback.v2:'))storage.removeItem(id);}return true;
 }catch{return false;}
}
