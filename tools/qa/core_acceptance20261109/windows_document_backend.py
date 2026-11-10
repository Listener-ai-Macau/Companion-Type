"""Continue the exact GUI document library through native backup/restore/purge.
Only the isolated public software fixture is touched; no audio/model/service.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,base64,ctypes,json,os,time
from windows_meeting import D,C,K,U,w,ExtendedLimits,CpuRate,require,spawn,alive,sha,station_name,object_name

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--case',type=Path,required=True);a=parser.parse_args();out=a.case.resolve();assert out.parent==C.resolve();case=json.loads((out/'result.json').read_text(encoding='utf8'));assert case['state']=='REAL_NATIVE_DOCUMENT_CONTEXT_UI_PASSED';root=Path(case['privateRoot']).resolve();assert root.parent==D.resolve();app=root/'app/companion-type.exe';assert sha(app)==case['exeSha256'] and sha(root/'app/companion_type_lib.dll')==case['dllSha256']
 state=root/'state/sessions.json';rows=json.loads(state.read_text(encoding='utf8'));row=next(r for r in rows if r['id']==case['ui']['sessionId']);docs=row['documentContext']['rows'];assert len(docs)==7 and sum(bool(d.get('extraction')) for d in docs)==6;assert row['source']=='importedTranscript' and not row['audioStored'];recordings=root/'recordings';source_files={p.name:sha(p) for p in recordings.iterdir() if p.is_file() and not p.name.startswith('.')};assert len(source_files)>=14;source_index_sha=sha(state);dest=out/'document-backend';dest.mkdir()
 result={'at':datetime.now(timezone.utc).isoformat(),'state':'RUNNING_ACTUAL_DOCUMENT_CONTEXT_BACKUP_RESTORE_AND_CLEANUP','appSource':case['frozenAppSource'],'modelCalls':0,'aiServiceCalls':0,'deviceAccess':False,'ownerDataUsed':False,'steps':[]}
 def save():(dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 env={**os.environ,'APPDATA':str(root/'roaming'),'LOCALAPPDATA':str(root/'local'),'TEMP':str(root/'temp'),'TMP':str(root/'temp'),'COMPANION_TYPE_STATE_PATH':str(state),'COMPANION_TYPE_RECORDING_DIR':str(recordings),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
 for key in ['DEEPSEEK_API_KEY','OPENAI_API_KEY','COMPANION_TYPE_ASR_API_KEY','COMPANION_TYPE_VOLC_APP_KEY','COMPANION_TYPE_VOLC_ACCESS_KEY','GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:env.pop(key,None)
 job=require(K.CreateJobObjectW(None,None));limits=ExtendedLimits();limits.BasicLimitInformation.LimitFlags=0x2000|0x200;limits.JobMemoryLimit=768*1024**2;require(K.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)));cpu=CpuRate(5,10000 if os.environ.get('GITHUB_ACTIONS')=='true' else 500);require(K.SetInformationJobObject(job,15,ctypes.byref(cpu),ctypes.sizeof(cpu)));desktop=station_name()+'\\'+object_name(U.GetThreadDesktop(K.GetCurrentThreadId()))
 def call(name,flag,request,environment=env,failure=False):
  source=dest/(name+'-request.json');output=dest/(name+'-result.json');source.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8');started=time.perf_counter()
  with (dest/(name+'.log')).open('wb') as log:
   proc=spawn([app,flag,source,output],environment,app.parent,desktop,job,log);deadline=time.monotonic()+120
   try:
    while alive(proc) and time.monotonic()<deadline:time.sleep(.1)
    assert not alive(proc),'Owned native document operation exceeded timeout';code=w.DWORD();require(K.GetExitCodeProcess(proc.process,ctypes.byref(code)));assert (code.value!=0)==failure,(name,code.value,(dest/(name+'.log')).read_text(encoding='utf8',errors='replace')[-1000:])
   finally:K.CloseHandle(proc.process)
  result['steps'].append({'name':name,'exitCode':code.value,'seconds':time.perf_counter()-started,'expectedFailure':failure});save();return json.loads(output.read_text(encoding='utf8')) if output.exists() else None
 save()
 try:
  for index,doc in enumerate(docs):
   request={'action':'read','sessionId':row['id'],'revision':row['documentContext']['revision'],'documentId':doc['id']}
   if doc.get('extraction'):
    extracted=call('source-read-'+str(index),'--meeting-document-request',request);assert extracted['sourceSha256']==doc['sourceSha256']
  backups=root/'backups';backups.mkdir();backup=call('backup','--library-backup-request',{'directory':str(backups)});archive=Path(backup['path']).resolve();assert archive.parent.samefile(backups)
  restored=root/'restored-documents';restored.mkdir();new_recordings=restored/'recordings';new_recordings.mkdir();new_state=restored/'sessions.json';new_state.write_text('[]',encoding='utf8');target_env={**env,'APPDATA':str(restored/'roaming'),'LOCALAPPDATA':str(restored/'local'),'TEMP':str(restored/'temp'),'TMP':str(restored/'temp'),'COMPANION_TYPE_STATE_PATH':str(new_state),'COMPANION_TYPE_RECORDING_DIR':str(new_recordings),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(restored/'settings.json')}
  for key in ['APPDATA','LOCALAPPDATA','TEMP']:Path(target_env[key]).mkdir(exist_ok=True)
  call('restore','--library-restore-request',{'directory':str(archive)},target_env);copies=json.loads(new_state.read_text(encoding='utf8'));copy=next(r for r in copies if r['id']==row['id']);assert copy['documentContext']==row['documentContext'];assert copy['meetingNotes']==row['meetingNotes'];assert copy['transcriptText']==row['transcriptText'];assert not copy['audioStored'] and copy['processingPolicy']=='manual'
  assert all(sha(new_recordings/name)==digest for name,digest in source_files.items()),'Every original, extraction and independent owner anchor must survive the audio-free backup exactly'
  def current():return next(r for r in json.loads(new_state.read_text(encoding='utf8')) if r['id']==copy['id'])
  def target():return {'sessionId':copy['id'],'expectedRevision':current().get('organization',{}).get('revision',0)}
  first=next(d for d in docs if d.get('extraction'));revision=current()['documentContext']['revision'];call('restored-read','--meeting-document-request',{'action':'read','sessionId':copy['id'],'revision':revision,'documentId':first['id']},target_env);call('stale-remove-rejected','--meeting-document-request',{'action':'remove','sessionId':copy['id'],'revision':revision-1,'documentId':first['id']},target_env,True);assert current()['documentContext']==copy['documentContext']
  removed=next(d for d in docs if d['name']=='no-text.pdf');call('remove-one-entrance','--meeting-document-request',{'action':'remove','sessionId':copy['id'],'revision':revision,'documentId':removed['id']},target_env);assert (new_recordings/removed['file']).exists();assert len(current()['documentContext']['rows'])==6
  call('trash','--library-state-request',{'action':'trash','targets':[target()]},target_env);call('trashed-read-rejected','--meeting-document-request',{'action':'read','sessionId':copy['id'],'revision':current()['documentContext']['revision'],'documentId':first['id']},target_env,True);call('restore-trash','--library-state-request',{'action':'restore','targets':[target()]},target_env);call('read-after-trash-restore','--meeting-document-request',{'action':'read','sessionId':copy['id'],'revision':current()['documentContext']['revision'],'documentId':first['id']},target_env)
  controls=[r for r in json.loads(new_state.read_text(encoding='utf8')) if r['id']!=copy['id']];assert len(controls)==1 and controls[0]['id']=='core-public-document-unrelated';call('trash-for-purge','--library-state-request',{'action':'trash','targets':[target()]},target_env);call('purge','--library-purge-request',{'targets':[target()]},target_env);assert json.loads(new_state.read_text(encoding='utf8'))==controls;assert all(not(new_recordings/name).exists() for name in source_files),'Full record purge must include original files from removed document entrances and owner roots'
  assert sha(state)==source_index_sha and all(sha(recordings/name)==digest for name,digest in source_files.items());result.update(state='ACTUAL_PACKAGED_DOCUMENT_CONTEXT_BACKUP_RESTORE_TRASH_AND_EXACT_PURGE_PASSED',sourceOriginalIndexAndAllAttachmentsUnchanged=True,restoredOriginalAndExtractionFilesByteIdentical=len(source_files),unrelatedRestoredControlPreserved=True,removedEntranceOriginalRetainedUntilFullPurge=True,audioFreeDocumentBackupSupported=True,staleRevisionRejected=True,modelOrAiCalled=False,wholeSaleQualified=False)
 except BaseException as error:result.update(state='DOCUMENT_CONTEXT_BACKEND_FAILURE_RETAINED',error=repr(error));raise
 finally:K.CloseHandle(job);save()
 print(json.dumps({'state':result['state'],'evidence':str(dest),'steps':len(result['steps'])}))
if __name__=='__main__':main()
