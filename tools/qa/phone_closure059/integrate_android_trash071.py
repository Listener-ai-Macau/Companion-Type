from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
p=S/'apps/mobile/src/App.tsx';text=p.read_text(encoding='utf8')
def replace(old,new):
 global text
 assert text.count(old)==1,(old[:80],text.count(old));text=text.replace(old,new)
replace("import {LibraryBackups,type LibraryStatus} from './LibraryBackups';","import {LibraryBackups,type LibraryStatus} from './LibraryBackups';\nimport {RecordingManagement,RecordingRecycleBin,type RecordingLife,type RecordingLifeRequest,type RecordingLifeResult,type RecordingTrash} from './RecordingLifecycle';")
replace("type Row={key:string;", "type Row={lifecycle?:RecordingLife;libraryToken?:string;key:string;")
replace("type Detail={transcript:string;", "type Detail={lifecycle?:RecordingLife;libraryToken?:string;transcript:string;")
replace(" async function library(){",''' async function changeRecordingLife(request:RecordingLifeRequest):Promise<RecordingLifeResult>{
  const result=await run('正在管理本机录音',async()=>{
   const changed=await call<RecordingLifeResult>('recordingLifecycle',request);
   if(changed.cancelled)return changed;
   if(request.action==='trash'){clearLibrarySelection();setPage('library');}
   else if(request.action==='protect'||request.action==='unprotect'){
    setDetail(old=>old&&selected?.key===request.key?{...old,lifecycle:changed as RecordingLife}:old);
    setSelected(old=>old?.key===request.key?{...old,lifecycle:changed as RecordingLife}:old);
   }
   try{await library();}catch{setNotice('录音管理操作已完成，请刷新录音库核对。');}
   return changed;
  });
  if(!result)throw Error('操作尚未确认，请核对页面上方的提示后重试。');return result;
 }
 async function library(){''')
replace(" {rows.length?<><button className=\"recording-entry\"",''' {!readingPreview&&<RecordingRecycleBin busy={!!busy||!!status?.running||updateRunning} revision={rows} onLoad={()=>call<RecordingTrash>('recordingTrash')} onChange={changeRecordingLife}/>}
 {rows.length?<><button className="recording-entry"''')
replace("{detail&&<>{detail.recovered",'''{detail&&<>{!readingPreview&&detail.lifecycle&&detail.libraryToken&&<RecordingManagement key={selected.key} title={selected.title} life={detail.lifecycle} libraryToken={detail.libraryToken} busy={!!busy||!!status?.running||updateRunning} onChange={changeRecordingLife}/>} {detail.recovered''')
p.write_text(text,encoding='utf8')
p=S/'apps/mobile/src/mobileRefinement.css'
with p.open('a',encoding='utf8') as stream:stream.write('''
/* Local recording lifecycle follows the existing light/dark surface tokens. */
.recording-management,.recording-recycle-bin{margin:16px 0;padding:16px;border:1px solid var(--border);border-radius:16px;background:var(--surface);}
.recording-management summary,.recording-recycle-bin summary{font-weight:600;cursor:pointer;}
.recording-recycle-bin summary svg{vertical-align:-3px;margin-right:8px;}
.recording-management .buttons,.recording-recycle-bin .buttons{flex-wrap:wrap;}
.recording-management button svg,.recording-recycle-bin button svg{vertical-align:-3px;margin-right:6px;}
.recycle-item{padding:16px 0;border-top:1px solid var(--border);overflow-wrap:anywhere;}
.recycle-item:first-of-type{margin-top:12px;}
''')
print('Integrated Android local recording lifecycle into ordinary library/detail UI.')
