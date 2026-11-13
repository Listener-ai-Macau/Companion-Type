from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');W=Path(__file__).parent;V=W.parent/'outputs';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';P=R/'docs/handoffs/20261110-android-media-import/android155';B=R/'docs/handoffs/20261112-product-closure/windows132'
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,1024**3)
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/scripts');from development_storage import preflight
def read(p):return json.loads(Path(p).read_bytes())
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
win=read(B/'installation.json');wp=read(B/'windows-verification.json');ab=read(O/'android155-local/result.json');pe=read(P/'end-session.json');pi=read(P/'installation.json');pr=read(P/'reading-notice-after-restart.json');reader=read(O/'note-readability-native132-r2/result.json');native=read(reader['evidence']);images=Path(reader['evidence']).parent
assert win['installedVersion']=='0.1.132' and win['dataManifestIdentical'] and sha('C:/Program Files/Companion Type/companion-type.exe')==win['installedExeSha256']
assert pe['actualVersion']=='0.1.155' and pe['ownedAppDisplayForwardJarClosed'] and pe['allPreviousLibrariesRetained'] and pe['onlyOldChangeLibraryIndex']
assert pr['originalAndReadableTranscriptSwitchChecked'] and not pr['modelsRun'] and pr['cloudCalls']==0
assert native['ui']['actualReadableAndCompleteOriginalTranscriptSwitchChecked'] and native['processRestart']['previousAppExited']
assert sha(wp['msi'])==wp['msiSha256'] and sha(ab['apk'])==ab['apkSha256']==pi['apkSha256']
storage=preflight(Path('E:/CodexData/Companion/.build-cache'),reserve_gib=.25);save(O/'storage-final132155.json',storage)
stage=O/'complete-notes132155';stage.mkdir(exist_ok=False)
files={
 '电脑/Companion-Windows-0.1.132.msi':Path(wp['msi']),'手机/Companion-Android-0.1.155.apk':Path(ab['apk']),
 '公开会议示例/完整纪要与原始转写.txt':images/'actual019f-ui-readable-preview.txt','公开会议示例/流畅阅读文字.txt':images/'actual-readable-transcript.txt',
 '界面/电脑实际-纪要浅色.png':images/'actual-public-minutes-light-viewport.png','界面/电脑实际-纪要深色.png':images/'actual-public-minutes-dark-viewport.png','界面/电脑实际-流畅阅读.png':images/'actual-readable-transcript-viewport.png',
 '界面/手机实际-纪要浅色.png':P/'reading-notice-before-restart-light.png','界面/手机实际-纪要深色.png':P/'reading-notice-before-restart-dark.png','界面/手机实际-转写切换.png':P/'readable-transcript-before-restart.png',
 '自验/电脑升级.json':B/'installation.json','自验/手机升级.json':P/'installation.json','自验/手机收尾.json':P/'end-session.json','自验/电脑真实会议阅读.json':O/'note-readability-native132-r2/result.json','自验/手机阅读切换及重开.json':P/'reading-notice-after-restart.json','自验/缓存预算.json':O/'storage-final132155.json',
}
for rel,source in files.items():
 assert source.is_file(),source;target=stage/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==sha(source)
scope=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='NOTES132155_INSTALLED_NATIVE_READING_AND_TRANSCRIPT_SWITCH_CHECKED_OWNER_JUDGMENT_OPEN',windowsVersion='0.1.132',androidVersion='0.1.155',windowsSource=wp['sourceCommit'],androidSource=ab['sourceCommit'],windowsOldDataFilesIdentical=win['existingDataFiles'],phoneOldContentFilesIdentical=pe['preexistingFilesByteIdentical'],phoneOriginalLibraryAndAppearanceRestored=True,ownPhoneDisplayClosed=True,
 references=[dict(name='Notta official overview/chapters/actions',url='https://www.notta.ai/en/features/ai-summary'),dict(name='Granola official grouped notes/templates',url='https://docs.granola.ai/help-center/taking-notes/customise-notes-with-templates'),dict(name='Granola official source checking',url='https://docs.granola.ai/help-center/taking-notes/ai-enhanced-notes')],
 adaptation='Official information hierarchy adapted to Chinese notes; licensed shadcn navigation retained. No proprietary assets/code imported. Source topic prefixes only; no invented note titles or meeting facts.',
 engineering=dict(actual132NativeNotesThemesReversibleTranscriptSwitchMutedReplaySelectedExportAndProcessReopen=True,actual155PhonePublicNotesThemesTranscriptSwitchAndProcessReopen=True,cleanPublicMinutesRegeneratedByActual129=True,transcriptionEngineChanged=False,originalTranscriptAndExportRetained=True,phoneNewModelOrCloudRun=False,phoneAiConfigured=pr['phoneAiConfigured'],noNewSpeakerOrBoardCapture=True),
 remaining=['Owner对清晰/好看/顺手的实际判断尚未签收。','流畅阅读属于可逆显示处理，未解决实卡复杂人声的错字或通用纪要事实可靠性；简短应答、原话与条件保留。','手机AI服务未配置，未声称本轮手机云纪要已生成。','整机、输入手感和正式售卖资格仍开放。'],fullAcceptancePassed=False,saleQualified=False,ownerAccepted=False,privateOrMixedRoomAudioTextIncluded=False,rawAudioModelsKeysCredentialsIncluded=False,ownerPopupSent=False)
save(stage/'自验/本轮范围.json',scope)
readme='''Companion 纪要阅读与转写阅读统一交付｜2026-11-13

电脑132、手机155均已正常升级。本轮围绕同一条反馈集中修复，没有新录音或新外放。

采用的成熟做法
Notta：短概览、主题章节、行动事项；Granola：清楚的标题/正文层次与按需核对原话。保留现有已许可的shadcn导航，按中文笔记适配，不宣称直接复制其闭源代码或品牌界面。来源链接见“自验/本轮范围.json”。

实际改变
• 概览作为一个集中阅读区域；主题标题和正文直接可读，避免把每段长句塞进折叠行。结论/行动/问题与原文依据分清，原文核对仍可打开。
• 双端中文字体、标题、选中态和正文间距统一，手机旧正文大边框已移除。
• “流畅阅读/原始转写”可直接切换，长段文字分段。长句中的停顿及重复起头可略去；简短回应、引号内原话、数字和条件保留。完整识别、人工编辑与导出不被覆盖。
• 同一公开30分钟源音用已安装129实际重新生成五条概览；132原生重验阅读、切换、静音回听控件、所选导出和真正重开。手机155实际公开资料阅读、切换、主题和重开通过，另有同30分钟真实结果的实际源码组件检查；不能把组件预览当手机本轮模型生成。

数据和边界
电脑249份原资料保持一致；手机6052份旧内容一致，仅旧资料库索引加入公开测试库，所有旧库仍在；原库与原外观已恢复，独立测试显示关闭。
公开示例包含实际原生导出的完整纪要/原始转写，以及从132实际“流畅阅读”界面读取的文字。没有预先手写漂亮会议内容来替代真实模型结果。

仍未完成
原始识别错字、实卡复杂/重叠人声及纪要事实可靠性仍需继续处理。清理语气词不等于提升识别准确率。手机AI尚未配置，本轮没有手机云端生成通过结论。Owner整体观感、输入手感与正式售卖尚未签收。
原会议内容不会自动重写。已有纪要可以继续查看，重新整理仍须由使用者发起并沿现有服务/隐私设置；工程没有重新处理旧私人录音或混入现场私语的01a7。
'''
(stage/'本轮交付说明.txt').write_text(readme,encoding='utf8')
inventory=[dict(file=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(stage.rglob('*'))if p.is_file()];save(stage/'文件校验.json',inventory)
archive=V/'Companion-Notes-132-155-20261113.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for p in sorted(stage.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(stage).as_posix())
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None
 for row in inventory:assert hashlib.sha256(z.read(row['file'])).hexdigest()==row['sha256']
screens=V/'Companion-132-155-ui';screens.mkdir(exist_ok=False)
for p in (stage/'界面').iterdir():shutil.copyfile(p,screens/p.name)
record=dict(**scope,archive=str(archive),archiveBytes=archive.stat().st_size,sha256=sha(archive),msiSha256=wp['msiSha256'],apkSha256=ab['apkSha256'],privateRemoteReadbackVerified=False,publishedPublicly=False,report=str(stage/'本轮交付说明.txt'))
for p in [H/'notes132155-delivery.json',V/'Companion-Notes-132-155-20261113-status.json']:save(p,record)
print(json.dumps({k:record[k]for k in ['state','archive','sha256','fullAcceptancePassed']},ensure_ascii=False))
