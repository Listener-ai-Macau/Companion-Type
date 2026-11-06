from pathlib import Path
import hashlib,json,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059')
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/word061'
PRE=[str(R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'),'-s','6LCAPVHE9PBE45DU']
def run(args):
    p=subprocess.run(PRE+args,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=40);assert p.returncode==0,p.stdout+p.stderr;return p.stdout
version=run(['shell','dumpsys','package','com.denzic.companion.app']);assert 'versionCode=61 ' in version
before=(C/'app-files-before061.sha256').read_text(encoding='utf8')
after=run(['shell',"run-as com.denzic.companion.app sh -c 'find files -type f -exec sha256sum {} \\;'"])
(C/'app-files-after061.sha256').write_text(after,encoding='utf8')
def hashes(text):return {s.split(None,1)[1].strip():s.split(None,1)[0] for s in text.splitlines() if len(s.split(None,1))==2}
old=hashes(before);new=hashes(after);assert old and all(new.get(k)==v for k,v in old.items())
v=json.loads((F/'apk61-verification.json').read_text(encoding='utf8'));path=run(['shell','pm','path','com.denzic.companion.app']).strip().removeprefix('package:');actual=run(['shell','sha256sum',path]).split()[0];assert actual==v['sha256']
record={'version':'0.1.61/code61','installed':True,'exactInstalledApkSha256':actual,'source':v['frontendSourceCommit'],'backendSource':v['backendSourceCommit'],
    'originalAppFilesByteIdentical':len(old),'physicalMainActivityStayedUnchanged':None,'mainDisplayInputInjected':False,'virtualDisplayId':2,
    'observerFailureRetained':'Initial installer stopped after successful installation because physical-main resumed activity differed before/after. Subsequent actual state: physical display has no resumed activity and keyguard/screen off; own QA receiver is resumed only on display2. Cause of the transition is not established; not a failed App update or permission bypass.',
    'ordinaryAppAcceptanceComplete':False,'snapshotFilesLocalOnly':True}
(C/'installation061.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(record,ensure_ascii=False));print(run(['shell','am','start','--display','2','-n','com.denzic.companion.app/.MainActivity']))
