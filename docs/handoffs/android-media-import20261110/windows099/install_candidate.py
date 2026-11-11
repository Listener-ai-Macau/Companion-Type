"""Upgrade own Windows app silently, hash original data, never open the app."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess,psutil,time,winreg
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import/windows099')
psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
verified=json.loads((C/'windows-verification.json').read_text(encoding='utf8'))
runtime=json.loads((C/'runtime-result.json').read_text(encoding='utf8'));assert runtime['state']=='WINDOWS099_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED' and runtime['appSourceCommit']==verified['sourceCommit']
backup=json.loads((C/'remote-candidate-backup.json').read_text(encoding='utf8'));assert backup['readbackByteIdentical'] and backup['msiSha256']==verified['msiSha256']
msi=Path(verified['msi']);installed=Path('C:/Program Files/Companion Type')
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def actual_version():
 result=[]
 for hive in [winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER]:
  try:key=winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\Uninstall')
  except FileNotFoundError:continue
  with key:
   for i in range(winreg.QueryInfoKey(key)[0]):
    with winreg.OpenKey(key,winreg.EnumKey(key,i)) as item:
     try:
      if winreg.QueryValueEx(item,'DisplayName')[0]=='Companion Type':result.append(winreg.QueryValueEx(item,'DisplayVersion')[0])
     except FileNotFoundError:pass
 assert len(result)==1,result
 return result[0]
assert sha(msi)==verified['msiSha256']
def active_daily_clients():
 blockers=[]
 daily=(Path(os.environ['APPDATA'])/'Companion Type').resolve()
 local=Path(os.environ['LOCALAPPDATA']).resolve()
 for process in psutil.process_iter(['name']):
  if (process.info['name'] or '').lower()!='companion-type.exe':continue
  try:
   executable=Path(process.exe()).resolve();values=process.environ()
   state=values.get('COMPANION_TYPE_STATE_PATH');recordings=values.get('COMPANION_TYPE_RECORDING_DIR')
   roaming=(Path(values.get('APPDATA',os.environ['APPDATA']))/'Companion Type').resolve()
   webview=values.get('WEBVIEW2_USER_DATA_FOLDER')
   webview_separate=(bool(webview) and not Path(webview).resolve().is_relative_to(local)) or Path(values.get('LOCALAPPDATA',os.environ['LOCALAPPDATA'])).resolve()!=local
   isolated=not executable.is_relative_to(installed.resolve()) and executable.with_name('companion_type_lib.dll').is_file() and state and recordings and not Path(state).resolve().is_relative_to(daily) and not Path(recordings).resolve().is_relative_to(daily) and not roaming.is_relative_to(daily) and webview_separate
   settings=values.get('COMPANION_TYPE_PRODUCT_SETTINGS_PATH')
   if settings and Path(settings).resolve().is_relative_to(daily):isolated=False
   if not isolated:blockers.append({'pid':process.pid,'reason':'Installed files or daily app storage may be in use'})
  except psutil.NoSuchProcess:continue
  except (psutil.AccessDenied,OSError):blockers.append({'pid':process.pid,'reason':'Cannot prove independent files and storage'})
 return blockers
assert not active_daily_clients(),'Daily Companion may be active; leave it intact'
previous=actual_version();assert tuple(map(int,previous.split('.')))<(0,1,99),previous
work=Path('E:/CodexData/Companion/.build-cache/windows-note-context20261110')/('upgrade099-private-'+str(time.time_ns()));work.mkdir(exist_ok=False)
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
product=Path(os.environ['APPDATA'])/'Companion Type'
def inventory():
 result={}
 if product.exists():
  for folder,dirs,files in os.walk(product,followlinks=False):
   dirs[:]=[name for name in dirs if not (Path(folder)/name).is_symlink()]
   for name in files:
    path=Path(folder)/name
    if path.is_file() and not path.is_symlink():result[path.relative_to(product).as_posix()]={'bytes':path.stat().st_size,'sha256':sha(path)}
 return result
before=inventory();(work/'data-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf8')
for relative in before:
 path=product/relative
 if path.suffix.lower() in ['.json','.txt','.md','.toml','.ini','.db','.sqlite','.bak'] and path.stat().st_size<10*1024*1024:
  target=work/'metadata-before'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
for name in ['companion-type.exe','companion_type_lib.dll']:
 if (installed/name).is_file():
  target=work/'installed-before'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(installed/name,target)
record={'state':'UPGRADING','startedAt':now(),'candidateVersion':'0.1.99','previousInstalledVersion':previous,'sourceCommit':verified['sourceCommit'],'msiSha256':sha(msi),'existingDataFiles':len(before),'dataContentsPrinted':False}
def save():(work/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
save()
try:
 # A second running-app observation immediately before the installer, after
 # the potentially lengthy data hashes. Do not ask RestartManager to close it.
 assert not active_daily_clients(),'Daily Companion opened meanwhile; preserve it'
 run=subprocess.run(['msiexec.exe','/i',str(msi),'/qn','/norestart','REBOOT=ReallySuppress','MSIRESTARTMANAGERCONTROL=Disable','/L*v',str(work/'install.log')],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
 record['installerExitCode']=run.returncode;assert run.returncode in [0,3010],run.returncode
 after=inventory();(work/'data-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf8')
 assert before==after,'Product data differs; retain both manifests'
 assert sha(installed/'companion-type.exe')==verified['embeddedExeSha256']
 assert sha(installed/'companion_type_lib.dll')==verified['dllSha256']
 assert actual_version()=='0.1.99'
 # --help returns before application startup, reconnect and all business IO.
 help_run=subprocess.run([str(installed/'companion-type.exe'),'--help'],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
 assert help_run.returncode==0 and b'Companion Type: launch without arguments' in help_run.stdout
 assert before==inventory(),'Read-only help changed original data'
 record.update(state='WINDOWS099_INSTALLED_EXISTING_DATA_IDENTICAL',finishedAt=now(),dataManifestIdentical=True,installedVersion='0.1.99',installedExeSha256=sha(installed/'companion-type.exe'),installedDllSha256=sha(installed/'companion_type_lib.dll'),installedHelpStartupPassed=True,ordinaryThirdPartyPasteQualified=False,oldWinRTSharePickerFixed=False,modelsRun=False,limitations='No interactive app opened, foreground interaction, private content inspected or printed, ordinary recipient paste, phone or device operation or model inference.')
except BaseException as error:
 record.update(state='UPGRADE_NOT_CONFIRMED_RETAINED',finishedAt=now(),error=repr(error));save();(C/'installation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');raise
save();(C/'installation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
