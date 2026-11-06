"""Stop only the owned probe, preserve exact unresolved state, no more UI input."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,psutil,shutil,subprocess
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share068');O=R/rel
m=json.loads((O/'probe-gui-session.json').read_text(encoding='utf8'));closed=True
if psutil.pid_exists(m['pid']):
 p=psutil.Process(m['pid']);assert p.create_time()==m['createTime'] and Path(p.exe()).resolve()==Path(m['exe']).resolve();p.terminate();p.wait(timeout=10)
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'at':now,'state':'WINDOWS067_ACTUAL_SHARE_TARGET_ENUMERATION_FAILED_ROOT_UNCONFIRMED_UI_STOPPED_BY_OWNER_ESCAPE',
 'ownerQuote':'需要继续推进到售卖标准','scope':'Continue original priority1/2 and existing sale backlog; no new feature tree, model or device takeover.',
 'installedProductUnchanged':'Windows0.1.67','actualProductShare':{'systemPanelOpened':True,'panelMessage':'重试，我们无法为你显示所有共享方法。','recipientDelivered':False},
 'counterfactuals':{'samePublicPdfExplorerShareTargetsListed':True,'localQaTargetListedFromExplorer':True,'normalWindowsProfileEnvironmentStillFailsFromProduct':True,'productAndExplorerBothElevatedDefaultType1':True,'exactProductPrepareCodeWorkerToStaCanReadOneFile':True},
 'notProven':['Which product/WinRT/STA/event-loop data-request condition causes the target enumeration failure.','Minimal native GUI baseline versus populating existing request.Data; window launched, no share action before physical Escape.','Local QA target actual activation/receipt; only built/installed/listed so far.'],
 'next':'先对照最小原生窗口baseline与填充现有request.Data的实际系统结果，只有新证据支持才修产品；不重复正常profile/权限相同对照。此次Computer Use被Owner物理Esc停止，本轮不再输入。后续前台实际对照需Owner恢复该操作；后台可接续原待办其它项。手机仍按共享记录等待既有满盘收尾/回收流程释放，不抢占。',
 'ownProbeClosed':closed,'ownProductAndPublicExplorerClosedBeforeProbe':True,'noFurtherUiInputAfterEscape':True,'qaRecipientInstalled':True,'qaRecipientIdentity':'Denzic.Companion.PublicShareQA068','qaRecipientHasNetworkCapability':False,
 'originalClipboardUntouchedThisBatch':True,'modelsRun':False,'ownerAcceptance':False,'fullPriority12Complete':False,'wholeProductQualified':False}
(O/'progress-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
cache=Path('E:/CodexData/Companion/.build-cache/windows-share068/native-probe');out=O/'native-probe-source';out.mkdir(exist_ok=True)
for name in ['Cargo.toml','Cargo.lock']:shutil.copy2(cache/name,out/name)
shutil.copytree(cache/'src',out/'src',dirs_exist_ok=True)
canonical=R/'docs/product_backlog.json';raw=canonical.read_bytes();data=json.loads(raw);front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['windowsShare068']=record;task['state']=record['state'];task['next']=record['next'];task['ownerPriority12']['latestContinuation']={'at':now,'ownerQuote':record['ownerQuote'],'meaning':'Continue original sale requirements and priority1/2; no scope cancellation.'};task['ownerPriority12']['state']=record['state'];task['ownerPriority12']['next']=record['next'];task['priority12Actual']['next']=record['next']
coverage=front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
for row in coverage:
 if row['id']=='exports':
  row['current']='Windows067已安装，原245文件不变；八格式实际系统保存/取消/内容通过，复制文字匹配。普通App真实系统分享打开后显示无法列出共享方式；资源管理器同公开PDF可列本机接收应用，正常Windows环境仍失败，根因待定位。最小原生窗口对照被Owner物理Esc停止，未发文件。Android066合并Word候选待共享手机释放后实验，原音/SRT/AI填外部表样及完整交付仍开。'
  row['engineering']['windowsShare068']={'receipt':str(O/'progress-result.json'),'actualProductShare':'FAILED_TARGET_ENUMERATION','recipientDelivered':False,'userStoppedUi':True,'readyForOwnerAcceptance':False}
assert canonical.read_bytes()==raw,'Concurrent backlog update, preserve receipt and retry fresh'
temp=canonical.with_suffix('.share068.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,canonical)
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:
 stream.write(f'''\n\n## {now}｜售卖标准续作：真实Windows分享暴露未交付缺陷，对照保留；Owner Esc停止前台\n\n承接Owner“需要继续推进到售卖标准”，仍沿原前两项/36行范围，Windows067及已验八格式保存不回退。共享板/手机原满空间17段长录、回收后再录流程仍占用，本侧无板/手机操作、无模型。准备本机ShareTarget QA068：Windows SDK/C++WinRT最小App，精确拒绝非本轮公开标题、只接1文件/32MiB，复制且不写来源，无Internet/联系人/宽泛文件能力。微软Windows11官方AllowUnsigned/OID测试路径已安装匹配exe，未变开发者模式/证书/UAC/隐私/安全设置。首编缺FileProperties头与guid帮助函数错误修正后构建通过；它只是工具准备，不算产品交付。\n\n前台动作前Owner明确回复“现在可以，集中验完”；只用公开虚构库，Windows067原实装exe未变。实际普通选择原文/PDF→系统面板显示“重试，我们无法为你显示所有共享方法”；App原反馈只说已打开面板并明确发送以接收应用为准，没有收件成功事实。新开资源管理器仅本轮同PDF的UUID缓存目录，普通共享可列本机QA/其它接收应用；未点联系人、微信、Outlook，未发送外部。为区分条件，关闭第一个App后同exe/同虚构源/明确状态与WebView隔离路径，恢复正常USERPROFILE/APPDATA/LOCALAPPDATA重验仍同失败；本侧App和Explorer均提升DefaultType1，不能归因两者权限不同。日志源无相关可取错误。未据正常环境对照改用户系统。\n\n最小Rust探针直接复制生产content_handoff prepare，MTA工作线程退出后STA仍能读取标题/StorageItems/1文件路径，排除基本文件不可读；不证明跨进程系统分享可用。准备小原生窗口对照原SetData与微软推荐填充request.Data，保编译准备失败；窗口刚启动，Computer Use报告Owner物理Esc停止，尚无该探针点击/结果。立即停止所有前台输入，精确验证PID/创建时间/exe后仅关闭自身探针；此前测试App/新文件窗口已关闭。原剪贴板本轮未动，亦未恢复已退役OLE方式。不能把工具/对照当Share功能完成。\n\n结果与原失败在{O/'progress-result.json'}，本轮无产品源码修复/新产品构建/安装；Windows仍067，真实Share接收未合格。根因未确认，下一步用最小对照区分，不重跑已失败profile或重复打包。前两项/整机售卖继续未完成，原客户、模型和硬件缺口均保留。\n''')
dest=S/rel;shutil.copytree(O,dest,dirs_exist_ok=True)
qa=S/'tools/qa/phone_closure059';shutil.copytree(W/'windows_shareqa068',qa/'windows_shareqa068',dirs_exist_ok=True)
for name in ['build_windows_shareqa068.py','install_windows_shareqa068.ps1','read_windows_share068_events.ps1','windows_share068_session.py','prepare_share068_probe.py','run_share068_probe_gui.py','close_preserve_share068_interrupted.py']:shutil.copy2(W/name,qa/name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 p=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,(p.stdout+p.stderr)[-2500:];return p.stdout.strip()
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md');git('add','-f','--',rel)
git('commit','-m','Retain actual Windows share failure and discriminating native probe workpoint')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
receipt={'commit':pin,'remoteConfirmed':True,'ownerStoppedUi':True,'ownProbeClosed':True,'actualShareQualified':False,'wholeProductQualified':False}
(O/'remote-readback.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt),flush=True)
