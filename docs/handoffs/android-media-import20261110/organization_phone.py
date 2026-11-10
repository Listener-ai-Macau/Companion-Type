from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone125');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app';now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
def fastFiles():return adb(['shell','run-as',PKG,'sh','-c','find files -type f -print0 | xargs -0 -r sha256sum'],timeout=120)
action=sys.argv[1]
if action=='prepare':
 assert version()==124 and not adb(['shell','pidof',PKG],required=False).strip();P.mkdir(exist_ok=False)
 path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw);h=d['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold'];assert not h['active'];h.update(active=True,serial=SERIAL,reservedFor='Companion125 public recording organization acceptance',requestedAt=now(),scope='Own app only, owned non-main display; own public QA library0a2cc0ac and newly restored copy. Folders/tags/selected-record management and backup lifecycle only; no BLE, mic, model or private owner data.');temp=path.with_suffix('.notes-hold.tmp');save(temp,d);assert path.read_bytes()==raw;os.replace(temp,path)
 index=adb(['shell','run-as',PKG,'cat','files/companion-library-index.json']);assert json.loads(index)['activeId']=='original';(P/'original-index.private.json').write_text(index);snapshot=fastFiles();(P/'before-install.sha256').write_text(snapshot);save(P/'preparation.json',{'at':now(),'files':len(hashes(snapshot)),'version':version(),'mainFingerprint':primary()});print('Phone124 idle; original library and complete private hash manifest retained; scoped hold acquired.')
elif action=='install':
 assert version()==124 and not adb(['shell','pidof',PKG],required=False).strip();proof=json.loads((C/'android125/build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256'];before=primary();old=hashes((P/'before-install.sha256').read_text());assert 'Success' in adb(['install','-r','-t',apk],timeout=120) and version()==125
 snapshot=fastFiles();(P/'after-install.sha256').write_text(snapshot);assert hashes(snapshot)==old and primary()==before;code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]==proof['apkSha256'];save(C/'android125/installation.json',{'at':now(),'state':'ANDROID125_EXACT_APK_INSTALLED_EXISTING_CONTENT_IDENTICAL','sourceCommit':proof['sourceCommit'],'apkSha256':proof['apkSha256'],'existingFilesByteIdentical':len(old),'mainUnchangedDuringInstall':True});print('125 exact APK installed; existing app contents byte identical.')
elif action=='display':
 assert version()==125 and not adb(['shell','pidof',PKG],required=False).strip();assert not (P/'virtual.json').exists();before=primary();exe=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe');args=[exe,'-s',SERIAL,'--new-display=1440x3200/589','--no-window','--record=NUL','--record-format=mkv','--no-audio','--no-clipboard-autosync','--display-ime-policy=local','--keyboard=disabled','--mouse=disabled','--no-power-on','--no-vd-system-decorations','--no-terminal-title','--max-fps=1','--video-bit-rate=128K']
 with (P/'virtual.log').open('wb') as out:child=subprocess.Popen(list(map(str,args)),env={**os.environ,'ADB':str(A)},stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 state={'at':now(),'pid':child.pid,'createdAt':psutil.Process(child.pid).create_time(),'mainBefore':before,'physicalInput':False,'audioForwarded':False}
 for _ in range(30):
  m=re.search(r'New display:[^\n]*\(id=(\d+)\)',(P/'virtual.log').read_text(errors='replace'));assert child.poll() is None
  if m:state['displayId']=int(m[1]);break
  time.sleep(.2)
 assert state.get('displayId',0)>0 and primary()==before;save(P/'virtual.json',state);adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);print('Owned secondary display created; main unchanged.')
elif action in ['attach','restart']:
 state=json.loads((P/'virtual.json').read_text());before=primary()
 if action=='restart':
  old=json.loads((P/'cdp.json').read_text());assert adb(['shell','pidof',PKG]).strip()==str(old['pid']);main=next(v for v in adb(['shell','dumpsys','activity','activities']).split('Display #') if v.startswith('0 (activities from top to bottom):'));assert not any(PKG in line for line in main.splitlines() if 'Hist  #' in line);adb(['shell','am','force-stop',PKG]);adb(['forward','--remove','tcp:'+str(old['cdpPort'])]);adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity'])
 pid=''
 for _ in range(40):
  pid=adb(['shell','pidof',PKG],required=False).strip()
  if pid.isdigit():break
  time.sleep(.2)
 assert pid.isdigit();port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();save(P/'cdp.json',{'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'mainBefore':before,'mainUnchangedDuringOperation':primary()==before});print('Attached only own secondary-display app WebView.')
else:raise ValueError(action)
