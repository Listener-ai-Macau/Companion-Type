from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12');P=R/rel;F=P/'unified066';Win=P/'windows060-word062'
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
candidate=read(F/'apk66-verification.json');source=read(F/'source.json');install=read(Win/'installation.json');ui=read(Win/'installed-native-ui/result.json')
assert sha(Path(candidate['apk']))==candidate['sha256'] and ui['publicContentPreserved'] and install['dataManifestIdentical']
shared=R/'docs/handoffs/20261106-companion-device-management'
ota=read(shared/'phone064-metric-verdict.json');assert ota['result']=='PASS'
inherited={'source':str(shared/'phone064-metric-verdict.json'),'functionalResult':ota['functionalResult'],'metrics':ota['metrics'],'scope':'Inherited completed ordinary064/FW66688 upgrade evidence. Do not repeat unchanged OTA; this is not pause/playback/delete or066 actual Word qualification.'}
write(P/'inherited064-ota-final-summary.json',inherited)
record={'at':now,'state':'WINDOWS060_INSTALLED_PROTECTED_ANDROID066_UNIFIED_CANDIDATE_READY_ACTUAL_PHONE_STILL_PENDING',
 'windowsInstalled':install,'windowsInstalledIsolatedPublicUi':ui,'androidCandidate':candidate,'androidCandidateSource':source,'inheritedActualOta':inherited,
 'androidActualTransportAlreadyVerifiedFormats':['txt','markdown','word','pdf','pptx','xlsx','mindmap','png'],
 'androidPublicCopyActuallyPasted':True,'word066FinalActualPhoneSchemaPassed':False,
 'remaining':['Shared phone locked/current OTA reception owner still holds lease; no own phone install or input until actual handoff.',
  'Actual unified latest Android Word save/share and final OpenXML validation; do not downgrade if another newer version appears.',
  'Only self-created new board recording pause/resume/stop, receive, full playback, controlled deletion cancel/confirm and original audio save/share.',
  'Return retained original phone library; current shared public test library must not be called original.',
  'Windows native system SaveAs and local share-sheet recipient still unverified; installed-source preview is a separate result.'],
 'originalAppDataChangedByWindowsUpgrade':False,'originalWindowsFilesCount':install['existingDataFiles'],
 'noModelsRun':True,'fullPriority12Complete':False,'wholeProductQualified':False,
 'estimate':'Original plan remains4-8 effective engineering/acceptance hours, roughly one working day for these two scopes, excluding unknown shared-device wait; new substantive defects can change it. Not a whole-product sale date.'}
write(P/'latest-result.json',record)
canonical=R/'docs/product_backlog.json';raw=canonical.read_bytes();data=json.loads(raw)
front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055'];current=task['priority12Actual']
task['state']=record['state'];task['candidateVersion']='0.1.66/code66, unified, not installed';task['currentCandidateSourceCommit']=source['frontendSourceCommit']
task['latestWindowsInstalled']={'version':'0.1.60','receipt':str(Win/'installation.json'),'existingFilesByteIdentical':245,'source':install['sourceCommit']}
task['ownerPriority12']['state']=record['state']
current.update(state=record['state'],at=now,candidate=candidate,candidateSource=source,latestResult=str(P/'latest-result.json'),windowsInstalled060=install,windowsInstalledNativeUi060=ui,inheritedActualOta064=inherited)
current['next']='当前手机锁屏且065收取实测占用尚未交回，不抢占/不降级。释放后重查实际版本；若无更新者，用已合并Word062原生212ec44d与最新Java传输的066，先实际Word保存/分享及SDK核验，再仅新录音控制/回听/受控删除/原音交付，最后切原库。Windows060已原位静默更新及隔离公开资料启动/八格式预览通过，系统SaveAs/分享接收端仍开。'
task['next']=current['next'];task['currentBoardLeaseHeld']=False
coverage=front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
for row in coverage:
    if row['id']=='exports':
        row['engineering']['windows060WordCandidate'].update(installed=True,installationReceipt=str(Win/'installation.json'),originalFilesIdentical=245,installedNativeEightFormatPreview=True)
        row['engineering']['androidActualPriority12'].update(candidate='0.1.66 unified, uninstalled',receipt=str(P/'latest-result.json'))
        row['current']='Windows060已原位安装：原245资料文件一致，实际安装程序隔离公开库八格式预览/浅深色通过，系统保存与分享接收未验。Android普通保存/本机分享八格式、实际粘贴已验；Word Unicode与共享页脚修复合入066同签名候选，保最新2M/升级回执修复，待当前065实测交回后实际复验。原音/SRT及AI外部表样填字段和完整交付仍开。'
    elif row['id']=='updates':
        row['engineering']['windows060Candidate'].update(installed=True,installationReceipt=str(Win/'installation.json'))
        row['current']='Windows060实装及原245文件一致；Android最新共享观察065，066合并候选未装。本侧复用064/FW66688普通OTA指标与原34目录保持通过证据，不重复升级；最新收取速度、恢复资格、清配对和正式签名等原范围仍沿原待办。'
assert canonical.read_bytes()==raw,'Concurrent canonical backlog mutation; retry from current'
temp=canonical.with_suffix('.unified066.tmp');write(temp,data);os.replace(temp,canonical)
entry=f'''\n\n## {now}｜前两项交付点：Windows060静默实装保原245文件；Android066合并Word与最新传输，真机闭环仍开放\n\nWindows先确认原0.1.52且无Companion进程；按已授权前两项静默升级060（MSI2a1ddda2、源2b5f3529），退出0，原245个应用资料文件长度/SHA全同，实装exe9da28961/dll6589a071与已验包一致。私密保护清单、原元数据及安装日志仅保本地E缓存，未上传；未打开Owner日用资料/窗口。实际已安装程序用独立虚构文字库后台启动，普通八格式预览、主题及打包资产核对通过，源内容保留、剪贴板未动；没有系统保存/分享面板或设备/模型操作。Tauri bundle仅把Cargo.toml换行改为LF，精确对照原提交后恢复CRLF；所有冻结Windows源哈希再一致，未重编，不是产品语义变化。\n\n源分支继续合并他方已提交a688c28/63e9a29/c542833对应升级迟到耐久回执与录音/OTA共用2M偏好，后端561708a9与该生产Java源全同， native及共用Windows源和Word062已验4d86908f相同。只重新编译Java，受影响Unicode、真实120B/112B状态回调、升级回执检查通过；复用Word062原生212ec44d与其它AAR条目逐字节，未训练/推理。新AAR收据去掉不适用的累积历史顶层标记，旧062原件单列保留。主源2e093cc8已远端；066同签名候选{candidate['sha256']}，包内网页、三个native及16KiB均核对，未装。源码、候选与实际UI资格分开。\n\n沿共享现成终态复用064/FW66688普通OTA：55.466KiB/s，完整118.764秒，传完至核对92.259秒，原34目录与空间未变，实际新固件身份和被动UART相符。保留此前失败，不重复升级；这不关闭066 Word或控制/回听/删除。现共享065第二场收取因物理锁屏暂停并在原会话询问就绪，仍持原占用。本侧未再控制手机，也不重复弹窗，不关闭正被其使用的虚屏2。原库保留但尚未切回。前两项未全完成；其它原36项和整机售卖/模型继续未关闭。下一动作见原ownerDevicePhoneClosure055.priority12Actual.next。\n'''
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:stream.write(entry)
with (R/'docs/board_operations.md').open('a',encoding='utf8') as stream:
    stream.write(f'\n- **前端合并候选 {now}**：未抢当前占用；066候选（主源2e093cc8/后端561708a9、native212ec44d）已保Word062与最新065纯Java接收/OTA修复，同签名未装。当前原库切回、实际Word/暂停续录回听及删除仍待；虚屏2供当前实测使用，不提前关闭。Windows060已独立静默实装且原245文件同。接续先取当前占用终态/实际版本，勿旧062降级。\n')
target=S/rel
shutil.copytree(F,target/'unified066',dirs_exist_ok=True)
for name in ['latest-result.json','inherited064-ota-final-summary.json']:shutil.copy2(P/name,target/name)
tw=target/'windows060-word062'
for name in ['installation.json','post-bundle-source-readback.json','Cargo-after-tauri-bundle-line-endings.txt']:shutil.copy2(Win/name,tw/name)
shutil.copytree(Win/'installed-native-ui',tw/'installed-native-ui',dirs_exist_ok=True)
qa=S/'tools/qa/phone_closure059'
for name in ['package_unified066_word_and_transport.py','preserve_unified066_delivery.py','prepare_install_windows060.py','install_windows060_verified.py','prepare_installed_windows060_check.py','test_installed_windows060_readonly.py']:shutil.copy2(W/name,qa/name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
    p=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md')
git('add','-f','--',rel/'unified066',rel/'latest-result.json',rel/'inherited064-ota-final-summary.json',rel/'windows060-word062/installation.json',rel/'windows060-word062/post-bundle-source-readback.json',rel/'windows060-word062/Cargo-after-tauri-bundle-line-endings.txt',rel/'windows060-word062/installed-native-ui')
git('commit','-m','Preserve Windows060 installed data protection and unified Android066 candidate with actual remaining scope')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
for file in [Path(candidate['apk']),P/'latest-result.json',Win/'installation.json']:
    path=rel/file.relative_to(P);p=subprocess.run(['git','show',pin+':'+path.as_posix()],cwd=S,capture_output=True)
    assert p.returncode==0 and hashlib.sha256(p.stdout).hexdigest()==sha(file)
write(P/'remote-final-readback.json',{'commit':pin,'remoteReadback':True,'candidateAndLatestResultAndInstallationBlobsVerified':True,'android066Installed':False,'windows060Installed':True,'fullPriority12Complete':False})
print(json.dumps({'commit':pin,'remoteReadback':True,'windows060Installed':True,'windowsOriginalFilesIdentical':245,'android066CandidateProtected':True,'android066Installed':False,'fullPriority12Complete':False},ensure_ascii=False),flush=True)
