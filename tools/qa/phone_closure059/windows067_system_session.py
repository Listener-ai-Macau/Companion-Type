"""Installed product on a new, never switched Windows QA desktop; public data only."""
from pathlib import Path
from ctypes import wintypes
import ctypes,hashlib,json,os,psutil,socket,time,uuid
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12'
F=P/'windows067-literal-and-rendering/system-handoff';F.mkdir(parents=True,exist_ok=True)
base=Path('E:/CodexData/Companion/.build-cache/windows051');C=base/('system-handoff067-'+uuid.uuid4().hex[:10]);C.mkdir()
exe=Path('C:/Program Files/Companion Type/companion-type.exe')
installation=json.loads((P/'windows067-literal-and-rendering/installation.json').read_text(encoding='utf8'))
assert hashlib.sha256(exe.read_bytes()).hexdigest()==installation['installedExeSha256']
assert not [p for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='companion-type.exe'],'Do not interfere with an existing daily product process'
for name in ['roaming','local','recordings','webview','temp','saved','Documents','Desktop','Downloads','Music','Pictures','Videos']:(C/name).mkdir()
prior=R/'docs/handoffs/20261105-windows-content051'
fixture=max((p for p in prior.glob('native-files-*') if (p/'public-session.json').exists()),key=lambda p:p.stat().st_mtime)
row=json.loads((fixture/'public-session.json').read_text(encoding='utf8'))[0]
for name in ['audioPath','deviceRecordingId','deviceRecordingKey','deviceTotalLength','deviceSha256','sourceDeviceId','recorderControl','meetingTracks']:row[name]=None
row.update(title='公开虚构Windows内容验收 · 非真实会议',audioStored=False,audioBytes=0,chunks=[],status='minutesReady',source='importedTranscript',pendingReason=None,captureIncomplete=False,recorderControlUncertain=False)
row['retention']['audioCached']=False;row['recovery'].update(intent='none',stage='idle',nextRetryAtUnixMs=None)
row['transcriptText']+='\n公开虚构验收：追加20%的费用尚未批准。小陈在11月8日前核对报价。\n# literal **keep** <A&B> 😀\n=HYPERLINK("https://example.invalid","literal")'
(C/'sessions.json').write_text(json.dumps([row],ensure_ascii=False),encoding='utf8');(C/'settings.json').write_text('{}',encoding='utf8')
(C/'public-seed.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
keep={'SYSTEMROOT','WINDIR','SYSTEMDRIVE','PATH','PATHEXT','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','PROGRAMDATA','PUBLIC','OS','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','COMSPEC'}
env={k:v for k,v in os.environ.items() if k.upper() in keep}
env.update(APPDATA=str(C/'roaming'),LOCALAPPDATA=str(C/'local'),USERPROFILE=str(C),TEMP=str(C/'temp'),TMP=str(C/'temp'),
 COMPANION_TYPE_STATE_PATH=str(C/'sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(C/'recordings'),COMPANION_TYPE_PRODUCT_SETTINGS_PATH=str(C/'settings.json'),
 COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1',COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED='0',
 WEBVIEW2_USER_DATA_FOLDER=str(C/'webview'),COMPANION_TYPE_WEBVIEW_ARGS=f'--remote-debugging-port={port}')
block=ctypes.create_unicode_buffer('\0'.join(f'{k}={v}' for k,v in sorted(env.items(),key=lambda item:item[0].upper()))+'\0\0')
class Startup(ctypes.Structure):
 _fields_=[('cb',wintypes.DWORD),('reserved',wintypes.LPWSTR),('desktop',wintypes.LPWSTR),('title',wintypes.LPWSTR),('x',wintypes.DWORD),('y',wintypes.DWORD),('xs',wintypes.DWORD),('ys',wintypes.DWORD),('xc',wintypes.DWORD),('yc',wintypes.DWORD),('fill',wintypes.DWORD),('flags',wintypes.DWORD),('show',wintypes.WORD),('reserved2',wintypes.WORD),('reservedP',ctypes.POINTER(ctypes.c_byte)),('stdin',wintypes.HANDLE),('stdout',wintypes.HANDLE),('stderr',wintypes.HANDLE)]
class Process(ctypes.Structure):
 _fields_=[('process',wintypes.HANDLE),('thread',wintypes.HANDLE),('pid',wintypes.DWORD),('tid',wintypes.DWORD)]
u=ctypes.WinDLL('user32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
u.CreateDesktopW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID];u.CreateDesktopW.restype=wintypes.HANDLE
u.CloseDesktop.argtypes=[wintypes.HANDLE];u.OpenInputDesktop.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];u.OpenInputDesktop.restype=wintypes.HANDLE
u.GetUserObjectInformationW.argtypes=[wintypes.HANDLE,ctypes.c_int,wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
k.CreateProcessW.argtypes=[wintypes.LPCWSTR,wintypes.LPWSTR,wintypes.LPVOID,wintypes.LPVOID,wintypes.BOOL,wintypes.DWORD,wintypes.LPVOID,wintypes.LPCWSTR,ctypes.POINTER(Startup),ctypes.POINTER(Process)];k.CreateProcessW.restype=wintypes.BOOL
k.CloseHandle.argtypes=[wintypes.HANDLE]
def input_desktop():
 handle=u.OpenInputDesktop(0,False,1);assert handle,ctypes.WinError(ctypes.get_last_error())
 try:
  name=ctypes.create_unicode_buffer(256);needed=wintypes.DWORD();assert u.GetUserObjectInformationW(handle,2,name,ctypes.sizeof(name),ctypes.byref(needed));return name.value
 finally:u.CloseDesktop(handle)
before_input=input_desktop();name='CompanionExportQA_'+uuid.uuid4().hex[:12];desk=u.CreateDesktopW(name,None,None,0,0x10000000,None);assert desk,ctypes.WinError(ctypes.get_last_error())
startup=Startup();startup.cb=ctypes.sizeof(startup);startup.desktop=name;proc=Process()
assert k.CreateProcessW(str(exe),ctypes.create_unicode_buffer('"'+str(exe)+'"'),None,None,False,0x00000400|0x08000000|0x00004000,block,str(exe.parent),ctypes.byref(startup),ctypes.byref(proc)),ctypes.WinError(ctypes.get_last_error())
owned=psutil.Process(proc.pid);created=owned.create_time()
meta={'pid':proc.pid,'createTime':created,'port':port,'desktop':name,'inputDesktopAtStart':before_input,'isolation':str(C),'expectedExeSha256':installation['installedExeSha256'],'exe':str(exe),'publicFixture':True,'noModelsOrBle':True,'desktopSwitched':False,'evidence':str(F)}
(F/'session.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(meta,ensure_ascii=False),flush=True)
try:
 deadline=time.monotonic()+2400
 while time.monotonic()<deadline and owned.is_running() and not (C/'stop-requested').exists():time.sleep(.5)
finally:
 if psutil.pid_exists(proc.pid):
  owned=psutil.Process(proc.pid);assert owned.create_time()==created and Path(owned.exe()).resolve()==exe.resolve()
  for child in owned.children(recursive=True):
   try:child.terminate()
   except psutil.NoSuchProcess:pass
  owned.terminate();owned.wait(timeout=15)
 k.CloseHandle(proc.thread);k.CloseHandle(proc.process);u.CloseDesktop(desk)
 (F/'session-closed.json').write_text(json.dumps({'ownProcessClosed':True,'inputDesktopAfter':input_desktop(),'initialInputDesktop':before_input,'desktopSwitchedByHarness':False,'modelsRun':False},indent=2),encoding='utf8')
 print('Own isolated product and desktop closed.',flush=True)
