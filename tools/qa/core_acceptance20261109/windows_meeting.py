"""One isolated native Windows meeting workflow; no demo or mock fallback.

Runs a frozen production app on a noninteractive window station, with a private
library/profile and existing automatic device/model recovery disabled. Neither
this tooling nor a seeded text record qualifies capture, ASR or a real meeting.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from ctypes import wintypes as w
import argparse,ctypes,hashlib,json,os,socket,subprocess,sys,time,uuid,msvcrt,shutil
import psutil

S=Path(__file__).resolve().parents[3];R=Path(os.environ.get('COMPANION_ACCEPTANCE_PROJECT_ROOT',str(S.parent)))
C=R/'docs/handoffs/20261109-core-acceptance';D=Path(os.environ.get('COMPANION_ACCEPTANCE_CACHE','E:/CodexData/Companion/.build-cache/core-acceptance20261109'))
CPU_PERCENT=100 if os.environ.get('GITHUB_ACTIONS')=='true' else 5
DEDICATED_CI=os.environ.get('GITHUB_ACTIONS')=='true'
K=ctypes.WinDLL('kernel32',use_last_error=True);U=ctypes.WinDLL('user32',use_last_error=True)
class Startup(ctypes.Structure):
 _fields_=[('cb',w.DWORD),('lpReserved',w.LPWSTR),('lpDesktop',w.LPWSTR),('lpTitle',w.LPWSTR),('dwX',w.DWORD),('dwY',w.DWORD),('dwXSize',w.DWORD),('dwYSize',w.DWORD),('dwXCountChars',w.DWORD),('dwYCountChars',w.DWORD),('dwFillAttribute',w.DWORD),('dwFlags',w.DWORD),('wShowWindow',w.WORD),('cbReserved2',w.WORD),('lpReserved2',ctypes.POINTER(ctypes.c_ubyte)),('hStdInput',w.HANDLE),('hStdOutput',w.HANDLE),('hStdError',w.HANDLE)]
class Process(ctypes.Structure):
 _fields_=[('process',w.HANDLE),('thread',w.HANDLE),('pid',w.DWORD),('tid',w.DWORD)]
class BasicLimits(ctypes.Structure):
 _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class IoCounters(ctypes.Structure):_fields_=[(name,ctypes.c_ulonglong) for name in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
class ExtendedLimits(ctypes.Structure):
 _fields_=[('BasicLimitInformation',BasicLimits),('IoInfo',IoCounters),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
class CpuRate(ctypes.Structure):_fields_=[('flags',w.DWORD),('rate',w.DWORD)]
EnumProc=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
for lib,name,args,result in [
 (K,'CreateJobObjectW',[ctypes.c_void_p,w.LPCWSTR],w.HANDLE),(K,'SetInformationJobObject',[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),
 (K,'AssignProcessToJobObject',[w.HANDLE,w.HANDLE],w.BOOL),(K,'CloseHandle',[w.HANDLE],w.BOOL),
 (K,'QueryInformationJobObject',[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p],w.BOOL),
 (K,'OpenProcess',[w.DWORD,w.BOOL,w.DWORD],w.HANDLE),(K,'IsProcessInJob',[w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL),
 (K,'CreateProcessW',[w.LPCWSTR,w.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,w.BOOL,w.DWORD,ctypes.c_void_p,w.LPCWSTR,ctypes.POINTER(Startup),ctypes.POINTER(Process)],w.BOOL),
 (K,'ResumeThread',[w.HANDLE],w.DWORD),(K,'GetExitCodeProcess',[w.HANDLE,ctypes.POINTER(w.DWORD)],w.BOOL),
 (K,'CreateMemoryResourceNotification',[ctypes.c_int],w.HANDLE),(K,'QueryMemoryResourceNotification',[w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL),
 (U,'GetProcessWindowStation',[],w.HANDLE),(U,'SetProcessWindowStation',[w.HANDLE],w.BOOL),
 (U,'GetThreadDesktop',[w.DWORD],w.HANDLE),(K,'GetCurrentThreadId',[],w.DWORD),(U,'SetThreadDesktop',[w.HANDLE],w.BOOL),
 (U,'CreateWindowStationW',[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p],w.HANDLE),(U,'CloseWindowStation',[w.HANDLE],w.BOOL),
 (U,'CreateDesktopW',[w.LPCWSTR,w.LPCWSTR,ctypes.c_void_p,w.DWORD,w.DWORD,ctypes.c_void_p],w.HANDLE),(U,'CloseDesktop',[w.HANDLE],w.BOOL),
 (U,'GetClipboardSequenceNumber',[],w.DWORD),(U,'EnumDesktopWindows',[w.HANDLE,EnumProc,w.LPARAM],w.BOOL),
 (U,'GetWindowThreadProcessId',[w.HWND,ctypes.POINTER(w.DWORD)],w.DWORD),(U,'GetWindowTextW',[w.HWND,w.LPWSTR,ctypes.c_int],ctypes.c_int),
 (U,'PostMessageW',[w.HWND,w.UINT,w.WPARAM,w.LPARAM],w.BOOL),(U,'GetUserObjectInformationW',[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)],w.BOOL)]:
 f=getattr(lib,name);f.argtypes=args;f.restype=result
def require(value):
 if not value:raise ctypes.WinError(ctypes.get_last_error())
 return value
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def object_name(handle):
 buf=ctypes.create_unicode_buffer(256);needed=w.DWORD();require(U.GetUserObjectInformationW(handle,2,buf,ctypes.sizeof(buf),ctypes.byref(needed)));return buf.value
def station_name():return object_name(U.GetProcessWindowStation())
def windows(desktop,pid):
 result=[]
 @EnumProc
 def visit(hwnd,_):
  owner=w.DWORD();U.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
  if owner.value==pid:
   text=ctypes.create_unicode_buffer(1000);U.GetWindowTextW(hwnd,text,1000);result.append({'hwnd':hwnd,'title':text.value})
  return True
 require(U.EnumDesktopWindows(desktop,visit,0));return result
def alive(process):
 value=w.DWORD();require(K.GetExitCodeProcess(process.process,ctypes.byref(value)));return value.value==259
def spawn(args,env,cwd,desktop,job,log):
 startup=Startup();startup.cb=ctypes.sizeof(startup);startup.lpDesktop=desktop;startup.dwFlags=0x100|0x80
 null=open(os.devnull,'rb');handles=[msvcrt.get_osfhandle(null.fileno()),msvcrt.get_osfhandle(log.fileno())]
 for handle in handles:os.set_handle_inheritable(handle,True)
 startup.hStdInput=handles[0];startup.hStdOutput=handles[1];startup.hStdError=handles[1]
 environment=ctypes.create_unicode_buffer('\0'.join(key+'='+str(value) for key,value in sorted(env.items(),key=lambda x:x[0].upper()))+'\0\0')
 command=ctypes.create_unicode_buffer(subprocess.list2cmdline(list(map(str,args))));process=Process()
 try:require(K.CreateProcessW(str(args[0]),command,None,None,True,0x400|0x08000000|0x40|0x4,environment,str(cwd),ctypes.byref(startup),ctypes.byref(process)))
 finally:
  for handle in handles:os.set_handle_inheritable(handle,False)
  null.close()
 require(K.AssignProcessToJobObject(job,process.process));assert K.ResumeThread(process.thread)!=0xffffffff;K.CloseHandle(process.thread);process.thread=None
 return process
def frozen_app(root):
 verification=Path(os.environ['COMPANION_ACCEPTANCE_VERIFICATION']) if os.environ.get('COMPANION_ACCEPTANCE_VERIFICATION') else R/'docs/handoffs/20261109-windows-file-copy078/windows-verification.json'
 v=json.loads(verification.read_text(encoding='utf8'))
 payload=Path(os.environ['COMPANION_ACCEPTANCE_FROZEN_NATIVE']) if os.environ.get('COMPANION_ACCEPTANCE_FROZEN_NATIVE') else R/'docs/handoffs/20261109-windows-file-copy078/msi-inspection/files'
 app=root/'app';app.mkdir()
 for name,key in [('companion-type.exe','embeddedExeSha256'),('companion_type_lib.dll','dllSha256')]:
  source=next(p for p in payload.rglob('*') if p.is_file() and sha(p)==v[key]);shutil.copy2(source,app/name);assert sha(app/name)==v[key]
 shutil.copytree(S/'apps/windows/src-tauri/resources/licenses',app/'licenses');shutil.copy2(S/'apps/windows/src-tauri/resources/opus-license.txt',app/'licenses/opus.txt')
 return app,v
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['inspect','handoff','audio','ai','transcribe','actions'],default='inspect');parser.add_argument('--library',type=Path);parser.add_argument('--audio',type=Path);parser.add_argument('--reviewed-ai',type=Path);a=parser.parse_args()
 psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
 low=K.CreateMemoryResourceNotification(0);require(low);value=w.BOOL();require(K.QueryMemoryResourceNotification(low,ctypes.byref(value)));assert not value.value,'Actual Windows low-memory signal; no app launched'
 token=uuid.uuid4().hex;root=D/token;root.mkdir(parents=True);out=C/token;out.mkdir(parents=True)
 app,v=frozen_app(root)
 state=root/'state';state.mkdir();session=json.loads((S/'apps/windows/src-tauri/src/calendar_test_fixtures/p738-sessions.json').read_text(encoding='utf8'))[0]
 session.update(id='core-public-20261109',title='明确虚构·核心会后流程验收',transcriptText='小王：采购清单需要周五前核对。\n小李：追加20%的费用尚未批准，需要书面确认。',transcriptPreview='小王：采购清单需要周五前核对。',calendarCopies=[],calendarSlotCopies=[],calendarCopyRevision=0,exportedAt=None,exportMarkdown='')
 text='## Summary\n明确虚构的工程资料，仅验证会后操作和文件交付，不代表ASR或AI质量。\n\n## Action Items\n- [ ] 核对采购清单（负责人：小王；截止：周五）\n\n## Questions\n- 追加20%的费用尚未批准，等待书面确认。'
 session['minutes'].update(markdown=text,source='userAuthored');session['minutesByMode']['offlineStore'].update(markdown=text,source='userAuthored')
 session['meetingNotes']=[{'id':'exclude-note','text':'不选择的补充：内部备注不可进入本次文件','createdAt':'2026-11-09T05:00:00Z','updatedAt':'2026-11-09T05:00:00Z'}]
 sessions=[session]
 if a.library:
  evidence=a.library.resolve();assert evidence.parent==C.resolve() and evidence.name.startswith('saved-')
  prior=json.loads((evidence/'result.json').read_text(encoding='utf8'));source=Path(prior['root'])/'state/sessions.json'
  assert sha(source)==prior['checkpointStateSha256'];sessions=json.loads(source.read_text(encoding='utf8'));session=next(row for row in sessions if row['id']=='core-real-public-S_R004S03C01')
 if a.stage in {'ai','actions'}:
  assert a.reviewed_ai and not a.library and not a.audio
  session=json.loads(a.reviewed_ai.read_text(encoding='utf8'));sessions=[session]
  whole=os.environ.get('COMPANION_ACCEPTANCE_WHOLE_DELIVERY_DIR')
  if whole:
   material=Path(whole);manifest=json.loads((material/'manifest.json').read_text(encoding='utf8'))
   assert session['id']==manifest['sessionId'] and session['source']=='importedAudio' and session['audioStored']
   assert hashlib.sha256(session['transcriptText'].encode('utf8')).hexdigest()==manifest['rawTranscriptSha256']
   original=next(c for c in session['chunks'] if c['status']=='importedOriginal');original_path=original['path'];decoded_path=session['audioPath'];(root/'recordings').mkdir()
   paths={decoded_path:root/'recordings'/(session['id']+'.wav'),original_path:root/'recordings'/(session['id']+'.original.wav')}
   for name,old,digest in [('decoded.wav',decoded_path,manifest['decodedAudioSha256']),('original.wav',original_path,manifest['sourceAudioSha256'])]:
    assert sha(material/name)==digest;shutil.copy2(material/name,paths[old]);assert sha(paths[old])==digest
   session['audioPath']=str(paths[decoded_path])
   for chunk in session['chunks']:assert chunk['path'] in paths;chunk['path']=str(paths[chunk['path']])
  else:
   assert session['id']=='core-real-public-S_R004S03C01' and session['source']=='importedTranscript'
   assert session['transcriptReview']['revision']==1 and not session['audioStored']
  assert session['minutes']['source']=='llm_deepseek' and session['minutes']['processing']['complete']
 (state/'sessions.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
 whole_delivery=a.stage=='ai' and bool(os.environ.get('COMPANION_ACCEPTANCE_WHOLE_DELIVERY_DIR'))
 (out/'plan.json').write_text(json.dumps({'sessionId':session['id'],'title':session['title'],'sourceMeeting':prior['sourceMeeting'] if a.library else 'S_R004S03C01' if a.stage=='ai' else None,'selectedNoteId':(session.get('meetingNotes') or [{}])[0].get('id'),'expectedManualDocument':session['minutesByMode']['offlineStore']['markdown'],'realAsrInput':bool(a.library) or a.stage=='ai','requireGroupedUi':v['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82'},'wholeMeetingDelivery':whole_delivery,'browserAttachments':whole_delivery and os.environ.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1','aiChunks':session['minutes']['processing']['totalChunks'] if whole_delivery else 2,'expectedExportContains':session['minutes']['summary'][0][:50] if whole_delivery else None},ensure_ascii=False),encoding='utf8')
 if a.stage=='actions':
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan['savedActionCount']=len(session['minutes']['actionItems']);(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage in {'audio','transcribe'}:
  assert a.audio and sha(a.audio)=='82ac9f8b25e2c085b2e0434e444727af0577e373ed5e1f587d3f28881862fe2f'
  (root/'exports').mkdir();plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan.update(audioInput=str(a.audio.resolve()),audioSha256=sha(a.audio),audioTitle=a.audio.stem,audioSeconds=2327.119,exportDirectory=str(root/'exports'),receivedDirectory=str(root/'received-files'),wholeMeetingAsr=a.stage=='transcribe')
  (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage=='ai' and whole_delivery and os.environ.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1':
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan['desktopPrimaryFileCopy']=v['version']=='0.1.81'
  (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 for name in ['roaming','local','recordings','webview','temp']:(root/name).mkdir(exist_ok=True)
 # A missing private settings file means valid fresh defaults. Writing '{}'
 # would be a corrupt product store, not an empty configured user profile.
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'state':'PREPARING_NATIVE_WORKFLOW','stage':a.stage,'frozenAppVersion':v['version'],'frozenAppSource':v['sourceCommit'],'exeSha256':v['embeddedExeSha256'],'dllSha256':v['dllSha256'],'inputKind':'explicit fictional text-only software workflow fixture; not a real meeting/ASR/capture test','privateRoot':str(root),'ownerClipboardContentsRead':False,'ordinaryRecipientTested':False,'wholeCoreCandidateQualified':False,'modelsRun':False,'boardAccessed':False,'phoneAccessed':False}
 def save():(out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 def resources():
  limits=ExtendedLimits();require(K.QueryInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits),None))
  record['sampledJobPrivateCommitPeakBytes']=limits.PeakJobMemoryUsed
  memory=psutil.virtual_memory();record['lastResourceObservation']={'availablePhysicalBytes':memory.available,'systemPhysicalPercent':memory.percent}
 old_station=U.GetProcessWindowStation();old_desktop=U.GetThreadDesktop(K.GetCurrentThreadId());before_clip=U.GetClipboardSequenceNumber()
 if a.library:record['inputKind']='Existing real public ASR output plus explicit engineering manual review/document; not new ASR/AI or capture'
 if a.stage=='audio':record['inputKind']='Actual public S_R004S03C01 audio; native import, playback and export only, no ASR/AI or capture'
 if a.stage in {'ai','actions'}:record['inputKind']='Actual cached public AI minutes after declared manual source review; ordinary reading and export, no new cloud request or ASR'
 if whole_delivery:record['inputKind']='The same actual public imported audio and new fixed-product ASR, followed by actual cloud AI; reading/audio playback/document receipt and restoration continuation, no new ASR/cloud call in this UI stage'
 if a.stage=='transcribe':record.update(inputKind='Actual public S_R004S03C01 audio through the fixed current product CPU ASR; no training, provider substitution or cloud audio',modelsRun=True,modelResearchOrTrainingRun=False)
 name=station_name() if DEDICATED_CI else 'CompanionCore-'+token
 station=old_station if DEDICATED_CI else require(U.CreateWindowStationW(name,0,0x37f,None));desktop=None;job=None;processes=[];logs=[];receiver=None;handled=set();dialog_workers={}
 try:
  require(U.SetProcessWindowStation(station));desktop=old_desktop if DEDICATED_CI else require(U.CreateDesktopW('Meeting',None,None,0,0x1ff,None));require(U.SetThreadDesktop(desktop));assert station_name()==name
  desktop_path=name+'\\'+object_name(desktop)
  record['privateStation']=name;record['stationVerifiedBeforeLaunch']=True
  record['desktopIsolation']='Dedicated disposable GitHub Windows runner; no owner desktop' if DEDICATED_CI else 'Private noninteractive window station on owner PC'
  job=require(K.CreateJobObjectW(None,None));limit=ExtendedLimits();limit.BasicLimitInformation.LimitFlags=0x2000|0x200;limit.JobMemoryLimit=(3072 if DEDICATED_CI and (a.stage=='transcribe' or os.environ.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1') else 1536)*1024**2;require(K.SetInformationJobObject(job,9,ctypes.byref(limit),ctypes.sizeof(limit)));cpu=CpuRate(0x1|0x4,CPU_PERCENT*100);require(K.SetInformationJobObject(job,15,ctypes.byref(cpu),ctypes.sizeof(cpu)));record['cpuHardCapPercent']=CPU_PERCENT;record['ownJobPrivateCommitLimitBytes']=limit.JobMemoryLimit
  env={**os.environ,'APPDATA':str(root/'roaming'),'LOCALAPPDATA':str(root/'local'),'TEMP':str(root/'temp'),'TMP':str(root/'temp'),'COMPANION_TYPE_STATE_PATH':str(state/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(root/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json'),'COMPANION_TYPE_BACKGROUND_WINDOW':'1','COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1','COMPANION_TYPE_WEBVIEW_ARGS':f'--remote-debugging-port={port} --mute-audio --disable-gpu','WEBVIEW2_USER_DATA_FOLDER':str(root/'webview')}
  for key in ['DEEPSEEK_API_KEY','OPENAI_API_KEY','COMPANION_TYPE_ASR_API_KEY','COMPANION_TYPE_VOLC_APP_KEY','COMPANION_TYPE_VOLC_ACCESS_KEY','GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:env.pop(key,None)
  if a.audio:env['COMPANION_ACCEPTANCE_AUDIO_INPUT']=str(a.audio.resolve())
  if a.stage=='transcribe':
   assert DEDICATED_CI and os.environ.get('COMPANION_ACCEPTANCE_FIXED_ASR_ROOT'),'Fixed product inference only on the dedicated runner'
   env['COMPANION_TYPE_LOCAL_ASR_DIR']=os.environ['COMPANION_ACCEPTANCE_FIXED_ASR_ROOT']
  if a.stage=='actions':
   assert DEDICATED_CI,'The normal visible-window clipboard journey runs only on an owned dedicated CI runner'
   env['COMPANION_TYPE_BACKGROUND_WINDOW']='0'
   record['normalVisibleWindowOnDedicatedRunner']=True
  log=(out/'app.log').open('wb');logs.append(log);p=spawn([app/'companion-type.exe'],env,app,desktop_path,job,log);processes.append(p);record['appPid']=p.pid;record['state']='STARTING_PRIVATE_NATIVE_APP';save()
  deadline=time.monotonic()+60
  import urllib.request
  local_http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  while time.monotonic()<deadline:
   require(K.QueryMemoryResourceNotification(low,ctypes.byref(value)));assert not value.value,'Actual Windows low-memory signal; stopping only this owned job'
   assert alive(p),'Frozen native app exited before CDP'
   try:
    with local_http.open(f'http://127.0.0.1:{port}/json/version',timeout=1) as response:record['webviewAgent']=json.load(response).get('User-Agent');break
   except Exception:time.sleep(.3)
  else:raise TimeoutError('Private native WebView did not expose CDP; no foreground fallback')
  actual_windows=windows(desktop,p.pid);assert actual_windows,'App main window not proven on private desktop';record['nativeWindowsOnPrivateDesktop']=actual_windows
  # Hosted Edge131's browser is broker-launched and is not exposed as an
  # app descendant by psutil. Bind the PID listening on our freshly allocated
  # CDP port as well as descendants, then prove the exact private profile.
  # The browser must still belong to our bounded job, not an arbitrary browser.
  candidates={child.pid for child in psutil.Process(p.pid).children(recursive=True)}
  listeners={conn.pid for conn in psutil.net_connections(kind='tcp') if conn.status==psutil.CONN_LISTEN and conn.laddr.port==port and conn.pid}
  record['cdpListenerPids']=sorted(listeners);assert len(listeners)==1,'CDP listener is not uniquely attributable'
  candidates.update(listeners);profiles=[]
  for child_pid in sorted(candidates):
   try:
    child=psutil.Process(child_pid)
    try:arguments=child.cmdline()
    except (psutil.NoSuchProcess,psutil.AccessDenied):continue
    for argument in arguments:
     if argument.startswith('--user-data-dir='):
      folder=argument.split('=',1)[1].strip('"');handle=require(K.OpenProcess(0x1000,False,child.pid))
      try:in_job=w.BOOL();require(K.IsProcessInJob(handle,job,ctypes.byref(in_job)))
      finally:K.CloseHandle(handle)
      # The hosted WebView2 runtime creates EBWebView beneath the requested
      # data folder; both exact layouts are private to this owned test run.
      profiles.append({'pid':child.pid,'folder':folder,'matchesPrivateRoot':Path(folder).resolve() in {(root/'webview').resolve(),(root/'webview/EBWebView').resolve()},'belongsToBoundedJob':bool(in_job.value),'cdpListener':child.pid in listeners})
   except psutil.NoSuchProcess:continue
  record['observedWebviewProfiles']=profiles;save()
  assert any(item['cdpListener'] for item in profiles) and all(item['matchesPrivateRoot'] and item['belongsToBoundedJob'] for item in profiles),'Actual CDP browser is not proven in the private profile and bounded job';record['webviewProfileVerifiedPrivate']=True
  log=(out/'ui.log').open('wb');logs.append(log);node=spawn([shutil.which('node'),S/'tools/qa/core_acceptance20261109/windows_meeting_ui.cjs',str(port),str(out),a.stage],env,S,desktop_path,job,log);processes.append(node)
  deadline=time.monotonic()+(1200 if a.stage=='transcribe' else 480 if a.stage=='audio' else 180)
  while alive(node) and time.monotonic()<deadline:
   resources();require(K.QueryMemoryResourceNotification(low,ctypes.byref(value)));assert not value.value,'Actual low-memory signal during own UI worker'
   for request in sorted(out.glob('dialog-request-*.json')):
    if request.name in handled:continue
    reply=out/request.name.replace('dialog-request-','dialog-reply-');log=(out/(request.stem+'.log')).open('wb');logs.append(log)
    worker=spawn([sys.executable,S/'tools/qa/core_acceptance20261109/windows_native_dialog.py','--pid',str(p.pid),'--root',root,'--desktop',desktop_path,'--request',request,'--reply',reply],env,S,desktop_path,job,log);processes.append(worker);handled.add(request.name);dialog_workers[reply]=worker
   for reply,worker in dialog_workers.items():
    if not reply.exists() and not alive(worker):reply.write_text(json.dumps({'state':'OWNED_NATIVE_FILE_PICKER_ACTION_FAILED','error':'Helper exited before completion; see retained dialog log'}),encoding='utf8')
   for request in sorted(out.glob('handoff-request-*.json')):
    if request.name in handled:continue
    from windows_file_receiver import Receiver,copied_path
    data=json.loads(request.read_text(encoding='utf8'));source=copied_path();assert source.name==data['fileName'] and source.parent.name and source.parent.parent.name=='content-share'
    if receiver is None:
     receiver=Receiver(root,out,job,desktop,desktop_path,env);receiver.start()
    received=receiver.paste(source)
    audio_file=source.suffix in {'.wav','.mp3'}
    if a.stage=='audio' or audio_file:
     assert a.stage=='audio' or whole_delivery
     assert source.suffix in {'.wav','.mp3'}
     if source.suffix=='.wav':
      expected=plan['audioSha256'] if a.stage=='audio' else manifest['sourceAudioSha256']
      assert sha(source)==expected;received['originalAudioBytesIdentical']=True
     else:assert source.stat().st_size>64;received['mp3DecodeQualification']='Requires subsequent actual product reimport/playback, not size alone'
    elif source.suffix=='.pdf':
     from pypdf import PdfReader
     text='\n'.join(page.extract_text() or '' for page in PdfReader(receiver.destination/source.name).pages)
    elif source.suffix=='.docx':
     import zipfile,xml.etree.ElementTree as ET
     with zipfile.ZipFile(receiver.destination/source.name) as archive:text=''.join(ET.fromstring(archive.read('word/document.xml')).itertext())
    else:text=(receiver.destination/source.name).read_text(encoding='utf8')
    if a.stage!='audio' and not audio_file:
     assert 'EXCLUDED_CORE_NOTE_20261109' not in text
     if a.stage=='ai':
      if whole_delivery:
       expected=json.loads((out/'plan.json').read_text(encoding='utf8'))['expectedExportContains']
       if source.suffix=='.pdf':
        # PDF pagination inserts layout newlines inside ordinary sentences.
        # Ignore only whitespace; never edit/substitute source words or facts.
        (out/'actual-received-pdf-extracted.txt').write_text(text,encoding='utf8')
        assert ''.join(expected.split()) in ''.join(text.split())
        received['pdfContentMatch']='Source excerpt retained after layout-whitespace normalization only'
       else:assert expected in text
      else:assert '周一至周五' in text and '临时区' not in text and '基于修订后的转写生成' in text
     else:assert '人工软件验收草稿' in text and '工程验收补充' in text
     received['selectedContentsVerified']=True
    record.setdefault('receivedFiles',[]).append(received)
    reply=out/request.name.replace('handoff-request-','handoff-reply-');reply.write_text(json.dumps(received,ensure_ascii=False),encoding='utf8');handled.add(request.name);save()
   request=out/'text-clipboard-request.json'
   if a.stage=='actions' and request.exists() and request.name not in handled:
    # This station belongs to this isolated fixture. Read only the string the
    # immediately preceding public-fixture copy operation asked us to verify.
    expected=json.loads(request.read_text(encoding='utf8'))['expected']
    U.OpenClipboard.argtypes=[w.HWND];U.OpenClipboard.restype=w.BOOL;U.GetClipboardData.argtypes=[w.UINT];U.GetClipboardData.restype=w.HANDLE
    K.GlobalLock.argtypes=[w.HANDLE];K.GlobalLock.restype=ctypes.c_void_p;K.GlobalUnlock.argtypes=[w.HANDLE]
    require(U.OpenClipboard(None))
    try:
     handle=require(U.GetClipboardData(13));pointer=require(K.GlobalLock(handle))
     try:actual=ctypes.wstring_at(pointer)
     finally:K.GlobalUnlock(handle)
    finally:require(U.CloseClipboard())
    assert actual==expected,'Actual Windows clipboard does not match filtered public followup'
    result={'actualWindowsUnicodeClipboardMatched':True,'sha256':hashlib.sha256(actual.encode('utf8')).hexdigest(),'characters':len(actual),'scope':'Only the public draft copied by the immediately preceding ordinary button; no original owner clipboard read'}
    (out/'text-clipboard-reply.json').write_text(json.dumps(result),encoding='utf8');handled.add(request.name)
   time.sleep(.25)
  assert not alive(node),'UI workflow exceeded its bounded stage timeout';code=w.DWORD();require(K.GetExitCodeProcess(node.process,ctypes.byref(code)));assert code.value==0,(out/'ui.log').read_text(encoding='utf8',errors='replace')[-1800:]
  record['ui']=json.loads((out/'ui-result.json').read_text(encoding='utf8'));record['state']='NATIVE_PRIVATE_UI_INSPECTED' if a.stage=='inspect' else 'REAL_NATIVE_PUBLIC_AUDIO_FLOW_PASSED' if a.stage=='audio' else 'REAL_NATIVE_FIXED_PRODUCT_AUDIO_TRANSCRIPTION_PASSED' if a.stage=='transcribe' else 'REAL_NATIVE_REVIEWED_AI_READING_AND_HANDOFF_PASSED' if a.stage=='ai' else 'REAL_NATIVE_MEETING_SELECTED_FILES_RECEIVED_IN_ORDINARY_APP';record['ordinaryRecipientTested']=bool(receiver and len(receiver.results)==(2 if a.stage=='audio' else 5 if a.stage=='ai' and whole_delivery and env.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1' else 1 if a.stage=='ai' else 3))
  if a.stage=='actions':record['state']='REAL_NATIVE_ACTION_REVIEW_FOLLOWUP_AND_COPY_PASSED';record['remoteOwnedWindowFocused']=True
  if env.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1':
   assert record['ordinaryRecipientTested'] and all(row.get('browserAttachment',{}).get('trustedNativePaste') and row['browserAttachment']['sha256']==row['sha256'] for row in receiver.results)
   record['standardBrowserAttachmentsReceivedByteIdentical']=True
 except BaseException as error:
  record.update(state='NATIVE_WORKFLOW_STOPPED_RETAINED',error=repr(error));save();raise
 finally:
  if receiver:receiver.request_close()
  for p in processes:
   if p.pid==record.get('appPid'):
    for window in windows(desktop,p.pid) if desktop else []:U.PostMessageW(window['hwnd'],0x10,0,0)
  until=time.monotonic()+5
  while any(alive(p) for p in processes) and time.monotonic()<until:time.sleep(.1)
  if job:K.CloseHandle(job);job=None
  if receiver:record['receiverPreferencesRestoredIdentically']=receiver.restore_preferences_after_job_closed()
  for p in processes:K.CloseHandle(p.process)
  for log in logs:log.close()
  require(U.SetProcessWindowStation(old_station));require(U.SetThreadDesktop(old_desktop))
  record['testStationClipboardSequenceUnchangedAtObservation']=before_clip==U.GetClipboardSequenceNumber()
  record['ownerClipboardSequenceUnchangedAtObservation']=None if DEDICATED_CI else record['testStationClipboardSequenceUnchangedAtObservation']
  record['remotePickerFocusUsed']=any(json.loads(path.read_text(encoding='utf8')).get('focusWithinOwnedRemotePickerUsed',False) for path in out.glob('dialog-reply-*.json'))
  record['keyboardMouseOrForegroundControlUsed']=bool(receiver and receiver.remote_input_used) or record['remotePickerFocusUsed'] or bool(DEDICATED_CI and a.stage=='actions');record['ownerKeyboardMouseOrForegroundControlUsed']=False
  if desktop and not DEDICATED_CI:U.CloseDesktop(desktop)
  if not DEDICATED_CI:U.CloseWindowStation(station)
  K.CloseHandle(low);record['finishedAt']=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds');save()
 print(json.dumps({'state':record['state'],'evidence':str(out),'privateStation':name,'ownerClipboardSequenceUnchangedAtObservation':record['ownerClipboardSequenceUnchangedAtObservation'],'wholeCoreCandidateQualified':False},ensure_ascii=False))
if __name__=='__main__':main()
