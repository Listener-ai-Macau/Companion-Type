import {invoke} from '@tauri-apps/api/core';
import {IncomingFilesPanel,type IncomingFilesStatus} from '../../../packages/ui/src/IncomingFilesPanel';
import {getCompanionSnapshot,cancelCompanionAudioImport} from './companionClient';
export function WindowsIncomingFiles({busy,onChanged,onOpen}:{busy:boolean;onChanged:()=>void;onOpen:(id:string)=>void}){
 const command=(action:string,request:object={})=>invoke<IncomingFilesStatus>('companion_incoming_files',{action,request});
 return <IncomingFilesPanel busy={busy} onOpen={onOpen} onChanged={()=>onChanged()} adapter={{
  list:()=>command('list'),
  targets:async()=>{const snapshot=await getCompanionSnapshot();return snapshot.host.sessions.filter(row=>!row.organization?.trashedAt&&row.audioStored&&row.retention.audioCached&&row.status!=='recording').map(row=>({key:row.id,title:row.title}));},
  import:async request=>{try{return await command('import',request);}finally{onChanged();}},
  remove:id=>command('remove',{id}),cancel:async()=>{if(!await cancelCompanionAudioImport())throw Error('当前正在准备或完成保存，请稍候再取消，或等待接收结果。');}
 }}/>;
}
