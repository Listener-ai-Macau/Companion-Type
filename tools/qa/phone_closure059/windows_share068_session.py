"""Owner authorized a short foreground share test; normal installed product, public data."""
from pathlib import Path
import hashlib,json,os,psutil,subprocess,time,uuid,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';O=P/'windows-share068'
installed=json.loads((P/'windows067-literal-and-rendering/installation.json').read_text(encoding='utf8'));exe=Path('C:/Program Files/Companion Type/companion-type.exe')
assert hashlib.sha256(exe.read_bytes()).hexdigest()==installed['installedExeSha256']
assert not [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='companion-type.exe'],'Preserve existing product process'
C=Path('E:/CodexData/Companion/.build-cache/windows-share068')/('foreground-public-'+uuid.uuid4().hex[:10]);C.mkdir()
for name in ['roaming','local','recordings','webview','temp','saved','Documents','Desktop','Downloads','Music','Pictures','Videos']:(C/name).mkdir()
prior=json.loads((P/'windows067-literal-and-rendering/system-handoff/session.json').read_text(encoding='utf8'));seed=Path(prior['isolation'])/'public-seed.json';row=json.loads(seed.read_text(encoding='utf8'))
assert row['title']=='公开虚构Windows内容验收 · 非真实会议' and not row['audioStored']
(C/'sessions.json').write_text(json.dumps([row],ensure_ascii=False),encoding='utf8');(C/'public-seed.json').write_text(json.dumps(row,ensure_ascii=False),encoding='utf8');(C/'settings.json').write_text('{}',encoding='utf8')
keep={'SYSTEMROOT','WINDIR','SYSTEMDRIVE','PATH','PATHEXT','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','PROGRAMDATA','PUBLIC','OS','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','COMSPEC'}
env={k:v for k,v in os.environ.items() if k.upper() in keep}
normal_shell_environment='--normal-shell-environment' in sys.argv
env.update(APPDATA=str(C/'roaming'),LOCALAPPDATA=str(C/'local'),USERPROFILE=str(C),TEMP=str(C/'temp'),TMP=str(C/'temp'),
 COMPANION_TYPE_STATE_PATH=str(C/'sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(C/'recordings'),COMPANION_TYPE_PRODUCT_SETTINGS_PATH=str(C/'settings.json'),
 COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1',COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED='0',WEBVIEW2_USER_DATA_FOLDER=str(C/'webview'))
if normal_shell_environment:
 for key in ['APPDATA','LOCALAPPDATA','USERPROFILE','TEMP','TMP']:
  if key in os.environ:env[key]=os.environ[key]
  else:env.pop(key,None)
p=subprocess.Popen([str(exe)],cwd=exe.parent,env=env,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);owner=psutil.Process(p.pid);created=owner.create_time()
meta={'pid':p.pid,'createTime':created,'isolation':str(C),'exe':str(exe),'installedVersion':'0.1.67','publicSyntheticFixture':True,'foregroundAvailabilityExplicitlyConfirmed':True,'modelsRun':False,'bleDisabled':True,'normalWindowsShellEnvironment':normal_shell_environment}
if (O/'session.json').exists():(O/('session-prior-'+str(time.time_ns())+'.json')).write_bytes((O/'session.json').read_bytes())
(O/'session.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(meta,ensure_ascii=False),flush=True)
try:
 deadline=time.monotonic()+1200
 while p.poll() is None and time.monotonic()<deadline and not (C/'stop-requested').exists():time.sleep(.5)
finally:
 if p.poll() is None:
  assert owner.create_time()==created and Path(owner.exe()).resolve()==exe.resolve()
  for child in owner.children(recursive=True):
   try:child.terminate()
   except psutil.NoSuchProcess:pass
  p.terminate();p.wait(timeout=15)
 (O/'session-closed.json').write_text(json.dumps({'ownProductProcessClosed':True,'modelsRun':False,'originalLibraryOpened':False},indent=2),encoding='utf8')
 print('Own public share test app closed.',flush=True)
