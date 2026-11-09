"""Freeze the one grouped Windows meeting candidate, not a new task tree."""
from pathlib import Path
from datetime import datetime
import ast,copy,hashlib,json,os,shutil,subprocess,tomllib

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-core-acceptance';O=C/'candidate079';O.mkdir(exist_ok=True)
old_lock=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
old_npm=json.loads((S/'package-lock.json').read_text(encoding='utf8'))
names=['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']
for name in names:
 p=S/name;raw=p.read_bytes();assert b'"0.1.78"' in raw,name
 p.write_bytes(raw.replace(b'"0.1.78"',b'"0.1.79"'))
new_lock=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
for lock in (old_lock,new_lock):
 for item in lock['package']:
  if item['name']=='companion-type':item['version']='LOCAL_PRODUCT_VERSION_ONLY'
assert old_lock==new_lock,'External dependencies must not change in a UI release'
new_npm=json.loads((S/'package-lock.json').read_text(encoding='utf8'))
for lock in (old_npm,new_npm):
 lock['version']='LOCAL_PRODUCT_VERSION_ONLY'
 lock['packages']['']['version']='LOCAL_PRODUCT_VERSION_ONLY'
assert old_npm==new_npm,'NPM external dependency versions must stay fixed'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json'
lic=json.loads(p.read_text(encoding='utf8'))
for name in lic['lockedInputs']:lic['lockedInputs'][name]=sha(S/name)
p.write_text(json.dumps(lic,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
shutil.copyfile(R/'tools/check_type_build_target.py',S/'tools/check_type_build_target.py')
for name in ['tools/build_windows_candidate_ci.py','.github/workflows/windows-candidate.yml']:
 p=S/name;prior=subprocess.check_output(['git','show','HEAD:'+name],cwd=S)
 if prior.count(b'\r\n')==prior.count(b'\n'):
  p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
at=datetime.now().astimezone().isoformat(timespec='seconds')
record={'at':at,'state':'GROUPED_WINDOWS079_SOURCE_FROZEN_REMOTE_BUILD_PENDING','version':'0.1.79','purpose':'同一场会议从原音、转写修订、AI整理到所选内容/录音交付，集中收敛Windows候选。','changes':['会议顶部导出定位到所选内容面板','原音导出进入会议顶部工具栏','无最终文字时明确先转文字，不展示不可用AI工作区','会中问题不擅自标成未解决'],'affectedUiSourcePassedRun':42584662552,'realAudioFlowPassedRun':42587058258,'nativeRecompiled':False,'installed':False,'wholeCoreCandidateQualified':False,'saleQualified':False,'localHeavyBuild':False,'modelsRun':False,'phoneAccessed':False,'boardAccessed':False}
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets'])
b=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
b['groupedCandidate079']=record
b['activeWindowsAudio20261109'].update(state='WINDOWS_REAL_PUBLIC_AUDIO_IMPORT_PLAYBACK_DELIVERY_REOPEN_PASSED',acceptedRun=42587058258,currentVerificationSource='af03118156e59a17ad48bae3e54f573c690108be',savedOriginalByteIdentical=True,deliveredMp3ReimportedAndDecoded=True,ordinaryShellPasteQualified=True,physicalListeningQualified=False)
b['groupedMeetingUiSource20261109'].update(state='GROUPED_UI_SOURCE_CHECKS_PASSED_NOT_YET_PACKAGED',sourceCommit='5e8909e514866d6b513bf436636495f273eba77b',acceptedRun=42584662552,nativePackaged=False)
b['next']='同一批Windows079远端正常构建、包内核对和受影响普通界面确认；公开AI事实审阅链已实际跑通，保留原ASR错误/人工修订边界。随后Android/录音卡按原待办联调，不重跑未受影响旧检查。'
assert d['quality_targets']==quality and p.read_bytes()==raw
temp=p.with_suffix('.core079.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,p)
shutil.copyfile(p,S/'docs/product_backlog.json')
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'))
scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<approved-publisher>','exec'),scope)
paths=names+['apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json','tools/check_type_build_target.py','tools/build_windows_candidate_ci.py','.github/workflows/windows-candidate.yml','docs/product_backlog.json']
head=scope['ship'](S,paths,'[windows-build] Group the meeting audio, AI next steps and content delivery into Windows079')
record.update(sourceCommit=head,remoteReadbackConfirmed=True)
(O/'source-freeze.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(record,ensure_ascii=False))
