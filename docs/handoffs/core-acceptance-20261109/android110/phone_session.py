"""Continue the existing Android110 acceptance on the authorized USB phone only."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,re,shlex,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-core-acceptance/android110/phone-d6'
P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6');P.mkdir(parents=True,exist_ok=True);C.mkdir(parents=True,exist_ok=True)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def adb(args,binary=False,timeout=40,required=True):
 args=list(map(str,args))
 if args and args[0]=='shell':args=['shell',' '.join(shlex.quote(arg) for arg in args[1:])]
 p=subprocess.run([str(A),'-s',SERIAL,*args],capture_output=True,timeout=timeout)
 if required and p.returncode:
  save(P/('adb-failure-'+str(time.time_ns())+'.json'),{'args':args,'exit':p.returncode,'stdout':p.stdout.decode('utf8',errors='replace'),'stderr':p.stderr.decode('utf8',errors='replace')})
  raise RuntimeError('Authorized phone operation failed; details retained in private acceptance directory')
 return p.stdout if binary else p.stdout.decode('utf8',errors='replace')
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def version():
 match=re.search(r'versionCode=(\d+)\s',adb(['shell','dumpsys','package',PKG]));assert match;return int(match[1])
def primary():
 text=adb(['shell','dumpsys','activity','activities']);block=next((s for s in text.split('Display #') if s.startswith('0 (activities from top to bottom):')),text)
 row=next((line.strip() for line in block.splitlines() if 'topResumedActivity=' in line),'')
 return hashlib.sha256(row.encode()).hexdigest()
def files():return adb(['shell','run-as',PKG,'sh','-c',r'find files -type f -exec sha256sum {} \;'],timeout=180)
def hashes(text):return {line.split(None,1)[1].strip():line.split(None,1)[0] for line in text.splitlines() if len(line.split(None,1))==2}
action=sys.argv[1]
if action=='preflight':
 assert not (C/'preflight.json').exists(),'Preserve the original phone baseline'
 assert version()==109 and not adb(['shell','pidof',PKG],required=False).strip()
 assert 'ServiceRecord{' not in adb(['shell','dumpsys','activity','services',PKG])
 snapshot=files();assert hashes(snapshot);(P/'original-files-before.sha256').write_text(snapshot,encoding='utf8')
 code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert '\n' not in code
 adb(['pull',code,P/'original109.apk'],timeout=120)
 existing=adb(['shell','run-as',PKG,'sh','-c','for d in files shared_prefs databases; do [ ! -d "$d" ] || printf "%s\\n" "$d"; done']).splitlines()
 assert 'files' in existing and all(name in ['files','shared_prefs','databases'] for name in existing)
 size=adb(['shell','run-as',PKG,'du','-sk',*existing]);(P/'original-directory-sizes.txt').write_text(size,encoding='utf8')
 required=sum(int(line.split()[0])*1024 for line in size.splitlines());assert shutil.disk_usage(P).free>required*2
 with (P/'original-private-data.tar').open('wb') as out,(P/'backup-stderr.log').open('wb') as error:
  p=subprocess.run([str(A),'-s',SERIAL,'exec-out','run-as',PKG,'tar','-cf','-',*existing],stdout=out,stderr=error,timeout=180);assert p.returncode==0
 record={'at':now(),'state':'PHONE109_ORIGINAL_APK_AND_PRIVATE_DATA_BACKED_UP','serialSuffix':'213d','versionCode':109,'originalFileCount':len(hashes(snapshot)),'privateManifestSha256':hashlib.sha256(snapshot.encode()).hexdigest(),'originalApkSha256':sha(P/'original109.apk'),'backupBytes':(P/'original-private-data.tar').stat().st_size,'backupSha256':sha(P/'original-private-data.tar'),'primaryFingerprint':primary(),'privateContentsUploaded':False,'boardAccessed':False}
 save(C/'preflight.json',record);print(json.dumps(record,ensure_ascii=False))
elif action=='virtual':
 assert (C/'preflight.json').exists() and not (P/'virtual.json').exists()
 before=primary();exe=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe');assert exe.is_file()
 args=[str(exe),'-s',SERIAL,'--new-display=1080x1920/360','--no-window','--record=NUL','--record-format=mkv','--no-audio','--no-clipboard-autosync','--display-ime-policy=local','--keyboard=disabled','--mouse=disabled','--no-power-on','--no-vd-system-decorations','--no-terminal-title','--max-fps=1','--video-bit-rate=128K']
 with (P/'virtual.log').open('wb') as log:child=subprocess.Popen(args,env={**os.environ,'ADB':str(A)},stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 import psutil
 state={'at':now(),'pid':child.pid,'processCreatedAt':psutil.Process(child.pid).create_time(),'beforePrimaryFingerprint':before,'audioForwarding':False,'clipboardForwarding':False,'physicalInputForwarding':False,'recordingVideo':False,'videoSink':'Windows NUL; virtual-display frames discarded, not saved; no physical display capture'}
 for _ in range(20):
  text=(P/'virtual.log').read_text(encoding='utf8',errors='replace');assert child.poll() is None,text[-800:]
  match=re.search(r'New display:[^\n]*\(id=(\d+)\)',text)
  if match:state['displayId']=int(match[1]);break
  time.sleep(.5)
 assert state.get('displayId',0)>0;state['afterPrimaryFingerprint']=primary();state['primaryUnchanged']=before==state['afterPrimaryFingerprint'];save(P/'virtual.json',state);save(C/'virtual-display.json',state)
 assert state['primaryUnchanged'],'Phone primary activity changed; stop before input'
 print(json.dumps(state,ensure_ascii=False))
elif action=='install':
 before=primary();assert version()==109 and not adb(['shell','pidof',PKG],required=False).strip()
 proof=json.loads((C.parent/'Android110-core-candidate-verification.json').read_text(encoding='utf8'));apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256']
 output=adb(['install','-r','-t',apk],timeout=120);assert 'Success' in output;assert version()==110
 old=hashes((P/'original-files-before.sha256').read_text(encoding='utf8'));after=files();(P/'original-files-after-install.sha256').write_text(after,encoding='utf8');new=hashes(after);assert all(new.get(name)==digest for name,digest in old.items())
 code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');actual=adb(['shell','sha256sum',code]).split()[0];assert actual==proof['apkSha256']
 record={'at':now(),'state':'ANDROID110_EXACT_APK_INSTALLED_ORIGINAL_FILES_IDENTICAL','versionCode':110,'installedSha256':actual,'sourceCommit':proof['sourceCommit'],'backendSourceCommit':proof['backendSourceCommit'],'originalFilesByteIdentical':len(old),'primaryUnchanged':before==primary(),'phoneFlowQualified':False,'boardAccessed':False,'modelsRun':False};save(C/'installation.json',record);print(json.dumps(record,ensure_ascii=False))
elif action=='start':
 state=json.loads((P/'virtual.json').read_text(encoding='utf8'));assert state['displayId']>0 and version()==110
 before=primary();assert not adb(['shell','pidof',PKG],required=False).strip()
 adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);assert before==primary(),'App launch changed physical phone activity; no input'
 pid=adb(['shell','pidof',PKG]).strip();assert pid.isdigit();port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit()
 record={'at':now(),'state':'ANDROID110_WEBVIEW_ON_NON_MAIN_DISPLAY','displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'primaryUnchanged':True};save(P/'cdp.json',record);save(C/'ui-session.json',record);print(json.dumps(record,ensure_ascii=False))
else:raise ValueError(action)
