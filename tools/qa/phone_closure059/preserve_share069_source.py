from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share069');O=R/rel
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 p=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,(p.stdout+p.stderr)[-2500:];return p.stdout.strip()
result=json.loads((O/'source-test-result.json').read_text(encoding='utf8'));probe=json.loads((O/'dual-probe-result.json').read_text(encoding='utf8'))
source=S/'apps/windows/src-tauri/src/content_handoff.rs';assert hashlib.sha256(source.read_bytes()).hexdigest()==result['sourceSha256']==probe['candidateSourceSha256']
git('add','--','apps/windows/src-tauri/src/content_handoff.rs');git('diff','--cached','--check');git('commit','-m','Preserve Windows request-owned share context with apartment-safe file references')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'at':now,'state':'SHARE069_SOURCE_CONTEXT_REPAIR_AND_BACKGROUND_IPC_PASSED_SYSTEM_PICKER_UNVERIFIED','ownerQuote':'继续推进吧, 尽量不要computeruse','sourceCommit':pin,'remoteSourceConfirmed':True,'sourceSha256':result['sourceSha256'],'sourceTests':result,'backgroundIpc':probe,
 'decisionBasis':{'baseline':'Installed067 ordinary share sheet fails target enumeration; same public PDF Explorer share succeeds. Normal profile environment still fails; same elevation; cross-process package transfer now proved byte-identical in background.',
 'ruledOut':'Do not rewrite renderer/ASR, blame file corruption or repeat the normal-profile/elevation comparison. Independent IPC alone does not qualify system SharePicker.',
 'candidate':'Follow official Microsoft desktop/UWP samples: fill request.Data synchronously from pre-resolved file; preserve Windows-owned source metadata. Use AgileReference to resolve StorageFile on callback apartment; no unsafe Send override. Per-request file preparation errors use FailWithDisplayText with save fallback.',
 'stopCondition':'Keep source candidate pending until real picker/receiver path is observed; compare frozen old/current native methods before expensive product release. Do not call backend IPC a system-share fix.'},
 'manualTwoButtonProbeReady':True,'manualReplyPending':True,'computerUseThisBatch':False,'modelsRun':False,'productBuildOrInstallThisBatch':False,'installedProduct':'Windows0.1.67','wholeProductQualified':False}
(O/'progress-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
canonical=R/'docs/product_backlog.json';raw=canonical.read_bytes();data=json.loads(raw);front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['windowsShare069']=record;task['state']=record['state'];task['ownerPriority12']['latestContinuation']={'at':now,'ownerQuote':record['ownerQuote'],'meaning':'Resume original sale target; prefer background work and avoid Computer Use.'}
task['next']='Windows分享069源与针对检查/跨进程原文件核对已远端；真实Picker未验，暂不构建/替换067。已备同窗口原方式/修复候选手工对照，不用Computer Use；等Owner选择是否亲点，未答不打开桌面。并行推进不依赖该动作的原非模型项。手机/板沿现占用（当前FW66690满空间238/回收再录）等待释放，不安装066或抢设备。'
task['ownerPriority12']['state']=record['state'];task['ownerPriority12']['next']=task['next'];task['priority12Actual']['next']=task['next']
for item in front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']:
 if item['id']=='exports':item['engineering']['windowsShare069']={'receipt':str(O/'progress-result.json'),'sourceCommit':pin,'backgroundSourceAndIpcChecked':True,'actualSystemShareQualified':False,'installedVersion':'0.1.67'}
assert canonical.read_bytes()==raw,'Concurrent update, re-read canonical before retry'
temp=canonical.with_suffix('.share069.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,canonical)
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:
 stream.write(f'''\n\n## {now}｜按Owner尽量不用Computer Use接续：分享069源码候选与独立进程文件核对通过，系统Picker仍未验证\n\n承接“继续推进吧, 尽量不要computeruse”，本轮无Computer Use、桌面输入、模型或板/手机IO。复用068原失败，不重复profile/提升权限对照。新增纯后台COM封送：直接复制冻结60166生产prepare，工作线程MTA退出后STA可读，独立进程通过CoMarshal/CoUnmarshal读取WinRT StorageFile并与原72558B公开PDF逐字节一致。原包FileTypes列表0是观察；微软官方普通文件样例也未手填此列表，因此不凭此断言根因或盲补扩展名。COM封送blob仅留本机E，不入远端。\n\n按微软官方Windows-classic-samples WPF及Windows-universal-samples ShareFiles共同模式改content_handoff：预先取得文件，实际DataRequested填系统已有request.Data，而非替换整个DataPackage；保已有Windows来源上下文，复制/只读文件语义和失败保存回退保留。首次StorageFile裸跨线程编译被Send约束拒绝，改用windows-core AgileReference正常代理，不增加unsafe Send；失败编译原件保留。针对产品源码检查通过，含请求对象身份/已有ApplicationName上下文/准确单文件与Copy语义。独立进程再确认原方案和新候选都能拿到完整72558B，新候选来源上下文也完整保留。该结果支持源改写保信息，不证明已修复Picker枚举。源码{pin}远端核对，仍未产品原生构建/安装，日用保持067。\n\n同一最小原生窗口已备两个普通按钮，分别冻结旧方式/实际新候选，让手工对照能区分Tauri窗口路径与DataRequest填充；仅本机公开资料，不运行新窗口。已异步给Owner“我来手动点/暂时不方便”选择，等待回复时不打开桌面；后台继续可独立原事项。手机原嵌软工作当前FW66690真实满空间238、后续回收再录在途，本侧不抢占。原SharePicker接收、Android066Word/录控回听与原库切回、其它非模型售卖缺口继续未完成，source/tests/IPC准备不计实际销售交付。\n''')
dest=S/rel;shutil.copytree(O,dest,dirs_exist_ok=True)
qa=S/'tools/qa/phone_closure059';shutil.copytree(W/'windows_shareqa068',qa/'windows_shareqa068',dirs_exist_ok=True)
for name in ['prepare_share068_probe.py','run_share069_source_tests.py','prepare_share069_native_probe.py','preserve_share069_source.py']:shutil.copy2(W/name,qa/name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md');git('add','-f','--',rel)
git('commit','-m','Record background share repair checks and preserve real picker acceptance gap')
protected=git('rev-parse','HEAD');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}');assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==protected
receipt={'sourceCommit':pin,'protectedCommit':protected,'remoteConfirmed':True,'actualSystemShareQualified':False,'computerUseThisBatch':False}
(O/'remote-readback.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt),flush=True)
