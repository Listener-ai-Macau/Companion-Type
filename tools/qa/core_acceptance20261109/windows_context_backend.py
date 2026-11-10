"""Continue the completed actual GUI image-note case through backup/restore/purge.
Only its isolated public test library is touched; no GUI, model or service call.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,base64,ctypes,json,os,time,zipfile
import psutil
from windows_meeting import D,C,K,U,w,ExtendedLimits,CpuRate,require,spawn,alive,sha,station_name,object_name

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--case',type=Path,required=True);a=parser.parse_args();out=a.case.resolve();assert out.parent==C.resolve();case=json.loads((out/'result.json').read_text(encoding='utf-8'));assert case['state']=='REAL_NATIVE_RECORDING_IMAGE_CONTEXT_AND_SELECTED_ZIP_PASSED';root=Path(case['privateRoot']).resolve();assert root.parent==D.resolve();app=root/'app/companion-type.exe';assert sha(app)==case['exeSha256'];assert sha(root/'app/companion_type_lib.dll')==case['dllSha256']
 state=root/'state/sessions.json';rows=json.loads(state.read_text(encoding='utf-8'));ui=case['ui'];row=next(r for r in rows if r['id']==ui['sessionId']);note=next(n for n in row['meetingNotes'] if n['id']==ui['noteId']);image=note['image'];source_index_sha=sha(state);recording=root/'recordings';source_media={str(p):sha(p) for p in recording.iterdir() if p.is_file() and (p.name in [image['file'],image['preview']] or p.suffix in {'.wav','.mp3','.m4a'})}
 with zipfile.ZipFile(ui['zip']) as archive:
  pictures=[n for n in archive.namelist() if n.startswith('images/')];assert len(pictures)==1;assert __import__('hashlib').sha256(archive.read(pictures[0])).hexdigest()==image['sha256'];text=archive.read('会议材料.md').decode();assert note['text'] in text and '不选择的补充' not in text and '原图见图文ZIP' in text;assert json.loads(archive.read('备注来源.json'))==[note]
 result={'at':datetime.now(timezone.utc).isoformat(),'state':'RUNNING_ACTUAL_IMAGE_CONTEXT_BACKUP_RESTORE_AND_CLEANUP','appSource':case['frozenAppSource'],'imageSha256':image['sha256'],'modelCalls':0,'aiServiceCalls':0,'deviceAccess':False,'ownerDataUsed':False,'steps':[]};dest=out/'context-backend';dest.mkdir(exist_ok=False)
 def save():(dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 env={**os.environ,'APPDATA':str(root/'roaming'),'LOCALAPPDATA':str(root/'local'),'TEMP':str(root/'temp'),'TMP':str(root/'temp'),'COMPANION_TYPE_STATE_PATH':str(state),'COMPANION_TYPE_RECORDING_DIR':str(recording),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
 for key in ['DEEPSEEK_API_KEY','OPENAI_API_KEY','COMPANION_TYPE_ASR_API_KEY','COMPANION_TYPE_VOLC_APP_KEY','COMPANION_TYPE_VOLC_ACCESS_KEY','GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:env.pop(key,None)
 job=require(K.CreateJobObjectW(None,None));limits=ExtendedLimits();limits.BasicLimitInformation.LimitFlags=0x2000|0x200;limits.JobMemoryLimit=768*1024**2;require(K.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)));cpu=CpuRate(5,10000 if os.environ.get('GITHUB_ACTIONS')=='true' else 500);require(K.SetInformationJobObject(job,15,ctypes.byref(cpu),ctypes.sizeof(cpu)));desktop=station_name()+'\\'+object_name(U.GetThreadDesktop(K.GetCurrentThreadId()))
 def call(name,flag,request,environment=env,failure=False):
  input=dest/(name+'-request.json');output=dest/(name+'-result.json');input.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8');start=time.perf_counter()
  with (dest/(name+'.log')).open('wb') as log:
   proc=spawn([app,flag,input,output],environment,app.parent,desktop,job,log);deadline=time.monotonic()+120
   try:
    while alive(proc) and time.monotonic()<deadline:time.sleep(.1)
    assert not alive(proc),'Own CLI operation timed out; no completion claimed';code=w.DWORD();require(K.GetExitCodeProcess(proc.process,ctypes.byref(code)));assert (code.value!=0)==failure,(name,code.value,(dest/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-1000:])
   finally:K.CloseHandle(proc.process)
  result['steps'].append({'name':name,'exitCode':code.value,'seconds':time.perf_counter()-start,'expectedFailure':failure});save();return json.loads(output.read_text(encoding='utf-8')) if output.exists() else None
 save()
 try:
  readback=call('source-preview','--meeting-note-image-preview',{'sessionId':row['id'],'noteId':note['id']});picture=base64.b64decode(readback['dataUri'].split(',',1)[1],validate=True);assert picture[:2]==b'\xff\xd8' and __import__('hashlib').sha256(picture).hexdigest()==image['previewSha256']
  parent=root/'backups';parent.mkdir();backup=call('library-backup','--library-backup-request',{'directory':str(parent)});archive=Path(backup['path']).resolve();assert archive.parent.samefile(parent),'Backup must remain under its exact owned parent (including Windows extended-path aliases)'
  restored=root/'restored-context';restored.mkdir();new_recordings=restored/'recordings';new_recordings.mkdir();new_state=restored/'sessions.json';new_state.write_text('[]',encoding='utf-8');target_env={**env,'APPDATA':str(restored/'roaming'),'LOCALAPPDATA':str(restored/'local'),'TEMP':str(restored/'temp'),'TMP':str(restored/'temp'),'COMPANION_TYPE_STATE_PATH':str(new_state),'COMPANION_TYPE_RECORDING_DIR':str(new_recordings),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(restored/'settings.json')}
  for key in ['APPDATA','LOCALAPPDATA','TEMP']:
   Path(target_env[key]).mkdir(exist_ok=True)
  call('library-restore','--library-restore-request',{'directory':str(archive)},target_env);copies=json.loads(new_state.read_text(encoding='utf-8'));copy=next(r for r in copies if r['id']==row['id']);assert copy['meetingNotes']==row['meetingNotes'];assert copy['bookmarks']==row['bookmarks'];assert sha(new_recordings/image['file'])==image['sha256'];assert sha(new_recordings/image['preview'])==image['previewSha256'];assert copy['processingPolicy']=='manual'
  call('restored-preview','--meeting-note-image-preview',{'sessionId':copy['id'],'noteId':note['id']},target_env)
  def current():return next(r for r in json.loads(new_state.read_text(encoding='utf-8')) if r['id']==copy['id'])
  def target():return {'sessionId':copy['id'],'expectedRevision':current()['organization']['revision']}
  controls_before=[r for r in copies if r['id']!=copy['id']];call('trash','--library-state-request',{'action':'trash','targets':[target()]},target_env);call('trashed-preview-rejected','--meeting-note-image-preview',{'sessionId':copy['id'],'noteId':note['id']},target_env,True);assert (new_recordings/image['file']).exists();call('restore-trash','--library-state-request',{'action':'restore','targets':[target()]},target_env);call('restored-from-trash-preview','--meeting-note-image-preview',{'sessionId':copy['id'],'noteId':note['id']},target_env);call('trash-for-permanent-cleanup','--library-state-request',{'action':'trash','targets':[target()]},target_env);call('purge','--library-purge-request',{'targets':[target()]},target_env);after=json.loads(new_state.read_text(encoding='utf-8'));assert after==controls_before;assert not(new_recordings/image['file']).exists() and not(new_recordings/image['preview']).exists()
  assert sha(state)==source_index_sha;assert all(sha(Path(path))==digest for path,digest in source_media.items())
  plan=json.loads((out/'plan.json').read_text(encoding='utf-8'));assert sha(Path(plan['imageInput']))==plan['imageSha256'] and sha(Path(plan['audioInput']))==plan['audioSha256'];result.update(state='ACTUAL_PACKAGED_IMAGE_CONTEXT_BACKUP_RESTORE_PREVIEW_TRASH_RESTORE_AND_EXACT_PURGE_PASSED',sameSourceLibraryIndexAndAudioImageBytesUnchanged=True,unrelatedRestoredControlPreserved=True,originalSelectedInputFilesUnchanged=True,selectedZipContainsExactOriginalImage=True,restoredNotesAndBookmarksExact=True,restoredPreviewVerified=True,modelOrAiCalled=False,wholeSaleQualified=False)
 except BaseException as error:result.update(state='IMAGE_CONTEXT_BACKEND_FAILURE_RETAINED',error=repr(error));raise
 finally:K.CloseHandle(job);save()
 print(json.dumps({'state':result['state'],'evidence':str(dest),'steps':len(result['steps'])}))
if __name__=='__main__':main()
