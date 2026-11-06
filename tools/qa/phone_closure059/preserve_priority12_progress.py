from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059')
P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';F=P/'word062'
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def read(path):return json.loads(path.read_text(encoding='utf8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
source=read(F/'source.json');apk=read(F/'apk62-verification.json');assert sha(Path(apk['apk']))==apk['sha256']
saves=read(C/'actual-saf-saves.json');shares=read(C/'actual-share-receipts.json');assert len(saves)==8 and len({x['format'] for x in shares})==8
installed=read(C/'installation061.json');virtual=read(C/'virtual-session.json')
for name in ['installation059.json','installation061.json','actual-saf-saves.json','actual-share-receipts.json','content-triage-other-formats.json','openxml-validation.json']:
    shutil.copy2(C/name,P/name)
samples=P/'public-samples';samples.mkdir(exist_ok=True)
for file in (C/'saved').glob('*'):
    if file.is_file():shutil.copy2(file,samples/file.name)
if (C/'saved/pdf-pages').exists():shutil.copytree(C/'saved/pdf-pages',samples/'pdf-pages',dirs_exist_ok=True)
shutil.copytree(C/'shared',P/'public-recipient',dirs_exist_ok=True)
qa=read(P/'share-receiver-build.json');shutil.copy2(qa['apk'],P/Path(qa['apk']).name)
driver=Path('E:/CodexData/Companion/.build-cache/device-phone055/native-ui059/Companion-Native-UI059-QA.apk');shutil.copy2(driver,P/driver.name)
write(P/'virtual-display-actual.json',{'displayId':2,'serverPid':virtual['pid'],'newDisplayOnly':True,'ownContentOnlyAndOwnFocusFlagsObserved':True,
    'noAudioForwarding':True,'noClipboardAutosync':True,'noPhysicalScreenCapture':True,'physicalDisplayInputInjected':False,
    'nativeOpenDocumentAndCreateDocumentAndChooserOnDisplay2Observed':True,
    'physicalOwnerAppsOrLockStateChangedDuringRun':True,'audioPlaybackIsolation':False,
    'currentLifecycle':'Shared OTA flow currently uses this display after recorded owner handoff. Do not destroy while its OTA/verification is active; finish it and return original library before final cleanup.',
    'mainAppVersionLastProven':'0.1.61/code61','ordinaryPhysicalPhoneDisplayAcceptanceNotClaimed':True})
failures=[
 {'kind':'PRODUCT_ANDROID059_WORD_XML_INVALID','detail':'Android DOM Transformer emitted separate surrogate references. Original actual file retained in word061; custom scalar-preserving serializer independently roundtripped and actual061 body became valid.'},
 {'kind':'PRODUCT_SHARED_WORD_FOOTER_SCHEMA','detail':'After Unicode fix, Microsoft OpenXML found one footer w:rPr color/size ordering violation in actual061. Shared Rust source corrected in both repositories; native062 compiled and exact footer bytes found; controlled host diagnostic0 schema errors. Actual062 UI export still pending.'},
 {'kind':'QA_INSTALL_CANCELLED','detail':'First local share recipient install ended INSTALL_FAILED_USER_RESTRICTED/cancelled. Later explicit no-incremental install succeeded. No security setting disabled or account credentials used.'},
 {'kind':'QA_PRIVATE_CLIPBOARD_PANEL_LAYOUT','detail':'Long public paste pushed verify button outside view. Test recipient capped EditText at8 lines; actual paste and visible verify then succeeded. No product UI defect attributed.'},
 {'kind':'QA_ADB_BINARY_READBACK','detail':'Initial adb shell binary pull transformed bytes/line endings. Raw exec-out and on-device SHA matched receiver and producer exactly; no product payload corruption.'},
 {'kind':'QA_ASYNC_SHARE_RECEIPT','detail':'A chooser tap returned before receiver durable receipt. Bounded wait reused actual completed Word receipt; no unchanged share route rerun.'},
 {'kind':'QA_PNG_CHOOSER_OFFSCREEN','detail':'Image handler list placed local receiver below visible rows. Guard refused offscreen tap; ordinary vertical scroll exposed it, then actual PNG received/hash/grants verified.'},
 {'kind':'QA_BROWSER_CONFIRM_ASSISTANCE','detail':'Fixture setup used normal restore entry, CDP accepted browser confirm, real Android file picker selected public archive; native leftover prompt later cancelled. This assisted fixture setup is not a new complete backup/restore acceptance.'},
 {'kind':'QA_INSTALL_MAIN_ACTIVITY_OBSERVER','detail':'061 installed successfully but initial observer asserted on physical main resumed activity transition. Post-check proved exact installed bytes and571 original app files unchanged; no cause for physical transition asserted.'},
 {'kind':'QA_PACKAGING_CLASS_SET','detail':'Unicode source import/line changes also changed Section debug class bytes; bounded expected family corrected. Reused successful Java tests/compiled classes rather than repeat native compile.'},
 {'kind':'QA_RESUME_SCRIPT','detail':'First packaging resume omitted test_names and stopped before archive write. Added existing test class exclusions and completed source push.'}
]
write(P/'failures-retained.json',failures)
record={'at':now,'state':'ACTUAL_ANDROID_DOCUMENT_TRANSPORT_VERIFIED_WORD062_READY_FINAL_PHONE_AND_RECORDING_PENDING',
    'installedLastProven':installed,'candidate':apk,'candidateSource':source,
    'actualSavedFormats':[x['format'] for x in saves],'actualSharedFormats':sorted({x['format'] for x in shares}),
    'actualSharedHashMatchesProducer':all(x['actualRecipientBytesMatchSource'] for x in shares),
    'actualReadOnlyAndUngrantDenial':all(x['receipt']['readOnly'] and x['receipt']['otherUriDenied'] for x in shares),
    'actualPublicClipboardPasted':True,'contentQualifiedOtherSevenFormats':True,
    'wordUnicodeFixedAndActual061Observed':True,'wordFinalContentQualified':False,
    'wordRemaining':'Install062 or merge into newer candidate after current OTA holder releases, then actual normal Word save/share and Microsoft schema0.',
    'originalLibraryStillRetained':True,'originalLibraryReturnPending':True,
    'newRecordingControlAndFullPlaybackThisTurn':False,'oldBoardAudioPayloadReads':0,'oldBoardDeletes':0,
    'sharedHandoff':{'at':'2026-11-06T15:13:01+08:00','newItem':'Companion手机060真实OTA66687指标验收','recordedReason':'Owner确认前项已做完，授权本轮接续OTA；本侧未关闭他方进程，按明确交接更新记录',
        'meaningForThisTask':'Honor resource handoff, but frontend priority1/2 are still incomplete. No own new card recording has been made; current public library return and062 Word retest are pending. Preserve active virtual display used by the OTA.'},
    'windows':'Shared footer source corrected; desktop binary/package and ordinary SaveAs/share remain outside this actual Android evidence.',
    'next':'After shared66687 OTA final receipt/release, verify actual installed version; install062 only if no newer candidate, else merge. Retest Word affected route, return original library, then only self-created actual-card pause/resume/stop/receive/playback/delete and original-audio save/share. Inherit completed OTA evidence without needless repeat.',
    'modelsRun':False,'customerResult':None,'ownerAccepted':False,'wholeProductQualified':False}
write(P/'progress-result.json',record)
canonical=R/'docs/product_backlog.json';raw=canonical.read_bytes();d=json.loads(raw);front=d['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['priority12Actual']=record;task['state']=record['state'];task['next']=record['next'];task['candidateVersion']='0.1.62/code62, not installed';task['currentCandidateSourceCommit']=source['frontendSourceCommit'];task['latestInstalledVersionObservation']={'version':installed['version'],'receipt':str(P/'installation061.json'),'source':installed['source']};task['currentBoardLeaseHeld']=False
front['state']=record['state'];d['owner_module_execution']['nextBatch'].update(status=record['state'],next=record['next'],at=now)
coverage=front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
for row in coverage:
    if row['id']=='exports':
        row['engineering']['androidActualPriority12']= {'receipt':str(P/'progress-result.json'),'installed':'0.1.61 last proven','candidate':'0.1.62 uninstalled','actualDocumentSaveShareFormats':8,'actualCopyPasted':True,'wordFinalContentQualified':False,'audioAndRemainingOrdinaryFlowPending':True,'ownerAccepted':False}
        row['current']='Android061实装：实际系统保存及本机分享接收覆盖TXT/MD/DOCX/PDF/PPTX/XLSX/mm/PNG，复制文字实际粘贴；Word查出并修了Unicode和共享页脚结构，062待真机最终复验。原音/SRT等剩余实际范围、Windows系统SaveAs/分享与AI外部表样填字段仍开。原Windows052功能与旧Android048证据保留。'
    elif row['id']=='mindmap':row['current']='Windows052完整PNG/mm已交付；Android059在实际系统保存、普通分享接收端验证PNG/mm完整文件，文字源/图像已检查；当前061，062源头Word修复不改导图实现。长图交互及完整真实会后用途仍待。'
    elif row['id']=='updates':row['current']='Android061实装及原位升级资料校验已验，062 Word修复候选已编译签名，未装；Windows052为本侧最后安装证明。共享66686手机OTA功能已记录、速度目标未通过；新66687指标由现占用流程继续。正式发行签名/渠道和整机升级恢复资格仍未齐。'
assert canonical.read_bytes()==raw,'Concurrent canonical write'
tmp=canonical.with_suffix('.priority12-progress.tmp');write(tmp,d);os.replace(tmp,canonical)
entry=f'''\n\n## {now}｜前两项实际推进：手机独立显示验文件链，Word两处源头缺陷修复至062候选；共享OTA接续后继续剩余\n\n实际手机058→059（主源69c58e38/后端c30a775）静默更新、安装字节SHA核对及原562个应用资料文件一致；随后061主源0aebac91/后端34dee9ff、SHAfca337f0实装，原571文件一致。061首次观察器因物理主屏活动前后变化中止，但安装本身成功；后查主屏锁屏/无resume、验收接收端仅在显示2，不归因产品更新失败，也不伪称全程主屏状态未变。未经物理解锁、按键注入、音频采集/转发或Owner桌面接管。\n\n官方scrcpy5.0.1新建显示2，1080×1920/360dpi、OWN_CONTENT_ONLY/OWN_FOCUS、默认退出销毁，关闭音频、剪贴板自动同步和物理输入转发；仅新虚屏视频留本地，不上传。原主屏阅读/视频应用及后续锁屏没有被测试输入接管。源Companion App真实UI、Android安全文件选择器（小米导入/Google创建）和系统分享均在显示2。测试驱动新增非主屏限定UiAutomation，只取显示2根节点、根据实时控件/可见边界向显示2输入。先前WebView残留visible但attached=false识别已纠正；不靠内部业务API冒充普通UI。\n\n使用明确公开虚构056库，仅验证格式/文件交付，不代表ASR、真实会议、AI生成质量或合格音频。通过设置恢复入口/CDP确认及真实系统文件选择导入；遗留原生提示取消，属于辅助资料准备，不新增无辅助恢复资格。实际保存八种格式，实际系统Chooser选择本机无网络/联系人权限接收端八种，接收文件SHA、文件名/MIME/长度匹配生产缓存清单；只读和未授权其它URI拒绝通过。复制四类内容在外部验收端实际粘贴，否定句、负责人/日期、原样符号和来源/未完成人工提示留存。PDF两页渲染与PNG完整图检查无裁切；PPTX/XLSX Microsoft OpenXML0错误；其余文本/原话保留通过。\n\n普通交付抓到两处真实Word缺陷：059的Android DOM Transformer把emoji分成非法UTF16数字实体，实际保存/分享的坏文件均保留；061换成按Unicode标量输出，实际正文合法且字词保留，随后全包SDK再发现原共用Rust页脚w:sz在w:color前，结构1错。该源头在手机后端冻结共用文件与Windows当前源同步改正；后端4d86908f已远端。单作业/低优先级温缓存根crate重编92.641秒，库212ec44d、16KiB/JNI/依赖核对，未改神经网络/模型源或权重、未推理/训练。主源80b34fcd已远端，Android062候选SHA{apk['sha256']}，同签名、包内网页/native精确、ELF/ZIP16KiB核对；未装。新native中确有正确页脚原文且旧顺序不存在；把源页脚应用到061导出副本的明确host诊断得SDK0错，这不是实际062手机输出。Windows源已改但二进制未打包，不当作已交付修复。\n\n相关准备器失败与范围单列failures-retained：首分享验收安装取消后显式非增量安装成功、粘贴框过长推走按钮属QA布局、adb shell二进制回读取法改exec-out、异步接收收据等待、PNG分享应用列表普通滚动后选本机端、首次恢复确认辅助及061活动观察误断、Java内类行号变化的打包预期和一次续包变量缺项。原失败不删、不归因ASR/用户录音损坏。私密文件清单/主屏影像/新旧录音payload不入远端，仅公开文件与摘要证明。\n\n原共享占用本侧13:47接入；15:13:01共享记录按Owner明确交接释放本侧项并改领“Companion手机060真实OTA66687指标验收”。本侧守卫发现项已变即停止后续UI/安装；发现前仅一次显式显示2的自身App前台调用，没有BLE/复位/刷写。只读状态确认对方正在用独立显示区做66687，不能关闭本侧创建的虚屏/安装062打断。承认该资源交接，不把“前项已做完”的交接说法写成前端功能验完：原库仍保留但当前在公开测试库，切回未做，未新录一场实卡，暂停续录/完整回听/受控新删除与原音导出仍开。当前无本侧BLE/COM/SWD句柄。接续必须先取其终态/实际版本，再062或更新的合并候选验证Word，切原库及跑新样本，复用已通过OTA、不另抢占。36项、客户与售卖均未关闭。\n'''
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:out.write(entry)
with (R/'docs/board_operations.md').open('a',encoding='utf8') as out:
    out.write(f'\n- **前端交接事实 {now}**：当前前两项尚未全验完；0.1.61最后实装证明，Word062候选已备，源80b34fcd/4d86908f。原有资料保留，当前仍在明确公开测试库，需该轮OTA收尾后切回。虚屏2由本侧scrcpy进程{virtual["pid"]}创建，当前66687 OTA流程依赖它；无在途任务并确认占用释放前不销毁/不移到主屏。前端不抢当前占用、不重复旧录音；后续按nextBatch承接。\n')
archive=P/'public-evidence-and-current-backlog.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for root in [samples,P/'public-recipient']:
        for file in root.rglob('*'):
            if file.is_file():z.write(file,file.relative_to(P).as_posix())
    for name in ['product_backlog.json','development_log.md']:z.write(R/'docs'/name,'docs/'+name)
write(P/'preservation-progress.json',{'at':now,'archive':archive.name,'sha256':sha(archive),'noOwnerAudioOrPrimaryScreenUploaded':True,'candidate062Sha256':apk['sha256'],'ordinary062WordAccepted':False})
qa_dir=S/'tools/qa/phone_closure059'
for pattern in ['*059*.py','*059*.cjs','*061*.py','*062*.py','ValidateDocuments059.cs','preserve_priority12_progress.py']:
    for file in W.glob(pattern):shutil.copy2(file,qa_dir/file.name)
shutil.copytree(W/'shareqa059',qa_dir/'shareqa059',dirs_exist_ok=True)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
target=S/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';shutil.copytree(P,target,dirs_exist_ok=True)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
    p=subprocess.run(['git',*args],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md');git('add','-f','--','docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12')
git('-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Preserve actual Android document delivery and Unicode-footer repairs with pending phone handoff')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}');assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
for file in [Path(apk['apk']),archive,P/'progress-result.json']:
    rel='docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/'+file.relative_to(P).as_posix()
    p=subprocess.run(['git','show',pin+':'+rel],cwd=S,capture_output=True);assert p.returncode==0 and hashlib.sha256(p.stdout).hexdigest()==sha(file)
write(P/'remote-progress-readback.json',{'commit':pin,'remoteReadback':True,'trackedCandidateAndArchiveVerified':True,'candidate062Installed':False,'fullPriority12Complete':False})
print(json.dumps({'commit':pin,'remoteReadback':True,'savedFormats':8,'sharedFormats':8,'word062Installed':False,'originalLibraryReturnPending':True,'fullPriority12Complete':False}),flush=True)
