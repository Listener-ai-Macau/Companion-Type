from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess,tomllib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';F=P/'windows067-literal-and-rendering'
assert json.loads((F/'test-build-result.json').read_text())['result']=='FOCUSED_PRODUCT_SOURCE_TESTS_PASSED'
old=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
for name in ['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']:
 path=S/name;before=path.read_text(encoding='utf8');assert '0.1.60' in before,name
 path.write_text(before.replace('"0.1.60"','"0.1.67"'),encoding='utf8')
new=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
for lock in [old,new]:
 for item in lock['package']:
  if item['name']=='companion-type':item['version']='LOCAL_PRODUCT_VERSION_ONLY'
assert old==new,'No external dependency update is intended'
path=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';lic=json.loads(path.read_text(encoding='utf8'))
for name in lic['lockedInputs']:lic['lockedInputs'][name]=hashlib.sha256((S/name).read_bytes()).hexdigest()
for item in lic.get('localCompanyInputs',[]):
 if item.get('name')=='companion-type':item['version']='0.1.67'
path.write_text(json.dumps(lic,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 p=subprocess.run(['git','-c','maintenance.auto=false',*args],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
git('add','--','apps/windows/src-tauri/src/backend/pdf_export.rs','apps/windows/src-tauri/src/backend/mindmap_image_export.rs','package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json')
git('commit','-m','Package Windows067 literal document and asynchronous renderer completion fixes')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'sourceCommit':pin,'branch':branch,'version':'0.1.67','externalCargoDependenciesUnchanged':True,'remoteReadback':True,'installed':False,'modelsRun':False}
(F/'source-release.json').write_text(json.dumps(record,indent=2),encoding='utf8')
driver=(W/'build_windows060_word062.py').read_text(encoding='utf8').replace('windows060-word062','windows067-literal-and-rendering').replace('0.1.60','0.1.67')
driver=driver.replace("code=process.wait()","import psutil\n    own=psutil.Process(process.pid);cpus=own.cpu_affinity()[-4:];own.cpu_affinity(cpus)\n    while process.poll() is None:\n        for child in own.children(recursive=True):\n            try:\n                if child.name().lower() in ['cargo.exe','rustc.exe','link.exe']:child.cpu_affinity(cpus);child.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)\n            except (psutil.NoSuchProcess,psutil.AccessDenied):pass\n        time.sleep(1)\n    code=process.returncode")
(W/'build_windows067_release.py').write_text(driver,encoding='utf8')
pack=(W/'package_windows060_word062.py').read_text(encoding='utf8').replace('windows060-word062','windows067-literal-and-rendering').replace('0.1.60','0.1.67').replace('WINDOWS060_WORD062','WINDOWS067_LITERAL_DOCUMENTS').replace('录音与Word兼容修复','内容保真与文档导出修复')
(W/'package_windows067_release.py').write_text(pack,encoding='utf8')
print(json.dumps(record))
