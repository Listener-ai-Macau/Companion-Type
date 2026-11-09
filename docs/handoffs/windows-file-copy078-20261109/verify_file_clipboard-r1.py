"""Build exact production module, then run its real clipboard test off WinSta0."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ctypes
from ctypes import wintypes as w
import hashlib,json,os,subprocess,sys,time,uuid
R=Path(__file__).resolve().parents[1]
C=R.parent/'docs/handoffs/20261109-windows-file-copy078';C.mkdir(parents=True,exist_ok=True)
D=Path('E:/CodexData/Companion/.build-cache/windows-file-copy078');D.mkdir(parents=True,exist_ok=True)
module=R/'apps/windows/src-tauri/src/file_clipboard.rs'
digest=hashlib.sha256(module.read_bytes()).hexdigest()
probe=D/'probe';(probe/'src').mkdir(parents=True,exist_ok=True)
(probe/'Cargo.toml').write_text('''[package]
name = "companion-file-clipboard078-proof"
version = "0.1.0"
edition = "2021"
[dependencies]
windows = { version = "=0.58.0", features = ["Win32_Foundation", "Win32_System_DataExchange", "Win32_System_Memory", "Win32_UI_Shell", "Win32_UI_WindowsAndMessaging", "Win32_Graphics_Gdi"] }
''',encoding='utf8')
(probe/'src/lib.rs').write_text('#[path = '+json.dumps(str(module).replace('\\','/'))+']\nmod file_clipboard;\n',encoding='utf8')
env={**os.environ,'CARGO_TARGET_DIR':str(D/'target'),'CARGO_BUILD_JOBS':'1','RAYON_NUM_THREADS':'1','TEMP':str(D),'TMP':str(D)}
start=time.perf_counter()
with (C/'native-compile.log').open('wb') as log:
 child=subprocess.Popen(['cargo','test','--offline','--no-run','--message-format=json'],cwd=probe,env=env,stdout=subprocess.PIPE,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 import psutil
 psutil.Process(child.pid).cpu_affinity([12,13]);exe=None
 for line in child.stdout:
  log.write(line)
  try:
   item=json.loads(line)
   if item.get('reason')=='compiler-artifact' and item.get('executable') and item.get('profile',{}).get('test'):exe=item['executable']
  except (ValueError,UnicodeError):pass
 assert child.wait()==0,(C/'native-compile.log').read_text(encoding='utf8',errors='replace')[-4000:]
assert exe and hashlib.sha256(module.read_bytes()).hexdigest()==digest
compile_seconds=time.perf_counter()-start
user=ctypes.WinDLL('user32',use_last_error=True)
for name,args,result in [
 ('GetProcessWindowStation',[],w.HANDLE),('SetProcessWindowStation',[w.HANDLE],w.BOOL),
 ('CreateWindowStationW',[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p],w.HANDLE),
 ('CloseWindowStation',[w.HANDLE],w.BOOL),('CreateDesktopW',[w.LPCWSTR,w.LPCWSTR,ctypes.c_void_p,w.DWORD,w.DWORD,ctypes.c_void_p],w.HANDLE),
 ('CloseDesktop',[w.HANDLE],w.BOOL),('GetClipboardSequenceNumber',[],w.DWORD)]:
 fn=getattr(user,name);fn.argtypes=args;fn.restype=result
old=user.GetProcessWindowStation();sequence=user.GetClipboardSequenceNumber();name='CompanionFileCopy078-'+uuid.uuid4().hex
station=user.CreateWindowStationW(name,0,0x37f,None)
assert station,ctypes.WinError(ctypes.get_last_error())
desktop=None
try:
 assert user.SetProcessWindowStation(station),ctypes.WinError(ctypes.get_last_error())
 try:desktop=user.CreateDesktopW('ClipboardTest',None,None,0,0x1ff,None)
 finally:assert user.SetProcessWindowStation(old)
 assert desktop,ctypes.WinError(ctypes.get_last_error())
 startup=subprocess.STARTUPINFO();startup.lpDesktop=name+'\\ClipboardTest'
 private={**env,'COMPANION_FILE_CLIPBOARD_TEST_STATION':name,'COMPANION_FILE_CLIPBOARD_TEST_DIR':str(D/'public-files')}
 test_start=time.perf_counter()
 result=subprocess.run([exe,'--ignored','--exact','file_clipboard::tests::content078_real_file_clipboard_is_exact_unicode_copy_and_preserves_source','--nocapture','--test-threads=1'],
  cwd=probe,env=private,startupinfo=startup,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 (C/'native-isolated-test.log').write_bytes(result.stdout+result.stderr)
 assert result.returncode==0,(result.stdout+result.stderr).decode('utf8',errors='replace')[-4000:]
 assert b'PASS real CF_HDROP' in result.stdout
 record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'state':'PASS_REAL_FILE_CLIPBOARD_PRIVATE_WINDOW_STATION',
  'exactProductionModule':str(module),'sourceSha256':digest,'testExe':exe,'testExeSha256':hashlib.sha256(Path(exe).read_bytes()).hexdigest(),
  'compileSeconds':compile_seconds,'testSeconds':time.perf_counter()-test_start,'privateStation':name,
  'ownerClipboardSequenceUnchangedAtObservation':sequence==user.GetClipboardSequenceNumber(),
  'ownerClipboardContentsRead':False,'interactiveWindowOpened':False,'keyboardOrMouseUsed':False,
  'ordinaryThirdPartyPasteQualified':False,'modelsRun':False,'productInstalled':False,
  'primarySources':['https://learn.microsoft.com/en-us/windows/win32/shell/clipboard','https://learn.microsoft.com/en-us/windows/win32/winstation/window-stations']}
 (C/'native-isolated-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(record,ensure_ascii=False),flush=True)
finally:
 if desktop:user.CloseDesktop(desktop)
 user.CloseWindowStation(station)
