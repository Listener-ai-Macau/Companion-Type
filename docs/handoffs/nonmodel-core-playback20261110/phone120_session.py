"""Existing authorized phone, local public QA only; no BLE or owner main-display input."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time
import psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent/'android120';P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110/phone120');P.mkdir(exist_ok=True)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app';now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
action=sys.argv[1]
if action=='install':
 assert not (C/'installation.json').exists() and version()==117
 assert not adb(['shell','pidof',PKG],required=False).strip() and 'ServiceRecord{' not in adb(['shell','dumpsys','activity','services',PKG])
 path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw);hold=d['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold'];assert not hold['active']
 hold.update(active=True,reservedFor='Companion120 local playback correction and settings closure',serial=SERIAL,requestedAt=now(),ownerInstruction='测试手机一直插着，USB调试已开启；尽快完成并考虑设置',scope='Own APK117 to120, new public QA copy and owned virtual display only. No Bluetooth connection, capture, board access or owner recording mutation.')
 assert path.read_bytes()==raw;temp=path.with_suffix('.phone120-hold.tmp');save(temp,d);os.replace(temp,path)
 before=primary();snapshot=files();(P/'before-install.sha256').write_text(snapshot,encoding='utf8');old=hashes(snapshot);assert old
 index=adb(['shell','run-as',PKG,'cat','files/companion-library-index.json']);(P/'original-library-index.private.json').write_text(index,encoding='utf8');assert json.loads(index)['activeId']=='original'
 code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]=='2d3a2040e83ea84930ad0d9ecdfd784a0a66502945c623950a5c2ff85e412a5b'
 proof=json.loads((C/'build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256']
 assert 'Success' in adb(['install','-r','-t',apk],timeout=120) and version()==120
 after=files();(P/'after-install.sha256').write_text(after,encoding='utf8');assert hashes(after)==old
 code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]==proof['apkSha256']
 record={'at':now(),'state':'ANDROID120_EXACT_APK_INSTALLED_ORIGINAL_FILES_IDENTICAL','sourceCommit':proof['sourceCommit'],'installedSha256':proof['apkSha256'],'originalFilesByteIdentical':len(old),'primaryUnchanged':before==primary(),'modelsRun':False,'boardAccessed':False};save(C/'installation.json',record);print(json.dumps(record))
elif action=='virtual':
 assert version()==120 and not (P/'virtual.json').exists() and not adb(['shell','pidof',PKG],required=False).strip()
 before=primary();exe=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe')
 args=[str(exe),'-s',SERIAL,'--new-display=1440x3200/589','--no-window','--record=NUL','--record-format=mkv','--no-audio','--no-clipboard-autosync','--display-ime-policy=local','--keyboard=disabled','--mouse=disabled','--no-power-on','--no-vd-system-decorations','--no-terminal-title','--max-fps=1','--video-bit-rate=128K']
 with (P/'virtual.log').open('wb') as log:child=subprocess.Popen(args,env={**os.environ,'ADB':str(A)},stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 state={'at':now(),'pid':child.pid,'createdAt':psutil.Process(child.pid).create_time(),'mainBefore':before,'width':1440,'height':3200,'density':589,'audioForwarding':False,'physicalInput':False,'clipboardForwarding':False,'videoSink':'NUL; owned virtual frames not retained'}
 for _ in range(30):
  text=(P/'virtual.log').read_text(errors='replace');assert child.poll() is None,text[-1000:];match=re.search(r'New display:[^\n]*\(id=(\d+)\)',text)
  if match:state['displayId']=int(match[1]);break
  time.sleep(.4)
 save(P/'virtual.json',state);assert state.get('displayId',0)>0 and primary()==before;print(json.dumps(state))
elif action=='attach':
 state=json.loads((P/'virtual.json').read_text());session=json.loads((P/'cdp.json').read_text());before=primary();pid=adb(['shell','pidof',PKG]).strip();assert pid.isdigit() and state['displayId']>0
 port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit() and primary()==before
 record={'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'mainBefore':before,'attachedExistingOwnedRestart':True};save(P/'cdp.json',record);print(json.dumps(record))
elif action=='restart':
 state=json.loads((P/'virtual.json').read_text());session=json.loads((P/'cdp.json').read_text());assert state['displayId']>0 and version() in [120,121]
 activities=adb(['shell','dumpsys','activity','activities']);main=next(s for s in activities.split('Display #') if s.startswith('0 (activities from top to bottom):'));assert not any(PKG in row for row in main.splitlines() if 'Hist  #' in row)
 before=primary()
 assert adb(['shell','pidof',PKG]).strip()==str(session['pid'])
 adb(['shell','am','force-stop',PKG]);adb(['forward','--remove','tcp:'+str(session['cdpPort'])]);assert primary()==before
 adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);assert primary()==before
 pid=''
 for _ in range(25):
  pid=adb(['shell','pidof',PKG],required=False).strip()
  if pid.isdigit():break
  time.sleep(.2)
 assert pid.isdigit();port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit()
 record={'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'mainBefore':before,'mainUnchangedDuringRestart':True,'ownerMainChangedIndependentlyBeforeRestart':before!=session['mainBefore'],'restartOfOwnedAppOnly':True};save(P/'cdp.json',record);save(C/('ui-restart-'+str(time.time_ns())+'.json'),record);print(json.dumps(record))
elif action=='start':
 state=json.loads((P/'virtual.json').read_text());assert state['displayId']>0 and version()==120
 before=primary();assert not adb(['shell','pidof',PKG],required=False).strip();adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);assert before==primary()
 pid=''
 for _ in range(25):
  pid=adb(['shell','pidof',PKG],required=False).strip()
  if pid.isdigit():break
  time.sleep(.2)
 assert pid.isdigit();port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit()
 record={'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'mainBefore':before,'mainUnchanged':True};save(P/'cdp.json',record);save(C/'ui-session.json',record);print(json.dumps(record))
else:raise ValueError(action)
