from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share070');O=R/rel
source=json.loads((O/'source-release.json').read_text(encoding='utf8'))
bundle=json.loads((O/'windows-verification.json').read_text(encoding='utf8'))
checks=json.loads((O/'light-check-result.json').read_text(encoding='utf8'))
native=json.loads((O/'native-test-result.json').read_text(encoding='utf8'))
release=json.loads((O/'cargo-release.json').read_text(encoding='utf8'))
installed=json.loads((O/'installation.json').read_text(encoding='utf8')) if (O/'installation.json').exists() else None
assert source['sourceCommit']==bundle['sourceCommit']==release['sourceCommit']
assert release['exitCode']==0 and all(x['exitCode']==0 for x in checks)
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={
 'at':now,'state':'WINDOWS068_FOLDER_SHARE_INSTALLED_BACKGROUND_CHECKED_ACTUAL_RECIPIENT_PENDING' if installed else 'WINDOWS068_FOLDER_SHARE_MSI_PREPARED_ACTUAL_INSTALL_AND_RECIPIENT_PENDING',
 'ownerQuote':'继续吧, 你看看能不能不用computeruse方式处理',
 'userBenefit':'Windows所选内容和原音/MP3均有明确的文件夹分享入口，系统面板失败后可自行选择另一条路径；请求面板/文件夹不再显示为文件已保存或已发送。',
 'version':'0.1.68','sourceCommit':source['sourceCommit'],'sourceRemoteConfirmed':source['remoteReadback'],
 'msi':bundle['msi'],'msiSha256':bundle['msiSha256'],'embeddedExeSha256':bundle['embeddedExeSha256'],'dllSha256':bundle['dllSha256'],
 'installed':bool(installed),'installation':installed,
 'nativeTests':native,'frontendAndCompileChecks':checks,
 'releaseSeconds':release['wallSeconds'],'releasePeakOwnRssMiB':release.get('peakOwnRssMiB'),'releaseCpuSlots':[12,13],'jobs':1,
 'computerUse':False,'uiOpened':False,'clipboardTouched':False,'modelsRun':False,'deviceIo':False,
 'ordinarySystemShareFixed':False,'actualExplorerSelectionObserved':False,'actualRecipientReceived':False,
 'fullPriority12Complete':False,'wholeProductQualified':False,
 'boundaries':[
  'Native tests actually resolve the exact existing public Unicode/symbol/emoji file through Shell PIDL and check it is unchanged; reject relative path, directory and deleted file. Tests intentionally never invoke Explorer or SharePicker.',
  'Explicit folder route reuses frozen content selection/hash or original-audio copy checks, prepares only its own new immutable cache file, and calls documented SHOpenFolderAndSelectItems on the existing UI thread. No cmd/ShellExecute strings, undocumented CLSID route, ACL changes, recipient selection or automatic fallback.',
  'Actual Explorer opening/selection and QA recipient byte receipt are still pending. A documented API, passing tests, matching installer and successful installation do not qualify the unseen ordinary system handoff.',
  'Old 068/069 WinRT picker failures remain open; request-owned candidate was reverted, not shipped. No repeat profile/elevation/IPC trials or UAC/security/privacy changes.',
  'Shared firmware/phone lease remains with original embedded flow. No phone/board query, install, downgrade or library switch was done here. Android066 Word and affected ordinary flow plus return to original library remain pending.',
 ],
 'next':'优先在不占日用前台的可用条件下完成Windows068文件夹真实选中文件及本机QA收件；未提供条件则保留未完成，推进原待办P0安卓可恢复删除等可独立软件工作。手机/板等待现占用释放后先核最新实际版本，不能降级或直接套旧066；把原库切回及受影响真机流程收齐。'
}
(O/'delivery-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
canonical=R/'docs/product_backlog.json';raw=canonical.read_bytes();data=json.loads(raw)
front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['windowsShare070']=record;task['state']=record['state'];task['next']=record['next']
task['ownerPriority12']['state']=record['state'];task['ownerPriority12']['next']=record['next'];task['priority12Actual']['next']=record['next']
task['ownerPriority12']['latestContinuation']={'at':now,'ownerQuote':record['ownerQuote'],'meaning':'Continue original sale backlog, implement and verify without Computer Use or occupying daily desktop.'}
if installed:
 task['latestWindowsInstalled']={'version':'0.1.68','receipt':str(O/'installation.json'),'existingFilesByteIdentical':installed['existingDataFiles'],'source':source['sourceCommit']}
for item in front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']:
 if item['id']=='exports':
  item['engineering']['windowsShare070']={'receipt':str(O/'delivery-result.json'),'version':'0.1.68','installed':bool(installed),'selectedContentAndAudioFolderSharingImplemented':True,'backgroundShellPathVerified':True,'actualRecipientVerified':False,'computerUse':False}
  item['engineering']['label']='Windows068文件夹分享与状态修复已安装、后台核对；真实收件及安卓Word/录控等余项未齐' if installed else 'Windows068文件夹分享候选已准备；安装/真实收件及安卓余项未齐'
  item['engineering']['readyForOwnerAcceptance']=False
assert canonical.read_bytes()==raw,'Concurrent canonical update; re-read before retry'
tmp=canonical.with_suffix('.share070.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(tmp,canonical)
with (R/'docs/development_log.md').open('a',encoding='utf8') as f:
 f.write(f'''\n\n## {now}｜按Owner不用Computer Use接续：Windows068明确文件夹分享与请求状态完成，实际收件仍待验\n\n承接Owner“继续吧, 你看看能不能不用computeruse方式处理”。本轮没有Computer Use、键鼠/桌面自动化、窗口启动、剪贴板、模型或设备IO。沿原优先1/2修Windows分享阻断，不再重复068/069失败对照，也不调用私有Windows.ModernShareFlyout或Share With。参考微软公开SHOpenFolderAndSelectItems文档，新增显式文件夹分享；所选内容与原音/MP3均复用已冻结选择/来源校验和本机新副本，通过PIDL定位准确文件，避免命令字符串或更改网络共享权限。正常系统分享失败不自动打开别的应用，用户需自己选择备用路径。UI把分享请求与保存/发送分开，录音分享状态不再记saved。\n\n首次类型检查发现通用导出反馈类型漏加opened，已补后Windows与mobile均通过；原失败保留。原生完整测试编译190.537秒，5项针对检查通过，新增实际Shell文件路径往返覆盖中文、#、%、&、emoji，拒绝相对/目录/已删文件，原文件字节未变，未打开资源管理器。组件检查验证准确内容选择/hash、显式folder参数、错误状态不报成功且不自动备用；生产Windows前端构建与许可证校验通过。整机曾97%内存、原测试编译RSS约2.3GiB，准备停止时进程已经完成，没有实际终止；退出后可用内存回到约4.2GiB。后续顺序检查，release单作业/两CPU/低优先级，有实际持续内存压力则只停止本轮自有进程，不动Owner程序。\n\n源码{source['sourceCommit']}已远端核验，release {release['wallSeconds']}秒、峰值本轮进程RSS {release.get('peakOwnRssMiB')}MiB。MSI版本、同源EXE/DLL、许可证、升级身份和禁止降级核对完成。实际安装={bool(installed)}；用户资料保持结果以installation.json为准。未实际打开Explorer或选择本机QA，系统直开面板原缺陷仍开放，不能把这批后台结果写成分享已通过或整机可售。手机和板仍由原嵌软流程占用，Android新版本/原库切回/其余普通流程沿原待办继续。下一步见windowsShare070，不另建任务树、不再催Owner重复确认。\n''')

dest=S/rel;dest.mkdir(parents=True,exist_ok=True)
names=['delivery-result.json','source-release.json','native-test-result.json','targeted-native-tests.log','light-check-result.json','component-light.log','windows-types-light.log','mobile-types-light.log','frontend-check-result.json','frontend-0.log','frontend-1.log','frontend-2.log','windows-web-build.log','source-frozen.json','cargo-release.json','native-preflight.json','bundle-preflight.json','windows-verification.json','installation.json']
for name in names:
 if (O/name).exists():shutil.copy2(O/name,dest/name)
shutil.copy2(Path(bundle['msi']),dest/Path(bundle['msi']).name)
qa=S/'tools/qa/phone_closure059'
for name in ['run_share070_checks.py','check_share070_light.py','prepare_windows068_folder_share.py','build_windows068_folder_share.py','package_windows068_folder_share.py','install_windows068_folder_share.py','preserve_windows068_folder_share.py']:
 shutil.copy2(W/name,qa/name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 p=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
git('add','--','docs/product_backlog.json','docs/development_log.md','tools/qa/phone_closure059');git('add','-f','--',rel)
git('-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check');git('commit','-m','Preserve Windows068 folder sharing delivery and explicit remaining system handoff gap')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin','HEAD:refs/heads/'+branch)
assert git('ls-remote','origin','refs/heads/'+branch).split()[0]==pin
# Read back the actual installer blob from the remote-confirmed commit too.
blob=subprocess.run(['git','show',pin+':'+(rel/Path(bundle['msi']).name).as_posix()],cwd=S,capture_output=True,check=True).stdout
assert hashlib.sha256(blob).hexdigest()==bundle['msiSha256']
receipt={'protectedCommit':pin,'remoteReadbackConfirmed':True,'installerBlobMatched':True,'sourceCommit':source['sourceCommit'],'version':'0.1.68','installed':bool(installed),'actualRecipientVerified':False,'computerUse':False}
(O/'remote-readback.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
print(json.dumps(receipt),flush=True)
