from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,subprocess,shutil
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/android-trash071'
assert all(x['exitCode']==0 for x in json.loads((O/'checks.json').read_text(encoding='utf8')))
ui=S/'.cache/lifecycle071/result.json';assert json.loads(ui.read_text(encoding='utf8'))['exitCode']==0;shutil.copy2(ui,O/'ui-component-result.json')
p=S/'apps/android/app/build.gradle';text=p.read_text(encoding='utf8');assert 'versionCode 66' in text and "versionName '0.1.66'" in text
p.write_text(text.replace('versionCode 66','versionCode 69').replace("versionName '0.1.66'","versionName '0.1.69'"),encoding='utf8')
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 r=subprocess.run(['git','-c','maintenance.auto=false',*args],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert r.returncode==0,r.stdout+r.stderr;return r.stdout.strip()
files=['apps/android/app/build.gradle','apps/android/app/src/main/java/com/denzic/companion/app/LocalRecordingLifecycle.java','apps/android/app/src/main/java/com/denzic/companion/app/MainActivity.java','apps/mobile/src/App.tsx','apps/mobile/src/RecordingLifecycle.tsx','apps/mobile/src/mobileRefinement.css','tools/LocalRecordingLifecycle071Test.java','tools/test_mobile_lifecycle071.tsx','tools/test_mobile_lifecycle071.mjs']
git('add','--',*files);git('-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check');git('commit','-m','Add Android protected recordings and recoverable local recycle bin')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin','HEAD:refs/heads/'+branch);assert git('ls-remote','origin','refs/heads/'+branch).split()[0]==pin
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'sourceCommit':pin,'branch':branch,'remoteReadbackConfirmed':True,'versionName':'0.1.69','versionCode':69,'installed':False,'computerUse':False,'modelsRun':False,'nativeRebuilt':False,'phoneIo':False}
(O/'source-release.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record),flush=True)
