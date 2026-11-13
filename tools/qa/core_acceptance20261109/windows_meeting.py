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
from candidate_contract import grouped_meeting_candidate

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
 parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['inspect','handoff','audio','ai','transcribe','actions','context','documents','editing','incoming','product','product-background'],default='inspect');parser.add_argument('--library',type=Path);parser.add_argument('--audio',type=Path);parser.add_argument('--reviewed-ai',type=Path);a=parser.parse_args()
 public_import=None
 if os.environ.get('COMPANION_ACCEPTANCE_PUBLIC_SOURCE_IMPORT'):
  assert a.stage=='product-background' and a.audio and not DEDICATED_CI
  public_import=json.loads(Path(os.environ['COMPANION_ACCEPTANCE_PUBLIC_SOURCE_IMPORT']).read_text(encoding='utf8'))
  assert public_import['audioSha256']=='d6ab13a19fec81df257036b5cdc19eb47aea7c96fb140e3bd3f6977e84586347' and sha(a.audio)==public_import['audioSha256']
  assert public_import['durationSeconds']==1800 and public_import['publicSourceOnly'] is True
  assert sha(Path(public_import['localModelRoot'])/'ct-transformer-punctuation-zh-en-2024/model.onnx')=='e93593a6dbd69a07f8734ef269dbe861a379755f8d1c8354719432116f2c44bd'
 psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
 low=K.CreateMemoryResourceNotification(0);require(low);value=w.BOOL();require(K.QueryMemoryResourceNotification(low,ctypes.byref(value)));assert not value.value,'Actual Windows low-memory signal; no app launched'
 if a.stage in {'documents','incoming'}:
  fixture_root=Path(__file__).parent/'fixtures/document-context';fixture_manifest=json.loads((fixture_root/'manifest.json').read_text(encoding='utf8'));failures=[]
  for name,item in fixture_manifest.items():
   file=fixture_root/name
   if not file.is_file():failures.append(name+': missing')
   elif file.stat().st_size!=item['bytes'] or sha(file)!=item['sha256']:failures.append(name+': identity mismatch')
  assert not failures,'Complete public document fixture preflight failed: '+repr(failures)
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
 (out/'plan.json').write_text(json.dumps({'sessionId':session['id'],'title':session['title'],'sourceMeeting':prior['sourceMeeting'] if a.library else 'S_R004S03C01' if a.stage=='ai' else None,'selectedNoteId':(session.get('meetingNotes') or [{}])[0].get('id'),'expectedManualDocument':session['minutesByMode']['offlineStore']['markdown'],'realAsrInput':bool(a.library) or a.stage=='ai','requireGroupedUi':grouped_meeting_candidate(v['version']),'wholeMeetingDelivery':whole_delivery,'browserAttachments':whole_delivery and os.environ.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1','aiChunks':session['minutes']['processing']['totalChunks'] if whole_delivery else 2,'expectedExportContains':session['minutes']['summary'][0][:50] if whole_delivery else None},ensure_ascii=False),encoding='utf8')
 if a.stage=='actions':
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan['savedActionCount']=len(session['minutes']['actionItems']);(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage in {'audio','transcribe','context','editing'}:
  assert a.audio and sha(a.audio)=='82ac9f8b25e2c085b2e0434e444727af0577e373ed5e1f587d3f28881862fe2f'
  (root/'exports').mkdir();plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan.update(audioInput=str(a.audio.resolve()),audioSha256=sha(a.audio),audioTitle=a.audio.stem,audioSeconds=2327.119,exportDirectory=str(root/'exports'),receivedDirectory=str(root/'received-files'),wholeMeetingAsr=a.stage=='transcribe')
  (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage=='ai' and whole_delivery and os.environ.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1':
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan['desktopPrimaryFileCopy']=v['version']=='0.1.81'
  (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage=='context':
  assert DEDICATED_CI,'Native picker context flow belongs to a disposable CI machine'
  public=Path(__file__).parent/'fixtures/public-whiteboard124.png';assert sha(public)=='96d134af463a7b50fa6377fd988fbaa20ec8a9a02fafbda31e9c15dd2b855855'
  received=root/'received-files';received.mkdir();image=received/'Companion-public-whiteboard083.png';bad=received/'Companion-public-invalid083.png';shutil.copy2(public,image);bad.write_text('This is not a raster image. Explicit public test fixture.')
  # The unrelated control is an honest text-only fixture, with no missing board audio.
  session.update(source='importedTranscript',audioPath=None,audioStored=False,audioBytes=0,chunks=[],deviceRecordingId=None,deviceRecordingKey=None,sourceDeviceId=None,meetingTracks=None)
  session['retention']['audioCached']=False;(state/'sessions.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan.update(appVersion=v['version'],imageInput=str(image),imageSha256=sha(image),invalidImage=str(bad),invalidImageSha256=sha(bad),statePath=str(state/'sessions.json'),recordingDirectory=str(root/'recordings'));(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage=='editing':
  assert DEDICATED_CI
  session.update(source='importedTranscript',audioPath=None,audioStored=False,audioBytes=0,chunks=[],deviceRecordingId=None,deviceRecordingKey=None,sourceDeviceId=None,meetingTracks=None)
  session['retention']['audioCached']=False;(state/'sessions.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan.update(appVersion=v['version'],statePath=str(state/'sessions.json'),recordingDirectory=str(root/'recordings'));(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage in {'product','product-background'}:
  if a.stage=='product':assert DEDICATED_CI,'Complete native product workflow belongs to the disposable CI machine'
  else:assert not DEDICATED_CI,'Background product scope requires its private noninteractive station'
  session.update(source='importedTranscript',audioPath=None,audioStored=False,audioBytes=0,chunks=[],deviceRecordingId=None,deviceRecordingKey=None,sourceDeviceId=None,meetingTracks=None)
  session['retention']['audioCached']=False
  presented='# '+session['title']+'\n\nGenerated: 2026-11-12T01:00:00Z\nDuration: 12000 ms\nSource: importedTranscript\nMinutes engine: llm_deepseek (final)\n\n'+text
  session['minutes'].update(markdown=presented,source='userEdited')
  session['minutesByMode']['offlineStore'].update(markdown=presented,source='userEdited')

  session['meetingNotes'][0]['text']='EXCLUDED_CORE_NOTE_20261109 不选择的个人草稿'
  control=json.loads(json.dumps(session));control.update(id='core-product-unrelated',title='明确虚构·不参与本次操作的记录');sessions.append(control)
  # Match the native serializer's representation before the first save so the
  # unrelated-row byte comparison detects content changes, not omitted empty
  # legacy fixture fields. Only these known empty optional fields are omitted.
  for fixture_row in sessions:
   for key in ['deviceRecordingId','deviceRecordingKey','sourceDeviceId','meetingTracks']:
    if fixture_row.get(key) is None:fixture_row.pop(key,None)
   for key in ['calendarCopies','calendarSlotCopies']:
    if fixture_row.get(key)==[]:fixture_row.pop(key,None)
  (state/'sessions.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
  (root/'exports').mkdir() # The ordinary Shell receiver creates its own empty destination.
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan.update(appVersion=v['version'],backgroundOnly=a.stage=='product-background',verifyDateOnly=os.environ.get('COMPANION_ACCEPTANCE_VERIFY_DATE_ONLY')=='1',exportDirectory=str(root/'exports'),receivedDirectory=str(root/'received-files'),statePath=str(state/'sessions.json'),recordingDirectory=str(root/'recordings'));(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage in {'documents','incoming'}:
  assert DEDICATED_CI,'Document native pickers only on the disposable CI machine'
  session.update(source='importedTranscript',audioPath=None,audioStored=False,audioBytes=0,chunks=[],deviceRecordingId=None,deviceRecordingKey=None,sourceDeviceId=None,meetingTracks=None)
  session['retention']['audioCached']=False
  (state/'sessions.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
  control=json.loads(json.dumps(session));control.update(id='core-public-document-unrelated',title='明确虚构·不参与本次材料操作的记录');control.pop('documentContext',None);sessions.append(control);(state/'sessions.json').write_text(json.dumps(sessions,ensure_ascii=False),encoding='utf8')
  source=Path(__file__).parent/'fixtures/document-context';manifest=json.loads((source/'manifest.json').read_text(encoding='utf8'))
  received=root/'received-files';received.mkdir();(root/'exports').mkdir();inputs=[]
  for name,expected in [('material.docx','预算草案为12000元'),('material.xlsx','12,000.00'),('material.pptx','第一张'),('chinese.pdf','预算12000元'),('protected.pdf',None),('no-text.pdf',None),('material-gb.txt','人工')]:
   assert sha(source/name)==manifest[name]['sha256'];shutil.copy2(source/name,received/name);inputs.append({'name':name,'path':str(received/name),'sha256':manifest[name]['sha256'],'expected':expected})
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan.update(appVersion=v['version'],documentInputs=inputs,exportDirectory=str(root/'exports'),receivedDirectory=str(received),statePath=str(state/'sessions.json'),recordingDirectory=str(root/'recordings'));(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
 if a.stage=='incoming':
  import wave
  assert DEDICATED_CI
  audio=received/'公开接收100.wav';long_audio=received/'公开长文件取消100.wav'
  for destination,seconds in [(audio,2),(long_audio,7200)]:
   with wave.open(str(destination),'wb') as sound:
    sound.setnchannels(1);sound.setsampwidth(2);sound.setframerate(16000)
    for _ in range(seconds):sound.writeframesraw(bytes([1,0])*16000)
  image=received/'公开白板100.png';public=Path(__file__).parent/'fixtures/public-whiteboard124.png';assert sha(public)=='96d134af463a7b50fa6377fd988fbaa20ec8a9a02fafbda31e9c15dd2b855855';shutil.copy2(public,image)
  broken=received/'公开坏文件100.wav';broken.write_bytes(b'PUBLIC_INVALID_AUDIO_NOT_A_MEETING')
  plan.update(incomingAudio=str(audio),incomingAudioSha256=sha(audio),incomingLong=str(long_audio),incomingLongSha256=sha(long_audio),incomingImage=str(image),incomingImageSha256=sha(image),incomingBad=str(broken),incomingBadSha256=sha(broken),appExecutable=str(app/'companion-type.exe'),privateRoot=str(root))
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
 if a.stage=='incoming':record['inputKind']='Public generated PCM (2s import and2h cancellation) plus official engineering DOCX/PNG fixtures; not speech, ASR, meeting accuracy or hardware qualification'
 if a.stage=='audio':record['inputKind']='Actual public S_R004S03C01 audio; native import, playback and export only, no ASR/AI or capture'
 if a.stage in {'ai','actions'}:record['inputKind']='Actual cached public AI minutes after declared manual source review; ordinary reading and export, no new cloud request or ASR'
 if whole_delivery:record['inputKind']='The same actual public imported audio and new fixed-product ASR, followed by actual cloud AI; reading/audio playback/document receipt and restoration continuation, no new ASR/cloud call in this UI stage'
 if a.stage=='transcribe':record.update(inputKind='Actual public S_R004S03C01 audio through the fixed current product CPU ASR; no training, provider substitution or cloud audio',modelsRun=True,modelResearchOrTrainingRun=False)
 if public_import:
  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan['publicSourceImport']=public_import;(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
  record.update(inputKind='Verified public AISHELL4 source30m opened by the ordinary native incoming-file workflow, explicitly stored as a new recording and transcribed with fixed local ASR; software path only, no acoustic or board qualification.',modelsRun=True,sourceAudioSha256=public_import['audioSha256'],cloudAudioUploaded=False,modelResearchOrTrainingRun=False)
 name=station_name() if DEDICATED_CI else 'CompanionCore-'+token
 station=old_station if DEDICATED_CI else require(U.CreateWindowStationW(name,0,0x37f,None));desktop=None;job=None;processes=[];logs=[];receiver=None;handled=set();dialog_workers={}
 try:
  require(U.SetProcessWindowStation(station));desktop=old_desktop if DEDICATED_CI else require(U.CreateDesktopW('Meeting',None,None,0,0x1ff,None));require(U.SetThreadDesktop(desktop));assert station_name()==name
  desktop_path=name+'\\'+object_name(desktop)
  record['privateStation']=name;record['stationVerifiedBeforeLaunch']=True
  record['desktopIsolation']='Dedicated disposable GitHub Windows runner; no owner desktop' if DEDICATED_CI else 'Private noninteractive window station on owner PC'
  job=require(K.CreateJobObjectW(None,None));limit=ExtendedLimits();limit.BasicLimitInformation.LimitFlags=0x2000|0x200;limit.JobMemoryLimit=(3072 if DEDICATED_CI and (a.stage=='transcribe' or os.environ.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1') else 2048 if public_import else 1536)*1024**2;require(K.SetInformationJobObject(job,9,ctypes.byref(limit),ctypes.sizeof(limit)));cpu=CpuRate(0x1|0x4,CPU_PERCENT*100);require(K.SetInformationJobObject(job,15,ctypes.byref(cpu),ctypes.sizeof(cpu)));record['cpuHardCapPercent']=CPU_PERCENT;record['ownJobPrivateCommitLimitBytes']=limit.JobMemoryLimit
  env={**os.environ,'APPDATA':str(root/'roaming'),'LOCALAPPDATA':str(root/'local'),'TEMP':str(root/'temp'),'TMP':str(root/'temp'),'COMPANION_TYPE_STATE_PATH':str(state/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(root/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json'),'COMPANION_TYPE_BACKGROUND_WINDOW':'1','COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1','COMPANION_TYPE_WEBVIEW_ARGS':f'--remote-debugging-port={port} --mute-audio --disable-gpu','WEBVIEW2_USER_DATA_FOLDER':str(root/'webview')}
  for key in ['DEEPSEEK_API_KEY','OPENAI_API_KEY','COMPANION_TYPE_ASR_API_KEY','COMPANION_TYPE_VOLC_APP_KEY','COMPANION_TYPE_VOLC_ACCESS_KEY','GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:env.pop(key,None)
  reopen_from=os.environ.get('COMPANION_ACCEPTANCE_REOPEN_FROM_EVIDENCE')
  if reopen_from:
   assert a.stage=='product-background' and not DEDICATED_CI and env.get('COMPANION_TYPE_BLE_NATIVE_DISABLED')=='1'
   prior_evidence=Path(reopen_from).resolve();previous=json.loads(prior_evidence.read_text(encoding='utf8'));previous_root=Path(previous['privateRoot']).resolve()
   assert previous_root.is_relative_to(D.parent.parent.resolve()) and previous['inputKind'].startswith('explicit fictional text-only') and previous['firstAppExitObserved'] is True
   assert previous['frozenAppSource']==v['sourceCommit'] and previous['exeSha256']==v['embeddedExeSha256']
   env.update(APPDATA=str(previous_root/'roaming'),LOCALAPPDATA=str(previous_root/'local'),TEMP=str(previous_root/'temp'),TMP=str(previous_root/'temp'),COMPANION_TYPE_STATE_PATH=str(previous_root/'state/sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(previous_root/'recordings'),COMPANION_TYPE_PRODUCT_SETTINGS_PATH=str(previous_root/'product-settings.json'),WEBVIEW2_USER_DATA_FOLDER=str(previous_root/'webview'))
   restart_plan=json.loads((prior_evidence.parent/'plan.json').read_text(encoding='utf8'));restart_plan.update(expectedSnapshot=json.loads((previous_root/'state/sessions.json').read_text(encoding='utf8')),previousAppExited=True,firstPid=previous['firstAppPid'])
   record.update(reopenedPreviousEvidence=str(prior_evidence),reopenedPreviousPrivateRoot=str(previous_root));save()
  if a.audio:env['COMPANION_ACCEPTANCE_AUDIO_INPUT']=str(a.audio.resolve())
  if public_import:env.update(COMPANION_TYPE_LOCAL_ASR_DIR=public_import['localModelRoot'],COMPANION_TYPE_ASR_CACHE_DIR=str(root/'asr-cache'))
  if a.stage=='transcribe':
   assert DEDICATED_CI and os.environ.get('COMPANION_ACCEPTANCE_FIXED_ASR_ROOT'),'Fixed product inference only on the dedicated runner'
   env['COMPANION_TYPE_LOCAL_ASR_DIR']=os.environ['COMPANION_ACCEPTANCE_FIXED_ASR_ROOT']
  if a.stage in {'actions','context','documents','editing','incoming','product'}:
   assert DEDICATED_CI,'The normal visible-window clipboard journey runs only on an owned dedicated CI runner'
   env['COMPANION_TYPE_BACKGROUND_WINDOW']='0'
   record['normalVisibleWindowOnDedicatedRunner']=True
  if a.stage=='product-background':
   assert not DEDICATED_CI and name.startswith('CompanionCore-') and station_name()==name and name.lower()!='winsta0'
   # A visible WebView within this inaccessible station remains off the Owner desktop.
   env['COMPANION_TYPE_BACKGROUND_WINDOW']='0'
   record.update(noninteractiveProductScope=True,normalVisibleWindowOnDedicatedRunner=False,nativeSaveCancelOrOrdinaryRecipientRetested=False)
  real_public=os.environ.get('COMPANION_ACCEPTANCE_REAL_PUBLIC_SPEC')
  if real_public:
   assert a.stage=='product-background' and env.get('COMPANION_TYPE_BLE_NATIVE_DISABLED')=='1'
   specification=json.loads(Path(real_public).read_text(encoding='utf8'))
   source_state=Path(specification['statePath']);source_rows=json.loads(source_state.read_text(encoding='utf8'))
   expected_id=specification.get('sessionId','v1-real-installed-1794533232243')
   expected_key=specification.get('recordingKey',{'deviceUid':'120011000d50335754363720','formatEpoch':'5a6584e1707422bb','sessionId':'000000000000019f'})
   assert len(source_rows)==1 and source_rows[0]['id']==expected_id
   assert source_rows[0].get('deviceRecordingKey')==expected_key
   source_kind=specification.get('sourceKind','boardDevice');assert source_kind in {'boardDevice','importedAudio'}
   assert sha(source_state)==specification['stateSha256'] and source_rows[0]['source']==source_kind
   assert source_rows[0]['transcriptFinal']
   if specification.get('retranscriptionOnly'):
    # Bind every fresh public run to its completed capture receipt below;
    # never reopen the interrupted meeting capture or private old recording.
    assert specification['recordingKey']['sessionId'] not in ['00000000000001a3','000000000000019e']
    env['COMPANION_TYPE_LOCAL_ASR_DIR']=specification['localModelRoot']
    record['modelsRun']=True
   else:assert source_rows[0]['minutesByMode']['offlineStore']['source']=='llm_deepseek'
   if source_kind=='boardDevice':
    capture=json.loads(Path(specification['captureReceipt']).read_text(encoding='utf8'));assert capture['ownHandlesClosed'] and capture['release']['result']=='TURN_RELEASED'
    assert any(stage.get('sessionId')==expected_id and stage.get('recordingKey')==expected_key
     and stage.get('state')=='NATIVE_ORIGINAL_SAVED' for stage in capture['stages'])
   else:
    imported=json.loads(Path(specification['nativeImportEvidence']).read_text(encoding='utf8'))
    manifest=json.loads(Path(specification['nativeImportManifest']).read_text(encoding='utf8'))
    assert imported['state']=='REAL_NATIVE_PUBLIC_SOURCE_IMPORT_LOCAL_ASR_AND_REOPEN_PASSED' and imported['processRestart']['allPublicLibraryRowsUnchanged']
    assert imported['ui']['newAsrRun'] and imported['ui']['cloudCalls']==0 and imported['ui']['sessionId']==expected_id
    assert manifest['sourceAudioSha256']=='d6ab13a19fec81df257036b5cdc19eb47aea7c96fb140e3bd3f6977e84586347' and sha(Path(manifest['originalPath']))==manifest['sourceAudioSha256']
    assert manifest['sessionId']==expected_id and source_rows[0]['audioPath']==manifest['decodedPath'] and sha(Path(manifest['decodedPath']))==manifest['decodedAudioSha256']
    assert hashlib.sha256(source_rows[0]['transcriptText'].encode('utf8')).hexdigest()==manifest['transcriptSha256']
    upstream=Path(specification['upstreamStatePath']);assert upstream==Path(imported['privateRoot'])/'state/sessions.json'
    imported_rows=[row for row in json.loads(upstream.read_text(encoding='utf8')) if row['id']==expected_id]
    if specification.get('nativeRegenerationReceipt'):
     regeneration_path=Path(specification['nativeRegenerationReceipt']);regeneration=json.loads(regeneration_path.read_text(encoding='utf8'))
     assert regeneration['state']=='PUBLIC_NATIVE129_FIVE_POINT_OVERVIEW_REGENERATED_AND_CONTENT_READ'
     assert regeneration['publicOnly'] and regeneration['cloudTextOnly'] and regeneration['previousStateUntouched'] and regeneration['originalTranscriptUnchanged']
     assert regeneration['sourceTextSha256']==manifest['transcriptSha256']
     assert len(imported_rows)==1
     result_fields={'minutes','minutesByMode','exportMarkdown','exportedAt'}
     assert {k:v for k,v in source_rows[0].items() if k not in result_fields}=={k:v for k,v in imported_rows[0].items() if k not in result_fields}
     regenerated_state=regeneration_path.parent/'sessions.json'
     assert source_rows==json.loads(regenerated_state.read_text(encoding='utf8'))
     assert source_rows[0]==json.loads((regeneration_path.parent/'minutes.json').read_text(encoding='utf8'))
    else:assert source_rows==imported_rows
   for file,digest in specification['originalAudioFiles'].items():assert sha(Path(specification['recordingDir'])/file)==digest
   (state/'sessions.json').write_text(json.dumps(source_rows,ensure_ascii=False),encoding='utf8')
   plan.update(sessionId=source_rows[0]['id'],title=source_rows[0]['title'],realPublicReview=True,realPublicSpec=specification,statePath=str(state/'sessions.json'),expectedSnapshot=source_rows)
   (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')
   env['COMPANION_TYPE_RECORDING_DIR']=specification['recordingDir']
   record.update(inputKind=('Verified public-source ordinary native import, actual local ASR and configured text-only DeepSeek results; software reading only, no acoustic/board claim.' if source_kind=='importedAudio' else 'Exact declared new public acoustic recording with actual fixed-product ASR and configured DeepSeek results; isolated UI reads same recording originals. No reference transcription or fabricated result.'),realPublicSessionId=source_rows[0]['id'],realPublicSourceStateSha256=specification['stateSha256'],realPublicSpecification=real_public)
  log=(out/'app.log').open('wb');logs.append(log);p=spawn([app/'companion-type.exe',public_import['audioInput']] if public_import else [app/'companion-type.exe',plan['incomingAudio']] if a.stage=='incoming' else [app/'companion-type.exe'],env,app,desktop_path,job,log);processes.append(p);record['appPid']=p.pid;record['state']='STARTING_PRIVATE_NATIVE_APP';save()
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
      expected_profile=Path(env['WEBVIEW2_USER_DATA_FOLDER']).resolve()
      profiles.append({'pid':child.pid,'folder':folder,'matchesPrivateRoot':Path(folder).resolve() in {expected_profile,expected_profile/'EBWebView'},'belongsToBoundedJob':bool(in_job.value),'cdpListener':child.pid in listeners})
   except psutil.NoSuchProcess:continue
  record['observedWebviewProfiles']=profiles;save()
  assert any(item['cdpListener'] for item in profiles) and all(item['matchesPrivateRoot'] and item['belongsToBoundedJob'] for item in profiles),'Actual CDP browser is not proven in the private profile and bounded job';record['webviewProfileVerifiedPrivate']=True
  if reopen_from:
   restart_plan['reopenedPid']=p.pid;(out/'plan.json').write_text(json.dumps(restart_plan,ensure_ascii=False),encoding='utf8')
  log=(out/'ui.log').open('wb');logs.append(log);node=spawn([shutil.which('node'),S/'tools/qa/core_acceptance20261109/windows_meeting_ui.cjs',str(port),str(out),'product-reopen' if reopen_from else a.stage],env,S,desktop_path,job,log);processes.append(node)
  deadline=time.monotonic()+(1200 if a.stage=='transcribe' else 480 if a.stage in {'audio','context','documents','editing','incoming','product','product-background'} else 180)
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
    if a.stage=='product-background':
     assert not DEDICATED_CI and station_name()==name and name.lower()!='winsta0'
     # Tauri resolves Windows KnownFolder cache independently of LOCALAPPDATA
     # overrides. Inspect only this station's newly generated public-fixture file,
     # never enumerate or read other contents of the ordinary application cache.
     cache_root=(Path(os.environ['LOCALAPPDATA'])/json.loads((S/'apps/windows/src-tauri/tauri.conf.json').read_text(encoding='utf8'))['identifier']/'content-share').resolve()
     assert not source.is_symlink() and not source.parent.is_symlink()
     assert source.resolve().parent.parent==cache_root
     assert str(uuid.UUID(source.parent.name))==source.parent.name
     assert source.stat().st_mtime>=datetime.fromisoformat(record['at']).timestamp()-1 and source.stat().st_size<1024**2
     record.update(publicFixtureExportCache=str(source),appCacheUsesWindowsKnownFolder=True,testOnlyFileCreatedOutsidePrivateRoot=True)
     text=source.read_text(encoding='utf8');assert data['expected'] in text and data['excluded'] not in text
     received=dict(fileName=source.name,sha256=sha(source),bytes=source.stat().st_size,actualPackagedAppFileCreated=True,privateStationClipboardObserved=True,selectedContentsVerified=True,ordinaryRecipientTested=False)
     record.setdefault('privateExportFiles',[]).append(received)
     (out/request.name.replace('handoff-request-','handoff-reply-')).write_text(json.dumps(received,ensure_ascii=False),encoding='utf8');handled.add(request.name);save();continue
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
     elif a.stage=='product':assert data['expected'] in text and data['excluded'] not in text
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
    # CF_UNICODETEXT uses Windows CRLF. Compare only that representation change;
    # words, spaces, item selection and uncertainty must remain exact.
    comparison={'byteExactTextMatch':actual==expected,'matchesAfterWindowsCrLfOnly':actual.replace('\r\n','\n')==expected,'actualCharacters':len(actual),'expectedCharacters':len(expected),'actualCrLf':actual.count('\r\n'),'expectedCrLf':expected.count('\r\n'),'actualSha256':hashlib.sha256(actual.encode('utf8')).hexdigest(),'expectedSha256':hashlib.sha256(expected.encode('utf8')).hexdigest()}
    (out/'text-clipboard-comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf8')
    assert comparison['matchesAfterWindowsCrLfOnly'],'Actual Windows clipboard differs beyond the Windows newline representation'
    result={'actualWindowsUnicodeClipboardMatched':True,**comparison,'scope':'Only the public draft copied by the immediately preceding ordinary button; no original owner clipboard read. CRLF-to-LF comparison only.'}
    (out/'text-clipboard-reply.json').write_text(json.dumps(result),encoding='utf8');handled.add(request.name)
   time.sleep(.25)
  assert not alive(node),'UI workflow exceeded its bounded stage timeout';code=w.DWORD();require(K.GetExitCodeProcess(node.process,ctypes.byref(code)));assert code.value==0,(out/'ui.log').read_text(encoding='utf8',errors='replace')[-1800:]
  if os.environ.get('COMPANION_ACCEPTANCE_OWNER_PREFLIGHT')=='1':
   assert a.stage=='product-background' and not DEDICATED_CI and env.get('COMPANION_TYPE_BLE_NATIVE_DISABLED')=='1'
   first=next(process for process in processes if process.pid==record['appPid']);snapshot=json.loads((state/'sessions.json').read_text(encoding='utf8'))
   for window in windows(desktop,first.pid):require(U.PostMessageW(window['hwnd'],0x10,0,0))
   deadline=time.monotonic()+15
   while alive(first) and time.monotonic()<deadline:time.sleep(.1)
   assert not alive(first),'Normal owned app close did not exit; no forced Owner-desktop fallback'
   deadline=time.monotonic()+10
   while time.monotonic()<deadline:
    try:
     with socket.create_connection(('127.0.0.1',port),timeout=.3):pass
    except OSError:break
    time.sleep(.1)
   else:raise AssertionError('Previous private WebView listener did not exit')
   record.update(state='FIRST_NATIVE_PROCESS_EXITED_REOPEN_CHECK_RUNNING',firstAppPid=first.pid,firstAppExitObserved=True);save()
   reopened=out/'process-reopen';reopened.mkdir();log=(reopened/'app.log').open('wb');logs.append(log)
   second=spawn([app/'companion-type.exe'],env,app,desktop_path,job,log);processes.append(second);record['appPid']=second.pid;save()
   deadline=time.monotonic()+45
   while time.monotonic()<deadline:
    assert alive(second),'Reopened native app exited before its UI was ready'
    try:
     with local_http.open(f'http://127.0.0.1:{port}/json/version',timeout=1) as response:json.load(response)
     break
    except Exception:time.sleep(.2)
   else:raise TimeoutError('Reopened private WebView did not become ready')
   restart_plan=json.loads((out/'plan.json').read_text(encoding='utf8'));restart_plan.update(expectedSnapshot=snapshot,previousAppExited=True,firstPid=first.pid,reopenedPid=second.pid)
   (reopened/'plan.json').write_text(json.dumps(restart_plan,ensure_ascii=False),encoding='utf8')
   log=(reopened/'ui.log').open('wb');logs.append(log);check=spawn([shutil.which('node'),S/'tools/qa/core_acceptance20261109/windows_meeting_ui.cjs',str(port),str(reopened),'product-reopen'],env,S,desktop_path,job,log);processes.append(check)
   deadline=time.monotonic()+90
   while alive(check) and time.monotonic()<deadline:resources();time.sleep(.2)
   assert not alive(check),'Restart UI verification exceeded its bounded deadline'
   exit_code=w.DWORD();require(K.GetExitCodeProcess(check.process,ctypes.byref(exit_code)));assert exit_code.value==0,(reopened/'ui.log').read_text(encoding='utf8',errors='replace')[-1800:]
   record['processRestart']=json.loads((reopened/'ui-result.json').read_text(encoding='utf8'));assert record['processRestart']['previousAppExited'] and record['processRestart']['allPublicLibraryRowsUnchanged']
  record['ui']=json.loads((out/'ui-result.json').read_text(encoding='utf8'));record['state']='NATIVE_PRIVATE_UI_INSPECTED' if a.stage=='inspect' else 'REAL_NATIVE_PUBLIC_AUDIO_FLOW_PASSED' if a.stage=='audio' else 'REAL_NATIVE_FIXED_PRODUCT_AUDIO_TRANSCRIPTION_PASSED' if a.stage=='transcribe' else 'REAL_NATIVE_REVIEWED_AI_READING_AND_HANDOFF_PASSED' if a.stage=='ai' else 'REAL_NATIVE_MEETING_SELECTED_FILES_RECEIVED_IN_ORDINARY_APP';record['ordinaryRecipientTested']=bool(receiver and len(receiver.results)==(2 if a.stage=='audio' else 5 if a.stage=='ai' and whole_delivery and env.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1' else 1 if a.stage in {'ai','product'} else 3))
  if a.stage=='product':record['state']='REAL_NATIVE_COHERENT_PRODUCT_JOURNEY_PASSED';record['remoteOwnedWindowFocused']=True
  if a.stage=='product-background':record['state']='REAL_NATIVE_COHERENT_BACKGROUND_PRODUCT_JOURNEY_PASSED';record['remoteOwnedWindowFocused']=False
  if public_import:record['state']='REAL_NATIVE_PUBLIC_SOURCE_IMPORT_LOCAL_ASR_AND_REOPEN_PASSED'
  if a.stage=='context':record['state']='REAL_NATIVE_RECORDING_IMAGE_CONTEXT_AND_SELECTED_ZIP_PASSED';record['remoteOwnedWindowFocused']=True
  if a.stage=='editing':record['state']='REAL_NATIVE_AUDIO_EDITING_UI_PASSED';record['remoteOwnedWindowFocused']=True
  if a.stage=='documents':record['state']='REAL_NATIVE_DOCUMENT_CONTEXT_UI_PASSED';record['remoteOwnedWindowFocused']=True
  if a.stage=='incoming':record['state']='REAL_NATIVE_OS_INCOMING_FILE_WORKFLOW_PASSED';record['remoteOwnedWindowFocused']=True
  if a.stage=='actions':record['state']='REAL_NATIVE_ACTION_REVIEW_FOLLOWUP_AND_COPY_PASSED';record['remoteOwnedWindowFocused']=True
  if reopen_from:record.update(state='REAL_NATIVE_PROCESS_REOPEN_SCOPE_PASSED',processRestart=record['ui'])
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
  record['keyboardMouseOrForegroundControlUsed']=bool(receiver and receiver.remote_input_used) or record['remotePickerFocusUsed'] or bool(DEDICATED_CI and a.stage in {'actions','context','documents','editing','incoming','product'});record['ownerKeyboardMouseOrForegroundControlUsed']=False
  if desktop and not DEDICATED_CI:U.CloseDesktop(desktop)
  if not DEDICATED_CI:U.CloseWindowStation(station)
  K.CloseHandle(low);record['finishedAt']=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds');save()
 print(json.dumps({'state':record['state'],'evidence':str(out),'privateStation':name,'ownerClipboardSequenceUnchangedAtObservation':record['ownerClipboardSequenceUnchangedAtObservation'],'wholeCoreCandidateQualified':False},ensure_ascii=False))
if __name__=='__main__':main()
