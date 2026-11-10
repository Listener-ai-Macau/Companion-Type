from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone122');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app';now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
action=sys.argv[1]
if action=='prepare':
 assert version()==121 and not adb(['shell','pidof',PKG],required=False).strip() and not (P/'before-install.sha256').exists()
 path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw);hold=d['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold'];assert not hold['active'];hold.update(active=True,serial=SERIAL,reservedFor='Companion media import122 local public QA',requestedAt=now(),ownerInstruction='所有非模型达到售卖标准；沿已授权插线手机继续，USB保持唤醒已开启',scope='Own APK/UI on non-main display. Reuse own empty public QA library0a2cc0ac-149a-4688-8ff8-3180d987144a and newly restored test copies. Public media only; no BLE, board access or owner-record mutation.');temp=path.with_suffix('.import-phone-hold.tmp');save(temp,d);assert path.read_bytes()==raw;os.replace(temp,path)
 index=adb(['shell','run-as',PKG,'cat','files/companion-library-index.json']);assert json.loads(index)['activeId']=='original';(P/'original-index.private.json').write_text(index)
 print('Authorized phone idle; retaining private original-file manifest.',flush=True);snapshot=files();(P/'before-install.sha256').write_text(snapshot);print(json.dumps({'at':now(),'version':121,'files':len(hashes(snapshot)),'mainFingerprint':primary(),'boardAccessed':False}))
elif action=='install':
 assert version()==121 and not adb(['shell','pidof',PKG],required=False).strip();proof=json.loads((C/'android122/build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256'];before=primary();old=hashes((P/'before-install.sha256').read_text());assert 'Success' in adb(['install','-r','-t',apk],timeout=120) and version()==122
 after=files();(P/'after-install.sha256').write_text(after);assert hashes(after)==old;code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]==proof['apkSha256'];assert before==primary();save(C/'android122/installation.json',{'at':now(),'state':'ANDROID122_EXACT_APK_INSTALLED_EXISTING_FILES_IDENTICAL','sourceCommit':proof['sourceCommit'],'apkSha256':proof['apkSha256'],'existingFilesByteIdentical':len(old),'ownerMainUnchangedDuringInstall':True});print('Exact Android122 installed; all preexisting app files identical.')
elif action=='display':
 assert version()==122 and not adb(['shell','pidof',PKG],required=False).strip() and not (P/'virtual.json').exists();before=primary();exe=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe')
 args=[exe,'-s',SERIAL,'--new-display=1440x3200/589','--no-window','--record=NUL','--record-format=mkv','--no-audio','--no-clipboard-autosync','--display-ime-policy=local','--keyboard=disabled','--mouse=disabled','--no-power-on','--no-vd-system-decorations','--no-terminal-title','--max-fps=1','--video-bit-rate=128K']
 with (P/'virtual.log').open('wb') as log:child=subprocess.Popen(list(map(str,args)),env={**os.environ,'ADB':str(A)},stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 state={'at':now(),'pid':child.pid,'createdAt':psutil.Process(child.pid).create_time(),'mainBefore':before,'width':1440,'height':3200,'density':589,'physicalInput':False,'audioForwarded':False}
 for _ in range(30):
  match=re.search(r'New display:[^\n]*\(id=(\d+)\)',(P/'virtual.log').read_text(errors='replace'));assert child.poll() is None
  if match:state['displayId']=int(match[1]);break
  time.sleep(.2)
 assert state.get('displayId',0)>0 and primary()==before;save(P/'virtual.json',state);adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);assert primary()==before;print(json.dumps(state))
elif action in ['attach','restart']:
 state=json.loads((P/'virtual.json').read_text());before=primary()
 if action=='restart':
  old=json.loads((P/'cdp.json').read_text());assert adb(['shell','pidof',PKG]).strip()==str(old['pid']);activities=adb(['shell','dumpsys','activity','activities']);main=next(s for s in activities.split('Display #') if s.startswith('0 (activities from top to bottom):'));assert not any(PKG in row for row in main.splitlines() if 'Hist  #' in row);adb(['shell','am','force-stop',PKG]);adb(['forward','--remove','tcp:'+str(old['cdpPort'])]);adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity'])
 pid=''
 for _ in range(30):
  pid=adb(['shell','pidof',PKG],required=False).strip()
  if pid.isdigit():break
  time.sleep(.2)
 assert pid.isdigit() and primary()==before;port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();record={'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'mainBefore':before,'mainUnchangedDuringOperation':True};save(P/'cdp.json',record);print(json.dumps(record))
else:raise ValueError(action)
