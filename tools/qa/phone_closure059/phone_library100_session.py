"""Actual phone acceptance, restricted to this task's new non-main display."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,re,shlex,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-mobile-library-location/phone100'
P=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance100');P.mkdir(parents=True,exist_ok=True)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
PKG='com.denzic.companion.app';SERIAL='6LCAPVHE9PBE45DU'
ITEM='Android100手机资料恢复与导出验收（不接板卡BLE，不录音）'
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def adb(args,binary=False,timeout=35):
 args=list(map(str,args))
 if args and args[0]=='shell':args=['shell',' '.join(shlex.quote(arg) for arg in args[1:])]
 proc=subprocess.run([str(A),'-s',SERIAL,*args],capture_output=True,timeout=timeout)
 assert proc.returncode==0,proc.stderr.decode('utf8',errors='replace')+proc.stdout.decode('utf8',errors='replace')
 return proc.stdout if binary else proc.stdout.decode('utf8',errors='replace')
def guard():
 line=''.join(x for x in (R/'docs/board_operations.md').read_text(encoding='utf-8-sig').splitlines() if x.startswith('- **占用中**'))
 assert ITEM in line,'Shared phone acceptance item is not held'
def primary():
 text=adb(['shell','dumpsys','activity','activities'])
 block=next(s for s in text.split('Display #') if s.startswith('0 (activities from top to bottom):'))
 row=next((s for s in block.splitlines() if 'topResumedActivity=' in s),'')
 match=re.search(r'\bu\d+\s+(\S+)\s+t\d+',row)
 return match.group(1) if match else 'PRIMARY_NOT_RESUMED'
def primary_digest():return hashlib.sha256(primary().encode()).hexdigest()
def package():
 text=adb(['shell','dumpsys','package',PKG]);match=re.search(r'versionCode=(\d+)\s',text)
 assert match;return int(match[1])
def files():return adb(['shell','run-as',PKG,'sh','-c',r'find files -type f -exec sha256sum {} \;'],timeout=180)
def hashes(text):
 return {line.split(None,1)[1].strip():line.split(None,1)[0] for line in text.splitlines() if len(line.split(None,1))==2}
def current():
 state=json.loads((P/'virtual.json').read_bytes());assert state['displayId']>0
 import psutil
 proc=psutil.Process(state['pid']);assert abs(proc.create_time()-state['processCreatedAt'])<.01
 assert 'scrcpy.exe' in proc.name().lower()
 return state
guard();action=sys.argv[1]
if action=='preflight':
 assert not (C/'phone-preflight.json').exists(),'Preserve the original preflight'
 version=package();assert version==65,'Observed phone version changed; reevaluate rather than overwrite'
 assert not subprocess.run([str(A),'-s',SERIAL,'shell','pidof',PKG],capture_output=True).stdout.strip(),'App already active; check its task before upgrade'
 snapshot=files();(P/'private-original-files-before.sha256').write_text(snapshot,encoding='utf8')
 record={'at':now(),'serialSuffix':'45DU','observedVersionCode':version,'originalFileCount':len(hashes(snapshot)),
   'privateFileManifestSha256':hashlib.sha256(snapshot.encode()).hexdigest(),'primaryActivityFingerprint':primary_digest(),
   'scope':'Own app file hashes only; no recording content parsed or uploaded. Raw filenames remain private in E cache.',
   'appWasRunning':False,'modelsRun':False}
 save(C/'phone-preflight.json',record);print(json.dumps(record),flush=True)
elif action=='virtual':
 assert (C/'phone-preflight.json').exists(),'Complete and preserve the live phone/file preflight first'
 assert not (P/'virtual.json').exists(),'Existing display must be examined, not replaced'
 before=primary_digest();exe=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe')
 args=[str(exe),'-s',SERIAL,'--new-display=1080x1920/360','--no-window','--no-audio','--no-clipboard-autosync',
  '--display-ime-policy=local','--keyboard=disabled','--mouse=disabled','--no-power-on','--no-vd-system-decorations',
  '--no-terminal-title','--max-fps=1','--video-bit-rate=128K']
 log=P/'virtual.log'
 with log.open('wb') as handle:
  child=subprocess.Popen(args,env={**os.environ,'ADB':str(A)},stdout=handle,stderr=subprocess.STDOUT,
   creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 import psutil
 state={'at':now(),'pid':child.pid,'processCreatedAt':psutil.Process(child.pid).create_time(),'beforePrimaryFingerprint':before,
  'audioForwarding':False,'clipboardForwarding':False,'physicalInputForwarding':False,'recordingVideo':False}
 for _ in range(15):
  text=log.read_text(encoding='utf8',errors='replace')
  assert child.poll() is None,text[-1500:]
  match=re.search(r'New display[^\n]*?\b(\d+)\b',text)
  if match:state['displayId']=int(match[1]);break
  time.sleep(1)
 assert state.get('displayId',0)>0
 state['afterPrimaryFingerprint']=primary_digest();state['primaryUnchanged']=before==state['afterPrimaryFingerprint']
 save(P/'virtual.json',state);save(C/'virtual-display.json',state)
 assert state['primaryUnchanged'],'Primary owner activity changed; pause before input'
 print(json.dumps(state),flush=True)
elif action=='install':
 state=current();assert package()==json.loads((C/'phone-preflight.json').read_bytes())['observedVersionCode']
 assert not subprocess.run([str(A),'-s',SERIAL,'shell','pidof',PKG],capture_output=True).stdout.strip()
 before=primary_digest();proof=json.loads((C/'apk100-verification.json').read_bytes());apk=Path(proof['apk'])
 assert hashlib.sha256(apk.read_bytes()).hexdigest()==proof['sha256']
 output=adb(['install','-r','-t',apk],timeout=120);assert 'Success' in output
 assert package()==100
 old=hashes((P/'private-original-files-before.sha256').read_text(encoding='utf8'));after=files();(P/'private-original-files-after-install.sha256').write_text(after,encoding='utf8');new=hashes(after)
 assert old and all(new.get(name)==digest for name,digest in old.items()),'Original app files changed'
 code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:')
 actual=adb(['shell','sha256sum',code]).split()[0];assert actual==proof['sha256']
 result={'at':now(),'state':'ANDROID100_EXACT_APK_INSTALLED_ORIGINAL_FILES_IDENTICAL','versionCode':100,
  'installedSha256':actual,'sourceCommit':proof['frontendSourceCommit'],'backendSourceCommit':proof['backendSourceCommit'],
  'originalFilesByteIdentical':len(old),'primaryUnchanged':before==primary_digest(),'displayId':state['displayId'],
  'foregroundAcceptanceComplete':False,'modelsRun':False,'privateContentsUploaded':False}
 save(C/'installation.json',result);print(json.dumps(result),flush=True)
elif action=='start':
 state=current();before=primary_digest();assert package()==100
 print(adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']))
 after=primary_digest();assert before==after,'App launch changed physical activity; no input'
 pid=adb(['shell','pidof',PKG]).strip();assert pid.isdigit()
 port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit()
 result={'at':now(),'state':'ACTUAL_WEBVIEW_ON_NON_MAIN_DISPLAY','displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'primaryUnchanged':True}
 save(P/'cdp.json',result);save(C/'phone-ui-session.json',result);print(json.dumps(result),flush=True)
elif action=='native':
 state=current();display=state['displayId'];assert primary_digest()==state['beforePrimaryFingerprint'],'Primary activity changed; no input'
 verb=sys.argv[2] if len(sys.argv)>2 else 'dump';extra=['-e','display',display,'-e','action',verb]
 if len(sys.argv)>3:extra+=['-e','id' if sys.argv[3].startswith('id:') else 'label',sys.argv[3].removeprefix('id:')]
 if verb=='setText':extra+=['-e','value',sys.argv[4]]
 elif len(sys.argv)>4:extra+=['-e','index',sys.argv[4]]
 text=adb(['shell','am','instrument','-w',*extra,'com.denzic.companion.uidriver059/.NativeUi059'],timeout=45)
 assert 'INSTRUMENTATION_CODE: -1' in text,text[-1000:]
 row=next(x for x in text.splitlines() if x.startswith('INSTRUMENTATION_RESULT: result='))
 result=json.loads(row.split('result=',1)[1]);assert result['display']==display
 if verb=='dump':
  nodes=[{k:n[k] for k in ['text','desc','id','class','bounds','enabled']} for n in result['nodes'] if n.get('text') or n.get('desc')]
  print(json.dumps({'displayId':display,'nodes':nodes},ensure_ascii=False),flush=True)
 else:print(json.dumps({'displayId':display,'action':verb,'label':sys.argv[3] if len(sys.argv)>3 else '', 'result':'ORDINARY_NATIVE_UI_ACTION_SUCCEEDED'},ensure_ascii=False),flush=True)
else:raise ValueError(action)
