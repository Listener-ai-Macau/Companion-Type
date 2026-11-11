"""Exact installed-native audio editing, restart, backup and scoped cleanup.
All records are the isolated public/generated qualification library, no Owner data.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,ctypes,hashlib,json,os,struct,time
from windows_meeting import D,C,K,U,w,ExtendedLimits,CpuRate,require,spawn,alive,sha,station_name,object_name
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--case',type=Path,required=True);a=parser.parse_args()
 out=a.case.resolve();assert out.parent==C.resolve();case=json.loads((out/'result.json').read_text(encoding='utf8'));assert case['state']=='REAL_NATIVE_AUDIO_EDITING_UI_PASSED'
 root=Path(case['privateRoot']).resolve();assert root.parent==D.resolve();app=root/'app/companion-type.exe'
 assert sha(app)==case['exeSha256'] and sha(app.parent/'companion_type_lib.dll')==case['dllSha256']
 recordings=root/'recordings';state=root/'state/sessions.json';dest=out/'audio-edit-backend';dest.mkdir()
 result={'at':datetime.now(timezone.utc).isoformat(),'state':'RUNNING_ACTUAL_NATIVE_AUDIO_EDIT_BACKUP_RETRY_AND_PCM','appSource':case['frozenAppSource'],'ownerDataUsed':False,'modelsRun':False,'cloudCalls':0,'steps':[]}
 def save():(dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 env={**os.environ,'APPDATA':str(root/'roaming'),'LOCALAPPDATA':str(root/'local'),'TEMP':str(root/'temp'),'TMP':str(root/'temp'),'COMPANION_TYPE_STATE_PATH':str(state),'COMPANION_TYPE_RECORDING_DIR':str(recordings),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
 for key in ['DEEPSEEK_API_KEY','OPENAI_API_KEY','COMPANION_TYPE_ASR_API_KEY','COMPANION_TYPE_VOLC_APP_KEY','COMPANION_TYPE_VOLC_ACCESS_KEY','GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:env.pop(key,None)
 job=require(K.CreateJobObjectW(None,None));limits=ExtendedLimits();limits.BasicLimitInformation.LimitFlags=0x2000|0x200;limits.JobMemoryLimit=768*1024**2;require(K.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)));cpu=CpuRate(5,10000);require(K.SetInformationJobObject(job,15,ctypes.byref(cpu),ctypes.sizeof(cpu)))
 desktop=station_name()+'\\'+object_name(U.GetThreadDesktop(K.GetCurrentThreadId()))
 def invoke(name,flag,request,environment=env,failure=False,crash=False):
  source=dest/(name+'-request.json');output=dest/(name+'-result.json');source.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8');start=time.monotonic();killed=False;declared=None
  with (dest/(name+'.log')).open('wb') as log:
   proc=spawn([app,flag,source,output],environment,app.parent,desktop,job,log);deadline=time.monotonic()+180
   try:
    while alive(proc) and time.monotonic()<deadline:
     if crash and output.exists():
      try:status=json.loads(output.read_text(encoding='utf8'))
      except (OSError,json.JSONDecodeError):status={}
      if status.get('running') and 2<=status.get('completed',0)<31:
       journal=Path(environment['COMPANION_TYPE_STATE_PATH']).with_suffix('.audio-edit-job.json')
       declared=json.loads(journal.read_text(encoding='utf8'));K.TerminateProcess.argtypes=[w.HANDLE,w.UINT];K.TerminateProcess.restype=w.BOOL;require(K.TerminateProcess(proc.process,73));killed=True;break
     time.sleep(.01)
    if killed:
     until=time.monotonic()+10
     while alive(proc) and time.monotonic()<until:time.sleep(.02)
    assert not alive(proc),'Owned native edit operation timed out'
    code=w.DWORD();require(K.GetExitCodeProcess(proc.process,ctypes.byref(code)))
    assert killed if crash else (code.value!=0)==failure,(name,code.value,(dest/(name+'.log')).read_text(encoding='utf8',errors='replace')[-1200:])
   finally:K.CloseHandle(proc.process)
  result['steps'].append({'name':name,'exitCode':code.value,'seconds':round(time.monotonic()-start,3),'intentionalProcessTermination':killed,'expectedFailure':failure});save()
  return declared if crash else json.loads(output.read_text(encoding='utf8')) if output.exists() else None
 def call(name,action,request={},environment=env,**kw):return invoke(name,'--audio-edit-request',{'action':action,'request':request},environment,**kw)
 def owner(row,base):return base/('audio-edit-owner-'+hashlib.sha256(row['id'].encode()).hexdigest()+'.json')
 def verify_pcm(row,rows,base):
  meta=json.loads(owner(row,base).read_text(encoding='utf8'));assert meta['sessionId']==row['id'];plan=meta['provenance']['plan'];target=Path(row['audioPath'])
  assert target.stat().st_size==44+2*plan['frames'];assert sha(target)==meta['audioSha256']
  original=next(c for c in row['chunks'] if c['status']=='importedOriginal');assert sha(Path(original['path']))==meta['audioSha256']
  with target.open('rb') as actual:
   actual.seek(44);total=0
   for clip in plan['slices']:
    parent=next(r for r in rows if r['id']==clip['sourceKey']);assert parent['source']!='hostMeeting','Two-track range has its dedicated native PCM regression'
    chunks=[c for c in parent['chunks'] if '-host-part-' in c['id']]
    paths=[Path(c['path']) for c in chunks] if chunks else [Path(parent['audioPath'])]
    base_frame=0;copied=0
    for part in paths:
     frames=(part.stat().st_size-44)//2;lo=max(base_frame,clip['startFrame']);hi=min(base_frame+frames,clip['endFrame'])
     if lo<hi:
      with part.open('rb') as source:
       source.seek(44+2*(lo-base_frame));left=2*(hi-lo)
       while left:
        n=min(65536,left);expected=source.read(n);assert len(expected)==n and actual.read(n)==expected,'Actual derived PCM differs from the source map';left-=n
      copied+=hi-lo
     base_frame+=frames
    assert copied==clip['endFrame']-clip['startFrame'];total+=copied
   assert total==plan['frames'] and actual.read(1)==b''
  return {'id':row['id'],'frames':total,'sha256':meta['audioSha256']}
 save()
 try:
  rows=json.loads(state.read_text(encoding='utf8'));baseline_ids={r['id'] for r in rows};source_before={p.name:sha(p) for p in recordings.iterdir() if p.is_file() and not p.name.startswith('.')}
  exact=[verify_pcm(r,rows,recordings) for r in rows if r['source']=='derivedAudio'];assert len(exact)==4
  trim_id=case['ui']['trimId'];described=call('complete-trim-source','sources',{'keys':[trim_id]});src=described['sources'][0];assert src['frames']==240000
  def split_request(label):
   n=32;bounds=[src['frames']*i//n for i in range(n+1)]
   return {'libraryToken':described['libraryToken'],'outputs':[{'name':label+' · '+str(i+1),'plan':{'schema':1,'sampleRate':16000,'frames':bounds[i+1]-bounds[i],'slices':[{'sourceKey':trim_id,'sourceIdentity':src['identity'],'startFrame':bounds[i],'endFrame':bounds[i+1],'outputStartFrame':0,'outputEndFrame':bounds[i+1]-bounds[i]}]}} for i in range(n)]}
  cancelled=invoke('cancel-after-first-confirmed','--audio-edit-request',{'action':'start','request':split_request('公开取消重试093'),'cancelAfterOutputs':1})
  status=cancelled['status'];assert not status['running'] and status['state']=='cancelled' and 0<status['completed']<32
  ids=[o['key'] for o in status['outputs']];assert len(set(ids))==32
  retry=call('retry-cancelled-only-pending','retry',{'id':status['id']});assert retry['status']['state']=='complete';assert [o['key'] for o in retry['status']['outputs']]==ids
  crashed=invoke('crash-after-confirmed','--audio-edit-request',{'action':'start','request':split_request('公开退出恢复093')},crash=True)
  recovered=call('read-after-process-exit','status');assert not recovered['running'] and recovered['retryAvailable'] and recovered['id']==crashed['id']
  crash_ids=[o['key'] for o in crashed['outputs']];assert len(set(crash_ids))==32
  retry=call('retry-after-real-process-exit','retry',{'id':crashed['id']});assert retry['status']['state']=='complete';assert [o['key'] for o in retry['status']['outputs']]==crash_ids
  rows=json.loads(state.read_text(encoding='utf8'));assert len(rows)==len(baseline_ids)+64;assert baseline_ids.issubset({r['id'] for r in rows})
  assert all(sum(r['id']==key for r in rows)==1 for key in ids+crash_ids)
  exact.extend(verify_pcm(r,rows,recordings) for r in rows if r['id'] in ids+crash_ids)
  assert all(sha(recordings/name)==digest for name,digest in source_before.items())
  backups=root/'audio-edit-backups';backups.mkdir();backup=invoke('backup','--library-backup-request',{'directory':str(backups)});archive=Path(backup['path']).resolve();assert archive.parent.samefile(backups)
  restored=root/'restored-audio-edit';restored.mkdir();new_audio=restored/'recordings';new_audio.mkdir();new_state=restored/'sessions.json';new_state.write_text('[]',encoding='utf8')
  target_env={**env,'APPDATA':str(restored/'roaming'),'LOCALAPPDATA':str(restored/'local'),'TEMP':str(restored/'temp'),'TMP':str(restored/'temp'),'COMPANION_TYPE_STATE_PATH':str(new_state),'COMPANION_TYPE_RECORDING_DIR':str(new_audio),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(restored/'settings.json')}
  for key in ['APPDATA','LOCALAPPDATA','TEMP']:Path(target_env[key]).mkdir(exist_ok=True)
  source_all={p.name:sha(p) for p in recordings.iterdir() if p.is_file() and not p.name.startswith('.')};source_state_sha=sha(state)
  invoke('restore','--library-restore-request',{'directory':str(archive)},target_env)
  restored_rows=json.loads(new_state.read_text(encoding='utf8'));assert {r['id'] for r in rows}=={r['id'] for r in restored_rows};assert all(sha(new_audio/name)==digest for name,digest in source_all.items())
  restored_source=call('restored-parent-identity','sources',{'keys':[trim_id]},target_env)['sources'][0];assert restored_source==src
  child=next(r for r in restored_rows if r['id']==case['ui']['mergedId'])
  restored_map=call('restored-provenance','provenance',{'sessionId':child['id']},target_env);assert restored_map['available']
  target=call('restored-source-position','sourceTarget',{'sessionId':child['id'],'index':0},target_env);assert target=={'sessionId':trim_id,'positionMs':5000}
  before_cleanup={name:sha(new_audio/name) for name in source_all}
  invoke('audio-only-cleanup','--library-control-request',{'action':'privacyEraseAudio','sessionId':child['id']},target_env)
  after=next(r for r in json.loads(new_state.read_text(encoding='utf8')) if r['id']==child['id']);assert not after['audioStored'];assert owner(after,new_audio).is_file()
  assert call('provenance-after-audio-only-cleanup','provenance',{'sessionId':child['id']},target_env)==restored_map
  unrelated=[r for r in json.loads(new_state.read_text(encoding='utf8')) if r['id']!=child['id']]
  def current_target():
   row=next(r for r in json.loads(new_state.read_text(encoding='utf8')) if r['id']==child['id']);return {'sessionId':child['id'],'expectedRevision':row.get('organization',{}).get('revision',0)}
  invoke('trash','--library-state-request',{'action':'trash','targets':[current_target()]},target_env)
  invoke('purge','--library-purge-request',{'targets':[current_target()]},target_env)
  assert json.loads(new_state.read_text(encoding='utf8'))==unrelated;assert not owner(after,new_audio).exists()
  owned={Path(child['audioPath']).name,Path(next(c for c in child['chunks'] if c['status']=='importedOriginal')['path']).name,owner(child,new_audio).name}
  assert all((not(new_audio/name).exists()) if name in owned else sha(new_audio/name)==digest for name,digest in before_cleanup.items())
  assert sha(state)==source_state_sha and all(sha(recordings/name)==digest for name,digest in source_all.items())
  result.update(state='ACTUAL_PACKAGED_AUDIO_EDIT_PCM_CANCEL_RESTART_PENDING_ONLY_RETRY_BACKUP_RESTORE_AND_SCOPED_PURGE_PASSED',exactPcm=exact,generatedOutputRows=len(exact),cancelledCompleted=status['completed'],crashAcknowledgedOutputs=len([o for o in crashed['outputs'] if o['state']=='complete']),cancelRetrySame32Ids=True,crashRetrySame32Ids=True,backupFiles=backup['files'],restoreFilesByteIdentical=len(source_all),sourceAndUnrelatedRowsUnchanged=True,sourceIdentitySurvivesNewRoot=True,sourceMapSurvivesAudioOnlyCleanup=True,fullPurgeDeletesOnlyChildFiles=True,wholeSaleQualified=False)
 except BaseException as error:result.update(state='AUDIO_EDIT_BACKEND_FAILURE_RETAINED',error=repr(error));raise
 finally:K.CloseHandle(job);save()
 print(json.dumps({'state':result['state'],'evidence':str(dest),'steps':len(result['steps'])}))
if __name__=='__main__':main()
