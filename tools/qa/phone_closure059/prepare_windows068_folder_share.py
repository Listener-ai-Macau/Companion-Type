from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib,subprocess,os,tomllib,shutil,psutil
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share070'
assert json.loads((O/'native-test-result.json').read_text())['state']=='FOLDER_SHARE_SOURCE_AND_SHELL_PATH_TESTS_PASSED_NO_UI_OPENED'
checks=json.loads((O/'light-check-result.json').read_text());assert all(x['exitCode']==0 for x in checks)
old=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
for name in ['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']:
 p=S/name;text=p.read_text(encoding='utf8');assert '"0.1.67"' in text,name;p.write_text(text.replace('"0.1.67"','"0.1.68"'),encoding='utf8')
new=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
for lock in (old,new):
 for item in lock['package']:
  if item['name']=='companion-type':item['version']='LOCAL_PRODUCT_VERSION_ONLY'
assert old==new
p=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';lic=json.loads(p.read_text(encoding='utf8'))
for name in lic['lockedInputs']:lic['lockedInputs'][name]=hashlib.sha256((S/name).read_bytes()).hexdigest()
for item in lic.get('localCompanyInputs',[]):
 if item.get('name')=='companion-type':item['version']='0.1.68'
p.write_text(json.dumps(lic,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
psutil.Process().cpu_affinity([12,13]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
with (O/'windows-web-build.log').open('wb') as stream:
 run=subprocess.run(['C:/Program Files/nodejs/node.exe','C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js','run','build:windows'],cwd=S,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
assert run.returncode==0,(O/'windows-web-build.log').read_text(encoding='utf8',errors='replace')[-3000:]

env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 p=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
git('add','--','package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json','apps/windows/src-tauri/src/content_handoff.rs','apps/windows/src-tauri/src/commands.rs','apps/windows/src/App.tsx','apps/windows/src/companionClient.ts','packages/ui/src/CompanionDashboard.tsx','packages/ui/src/CompanionExportFeedback.tsx','packages/ui/src/ContentExportPanel.tsx','packages/ui/src/shareHandoff.ts','tools/test_content_export_panel051.tsx','tools/test_share070.mjs')
git('add','-f','--','docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share069/modern-invoke-first-error.log')
git('-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','diff','--cached','--check')
git('commit','-m','Add explicit Explorer sharing route for selected content and audio')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin','HEAD:refs/heads/'+branch);assert git('ls-remote','origin','refs/heads/'+branch).split()[0]==pin
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'sourceCommit':pin,'remoteReadback':True,'version':'0.1.68','installed':False,'computerUse':False,'modelsRun':False,'externalCargoDependenciesUnchanged':True,'actualRecipientVerified':False}
(O/'source-release.json').write_text(json.dumps(record,indent=2),encoding='utf8')
driver=(W/'build_windows067_release.py').read_text(encoding='utf8').replace('windows067-literal-and-rendering','windows-share070').replace('0.1.67','0.1.68').replace('Integrated Windows source with shared062 Word footer correction; no inference or training.','Explicit documented Explorer file-selection sharing route for content/audio; no private shell handlers, UI automation, device IO or inference.')
driver=driver.replace("from pathlib import Path","from pathlib import Path\nimport psutil\npsutil.Process().cpu_affinity([12,13]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)")
driver=driver.replace("while process.poll() is None:","peak_rss=0;pressure_since=None;resource_stop=False\n    while process.poll() is None:")
driver=driver.replace("        time.sleep(1)","        family=[own]+own.children(recursive=True);rss=0\n        for member in family:\n            try:rss+=member.memory_info().rss\n            except (psutil.NoSuchProcess,psutil.AccessDenied):pass\n        peak_rss=max(peak_rss,rss)\n        pressure=psutil.virtual_memory().percent>=97 and rss>1536*1024*1024\n        pressure_since=(pressure_since or time.monotonic()) if pressure else None\n        if pressure_since and time.monotonic()-pressure_since>15:\n            resource_stop=True\n            for member in reversed(family):\n                try:member.terminate()\n                except (psutil.NoSuchProcess,psutil.AccessDenied):pass\n            break\n        time.sleep(1)")
driver=driver.replace("    code=process.returncode","    code=process.wait()")
driver=driver.replace("'exitCode':code,","'exitCode':code,'peakOwnRssMiB':round(peak_rss/2**20),'stoppedForActualMemoryPressure':resource_stop,")
(W/'build_windows068_folder_share.py').write_text(driver,encoding='utf8')
pack=(W/'package_windows067_release.py').read_text(encoding='utf8').replace('windows067-literal-and-rendering','windows-share070').replace('0.1.67','0.1.68').replace('WINDOWS067_LITERAL_DOCUMENTS','WINDOWS068_FOLDER_SHARING').replace('内容保真与文档导出修复','文件夹分享与状态修复')
(W/'package_windows068_folder_share.py').write_text(pack,encoding='utf8')
install=(W/'install_windows067_verified.py').read_text(encoding='utf8').replace('windows067-literal-and-rendering','windows-share070').replace('0.1.67','0.1.68').replace('0.1.60','0.1.67').replace('upgrade067-private','upgrade068-private').replace('WINDOWS067_','WINDOWS068_')
(W/'install_windows068_folder_share.py').write_text(install,encoding='utf8')
print(json.dumps(record),flush=True)
