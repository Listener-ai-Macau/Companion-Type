from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');P=O/'public-source-full30-127';W=Path(__file__).parent;V=W.parent/'outputs'
H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';D=H/'resumed129154';D.mkdir(exist_ok=False);V.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,1024**3)
def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
win=read(R/'docs/handoffs/20261112-product-closure/windows129/installation.json');wp=read(R/'docs/handoffs/20261112-product-closure/windows129/windows-verification.json');wb=read(O/'windows129-local/result.json');ab=read(O/'android154-local/result.json');phone=R/'docs/handoffs/20261110-android-media-import/android154';pi=read(phone/'installation.json');pe=read(phone/'end-session.json');pr=read(phone/'reading-notice-after-restart.json');reader=read(P/'reader129-result.json');native=read(reader['evidence']);evaluation=read(P/'evaluation.json');minutes=read(P/'minutes-result.json')
assert win['installedVersion']=='0.1.129' and win['dataManifestIdentical'];assert sha(Path('C:/Program Files/Companion Type/companion-type.exe'))==wp['embeddedExeSha256']==win['installedExeSha256']
assert pe['actualVersion']=='0.1.154' and pe['onlyOldChangeLibraryIndex'] and pe['allPreviousLibrariesRetained'] and pe['ownedAppDisplayForwardJarClosed'];assert pi['apkSha256']==ab['apkSha256'] and pr['modelsRun']is False and pr['cloudCalls']==0
assert native['ui']['actualFallbackTopicListAndOrdinaryScrollChecked'] and native['processRestart']['previousAppExited'] and native['ui']['actualPublicImportedAudioResultsRead'] and not native['ui']['actualPhysicalAudioResultsRead']
assert minutes['publicSourceOnly'] and minutes['cloudTextOnly'] and not minutes['cloudAudioUpload']
msi=Path(wp['msi']);apk=Path(ab['apk']);assert sha(msi)==wp['msiSha256'] and sha(apk)==ab['apkSha256']
preview=read(O/'mobile-topic154-component-preview/result.json');assert preview['version']=='0.1.154' and not preview['connectedPhoneTested']
for name,digest in preview['testedSourceFiles'].items():assert sha(R/'companion-core-android20261109'/name)==digest
stage=O/'complete-software129154';stage.mkdir(exist_ok=False)
files={
 '电脑/Companion-Windows-0.1.129.msi':msi,'手机/Companion-Android-0.1.154.apk':apk,
 '公开示例/公开中文会议30分钟-完整软件结果.txt':P/'公开中文会议30分钟-软件完整结果.txt',
 '自验/公开源音转写评估.json':P/'evaluation.json','自验/电脑安装.json':R/'docs/handoffs/20261112-product-closure/windows129/installation.json',
 '自验/电脑真实会议阅读.json':P/'reader129-result.json','自验/手机安装.json':phone/'installation.json','自验/手机收尾.json':phone/'end-session.json','自验/手机真实阅读.json':phone/'reading-notice-after-restart.json',
 '自验/固定缓存预算.json':O/'storage-final129154.json',
 '界面/电脑-浅色.png':Path(reader['evidence']).parent/'actual-public-minutes-light-viewport.png',
 '界面/电脑-深色.png':Path(reader['evidence']).parent/'actual-public-minutes-dark-viewport.png',
 '界面/手机实机-浅色.png':phone/'reading-notice-before-restart-light.png',
 '界面/手机实机-深色.png':phone/'reading-notice-before-restart-dark.png',
 '界面/手机半小时会议组件预览-浅色.png':O/'mobile-topic154-component-preview/phone-component-light.png'
}
for rel,source in files.items():
 assert source.is_file(),source;target=stage/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==sha(source)
scope=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='SOFTWARE129154_INSTALLED_AND_CHECKED_FULL_PRODUCT_ACCEPTANCE_OPEN',windowsVersion='0.1.129',androidVersion='0.1.154',
 windowsSource=wp['sourceCommit'],androidSource=ab['sourceCommit'],androidBackendSource=ab['backendSourceCommit'],
 desktopOldDataFilesIdentical=win['existingDataFiles'],phoneOldContentFilesIdentical=pe['preexistingFilesByteIdentical'],phonePreviousLibrariesRetained=True,phoneOriginalLibraryAndAppearanceRestored=True,ownDisplay51Closed=True,
 softwareCase=dict(source='AISHELL4 published30m file; ordinary open-with/store-new-recording/localASR, configured desktop text-only minutes, export and actual process reopen',actualAsrAndMinutesEngine='0.1.127',current129AsrMinutesImportAndSdkExactTo127=True,transcriptCharacters=7211,referenceCharacters=6579,characterErrorRate=336/6579,referenceGivenToModels=False,minutesChunksComplete=True,actual129NativeReadingThemesTopicDetailsMutedReplaySelectedExportAndReopenPassed=True,actual154PhonePublicReadingThemesAndProcessReopenPassed=True,actual154EightTopicComponentPreviewPassed=True,componentPreviewIsNotNativePhoneOrNewPhoneCloudTest=True),
 acousticCase=dict(durationMs=1808330,captureFirmware=66830,captureWindows='0.1.126',normalStopAndDurableReceiveCompleted=True,ownConnectionReleased=True,nonSourceRoomSpeechDetected=True,retainedLocalOnly=True,excludedFromCloudAndPublicArtifacts=True,cleanPhysicalAsrAccuracyQualified=False),
 remaining=['实卡复杂/重叠人声的转写可靠性仍待解决，混音对照不能充当干净识别基准。','手机AI服务当前未配置，本轮未声称手机云端纪要实际生成通过。','Owner整体体验、输入手感及正式售卖验收仍未签收。'],
 phoneAiConfigured=pr['phoneAiConfigured'],generalAsrQualityQualified=False,fullAcceptancePassed=False,saleQualified=False,ownerExperienceAccepted=False,ownerAcceptancePopupSent=False,privateOrMixedRoomAudioTextIncluded=False,rawAudioModelWeightsKeysOrCredentialsIncluded=False)
save(stage/'自验/本轮范围与未完成.json',scope)
component={**preview,'state':'ANDROID154_ACTUAL_READING_COMPONENT_LAYOUT_VERIFIED_BROWSER_ONLY','legacyDriverStateName':preview['state']};save(stage/'自验/手机半小时组件范围.json',component)
text='''Companion 本轮统一软件交付｜2026-11-13

电脑：0.1.129；手机：0.1.154。两端均已正常升级并完成本轮阅读自验。
电脑249份原有资料保持一致；手机5997份原有内容字节一致，唯一旧变化是资料库索引增加公开测试库，原有资料库全部保留。手机已返回原资料库与原外观，自有测试显示51已关闭。

这轮完成的事情
• 恢复电脑扬声器外放并实际播完30分钟中文真人会议；本轮录音正常停止、收齐并释放自有连接。
• 沿用成熟的中性 Mail/侧栏布局，主路径集中在“录音 → 纪要／文字／笔记 → 导出”。重复生成说明收进详情，真实异常与未完成提醒保留。
• 简短概览不可用时，保留全部原有议题入口，逐条展开细节；不再让首屏被几段早期长摘要占满。完整摘要、原话依据、数字、否定与导出内容保留。
• 公开源音已用正常应用完成“打开音频 → 存为新录音 → 本地转写 → 电脑现有AI生成纪要 → 导出 → 真正重开”；当前电脑129重验了阅读、双主题、回听控件、所选导出与重开。
• 手机154实际公开资料阅读、双主题和进程重开通过；另用同一真实30分钟会议结果检查了小屏八议题布局、详情展开与完整摘要折叠，并修掉长标题撑宽页面的问题。

仍未完成的事情
• 实卡在复杂、重叠人声环境中的转写可靠性。这次采录混入其它现场人声，整段保留本地，没有送云端，也不在本包中。不能用它来宣称干净识别准确率。
• 手机AI服务当前未配置，本轮没有把已有公开资料的展示说成手机云端生成纪要已经通过。
• Owner整体体验与正式售卖验收未签收；本包是一次统一的软件候选交付，不能据此宣布完整产品可售。

如何看这一个完整场景
打开应用，选一场会议，先看整场议题入口，展开一条细节，再切到文字核对，最后从固定导出入口取走所选内容。后续人工体验沿这一条自然使用流程集中进行，不逐功能派发验收。
“公开示例”里是实际软件导出的完整文字结果；“界面”里已分别标明电脑实际原生界面、手机实际界面和手机组件预览。

证据边界
干净公开源音本次字错率约5.11%，只是这一个软件样例，不代表实卡或通用模型质量达标。参考文字从未提供给模型。
实际源音转写与纪要发生在127；129只变更阅读并继承已保存128兼容输入候选，ASR、纪要、音频导入和SDK源码逐项相同，因此保留原始结果，只重验受影响阅读路径。手机154完全复用已验证150的同一原生AAR，没有虚称本轮又跑了手机模型。
本包不含原始录音、环境混音、模型权重、私人资料、服务密钥或签名私钥。
'''
(stage/'本轮交付说明.txt').write_text(text,encoding='utf8')
inventory=[dict(file=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(stage.rglob('*'))if p.is_file()];assert all(not row['file'].lower().endswith(('.wav','.opus','.onnx','.pem','.key','.pfx'))for row in inventory);save(stage/'文件校验.json',inventory)
archive=V/'Companion-Software-129-154-20261113.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for p in sorted(stage.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(stage).as_posix())
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None
 for row in inventory:assert hashlib.sha256(z.read(row['file'])).hexdigest()==row['sha256']
screens=V/'Companion-129-154-ui';screens.mkdir(exist_ok=False)
for name in ['电脑-浅色.png','电脑-深色.png','手机实机-浅色.png','手机实机-深色.png','手机半小时会议组件预览-浅色.png']:shutil.copyfile(stage/'界面'/name,screens/name)
record=dict(**scope,archive=str(archive),archiveBytes=archive.stat().st_size,sha256=sha(archive),msiSha256=sha(msi),apkSha256=sha(apk),files=len(inventory)+1,privateRemoteReadbackVerified=False,publishedPublicly=False,invitationSent=False,report=str(stage/'本轮交付说明.txt'))
save(H/'complete-product129154-software.json',record);save(V/'Companion-Software-129-154-20261113-status.json',record);save(D/'result.json',record)
print(json.dumps({key:record[key]for key in ['state','archive','archiveBytes','sha256','windowsVersion','androidVersion','fullAcceptancePassed']},ensure_ascii=False))
