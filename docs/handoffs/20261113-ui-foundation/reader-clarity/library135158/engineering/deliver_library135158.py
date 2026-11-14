from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');Q=O/'library-closure20261114';W=Path(__file__).parent;V=W.parent/'outputs';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';B=R/'docs/handoffs/20261112-product-closure/windows135';P=R/'docs/handoffs/20261110-android-media-import/android158'
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m'];ENV={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0'}
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def read(p):return json.loads(Path(p).read_bytes())
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,env=ENV,text=True,encoding='utf8',timeout=180).strip()

def protect_sources():
 expected=[(E,'work/notebook135-frozen-20261114',read(B/'frozen-source.json')['sourceCommit']),(A,'work/notebook158-frontend-20261114',read(P/'source.json')['frontendSourceCommit'])]
 results=[]
 for root,branch,commit in expected:
  assert git(root,'rev-parse','HEAD')==commit and not git(root,'status','--porcelain');git(root,'push','origin',commit+':refs/heads/'+branch);actual=git(root,'ls-remote','origin','refs/heads/'+branch).split()[0];assert actual==commit;results.append(dict(branch=branch,commit=commit,remote=actual))
 save(Q/'source-protection.json',dict(at=now(),state='FINAL_UI_ONLY135158_SOURCES_REMOTE_VERIFIED',heads=results,modelsChanged=False));print('Final135/158 sources privately protected')

def assemble():
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(5,1024**3)
 sys.path.insert(0,str(R.parent/'ai-collaboration-workflow/scripts'));from development_storage import preflight
 win=read(B/'installation.json');wp=read(B/'windows-verification.json');ab=read(O/'android158-local/result.json');pe=read(P/'end-session.json');pi=read(P/'installation.json');pr=read(P/'reading-notice-after-restart.json');pb=read(P/'reading-notice-before-restart.json');reader=read(O/'note-readability-native135/result.json');native=read(reader['evidence']);images=Path(reader['evidence']).parent;source=read(Q/'source-protection.json')
 assert win['installedVersion']=='0.1.135' and win['dataManifestIdentical'] and sha('C:/Program Files/Companion Type/companion-type.exe')==win['installedExeSha256'];assert pe['actualVersion']=='0.1.158' and pe['ownedAppDisplayForwardJarClosed'] and pe['allPreviousLibrariesRetained']
 assert read(P/'library-after-restart.json')['organizationPersistedAfterTrueProcessRestart'];assert read(P/'library-before-restart.json')['actualPreparedExportPreview'];assert pr['originalAndReadableTranscriptSwitchChecked'] and pb['unifiedMoreMenuAndExportChecked'];assert not pr['modelsRun'] and pr['cloudCalls']==0;assert native['processRestart']['previousAppExited'];assert sha(wp['msi'])==wp['msiSha256'] and sha(ab['apk'])==ab['apkSha256']==pi['apkSha256']
 storage=preflight(Path('E:/CodexData/Companion/.build-cache'),reserve_gib=.25);save(Q/'storage-final.json',storage)
 stage=Q/'complete-notebook135158';stage.mkdir(exist_ok=False)
 files={
  '电脑/Companion-Windows-0.1.135.msi':Path(wp['msi']),'手机/Companion-Android-0.1.158.apk':Path(ab['apk']),
  '公开会议示例/完整纪要与原始转写.txt':images/'actual019f-ui-readable-preview.txt','公开会议示例/流畅阅读文字.txt':images/'actual-readable-transcript.txt',
  '界面/电脑实际-纪要浅色.png':images/'actual-public-minutes-light-viewport.png','界面/电脑实际-纪要深色.png':images/'actual-public-minutes-dark-viewport.png','界面/电脑实际-流畅阅读.png':images/'actual-readable-transcript-viewport.png',
  '界面/手机实际-纪要浅色.png':P/'reading-notice-before-restart-light.png','界面/手机实际-纪要深色.png':P/'reading-notice-before-restart-dark.png','界面/手机实际-文字切换.png':P/'readable-transcript-before-restart.png',
  '自验/电脑升级.json':B/'installation.json','自验/电脑连续使用.json':B/'runtime-result.json','自验/真实公开会议阅读.json':O/'note-readability-native135/result.json','自验/电脑排版.json':images/'actual-notebook-polish-layout.json',
  '自验/手机升级.json':P/'installation.json','自验/手机阅读及重开.json':P/'reading-notice-after-restart.json','自验/手机收尾.json':P/'end-session.json','自验/来源保护.json':Q/'source-protection.json','自验/固定缓存预算.json':Q/'storage-final.json',
 }
 files.update({
  '界面/电脑实际-先选择再整理.png':images/'actual-library-choose-first.png','界面/电脑实际-筛选范围.png':images/'actual-library-current-scope.png',
  '界面/手机实际-选择录音.png':P/'library-one-selected.png','界面/手机实际-筛选范围.png':P/'library-visible-scope.png','界面/手机实际-整理后导出预览.png':P/'library-to-real-export-preview.png',
  '自验/手机真实分类与导出.json':P/'library-before-restart.json','自验/手机分类真正重开.json':P/'library-after-restart.json','自验/源界面完整使用.json':Q/'after-r1/result.json',
 })
 for rel,path in files.items():
  assert path.is_file(),path;dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest);assert sha(path)==sha(dest)
 scope=dict(at=now(),state='NOTEBOOK135158_COMPLETE_FRONTEND_BACKGROUND_CLOSURE_INSTALLED_SELF_REVIEWED_OWNER_TASTE_OPEN',windowsVersion='0.1.135',androidVersion='0.1.158',windowsSource=wp['sourceCommit'],androidSource=ab['sourceCommit'],windowsOldDataFilesIdentical=win['existingDataFiles'],phoneOldContentFilesIdentical=pe['preexistingFilesByteIdentical'],phoneAllPreviousLibrariesRetained=True,phoneOriginalLibraryAndAppearanceRestored=True,ownPhoneDisplayClosed=True,
  scope='Coherent frontend UI delivery. Windows uses prior real public30m saved results; phone uses declared public90s saved recording for the actual reading journey. No new model or physical capture qualification.',
  references=[dict(name='shadcn official Tasks filter and selection toolbar',url='https://ui.shadcn.com/examples/tasks'),dict(name='Granola official note layout and grouped reading',url='https://www.granola.ai/'),dict(name='Granola official source checking',url='https://docs.granola.ai/help-center/taking-notes/ai-enhanced-notes')],
  engineering=dict(actualWindowsSaveSourceSelectedExportDateAndTrueProcessReopen=True,actualWindowsPublicMinutesThemesTranscriptSwitchMutedReplayAndSourceDataUnchanged=True,actualPhoneMoreMenuOrganizationMindmapExportThemesTranscriptSwitchAndTrueProcessReopen=True,actualPhoneFinalCssLayerVerified=True,phoneAiConfigured=pr['phoneAiConfigured'],newModelsRunAfterOwnerAssignment=False,modelLogicChangedInDelivery=False,modelWorkOwnerAssignedOtherChat=True,noSpeakerBoardMicrophoneThisBatch=True),
  visualChanges=['Visible removable folder/tag/date scope; clearing filters preserves the explicit search.','Selection count and targets stay visible; empty management directs users back to select recordings.','Phone selection shows one compact organization row; dirty input and cancellation remain guarded.','Compact title/replay/export header and earlier reading content on desktop.','Shared paper, ink, type and spacing; dark theme no longer inherits older purple/blue palettes.','Phone idle replay occupies one row; inherited title padding removed; duplicate minutes/AI entry consolidated in More.','Existing overview supplies library snippet; literal raw-source search and complete originals remain available.','Outline closes after selection/Escape; retained keyboard focus and narrow-screen layouts.'],
  previousComplete133157Baseline='Installed133/157 retained until this full UI batch. No intermediate native candidate was delivered.',
  actualPublicLibraryScopeAndSelectionChecked=True,phoneOnlySelectedPublicRecordingOrganizedAndReopened=True,phoneActualPreparedExportPreview=True,sourceSelectionPanelHeightBefore=445.1875,sourceSelectionPanelHeightAfter=46,
  remaining=['Owner对完整UI的清晰、精致和顺手感尚未最终签收。','模型/转写/纪要事实质量由Owner安排的另一个会话继续；本轮保留132/155模型逻辑。','手机AI配置与实体输入手感、硬件可靠性、整机售卖资格不由本UI批次关闭。'],frontendEngineeringAcceptancePassed=True,ownerAccepted=False,fullAcceptancePassed=False,saleQualified=False,privateOrMixedRoomAudioTextIncluded=False,rawAudioModelsKeysCredentialsIncluded=False,ownerPopupSent=False)
 save(stage/'自验/本轮范围.json',scope)
 explanation='''Companion 前端整体交付｜2026-11-14

电脑135、手机158均已正常安装。本轮在你休息期间完成录音查找、选择、整理与带走的后台收口，包含上一版已交付的阅读界面。

完整使用顺序
在“我的录音”找到要用的内容；需要缩小范围时，文件夹、标签、日期等条件会留在列表上，可直接取消。要统一分类或导出，先选择录音；选了几条、正在处理谁始终清楚。打开内容后，主要区域仍固定为纪要、文字、笔记，回听与导出在上方。

这一轮实际改善
• 筛选关闭后仍看得见当前条件，清除分类筛选保留已输入的搜索。
• 电脑不再在零选择时先显示整块管理表单；可直接返回列表勾选，再整理所选。
• 取消选择会清掉原选择，未应用的分类修改继续保留防丢约束。
• 手机选中录音后只出现一条整理入口；列表仍可继续选择，分类工具在需要时展开，保护与删除另行收拢。
• 延续Granola笔记层级和已许可shadcn导航，本轮补用shadcn Tasks的筛选/选择层级；两端纸色、字体、深浅色、文字切换和阅读界面保持一致。

已经自行完成
电脑实际正常程序的筛选、选择、草稿保护、阅读、来源、所选导出、保存和真正退出重开。手机实际公开资料中，选择一条、应用文件夹和标签、筛选找回、准备真实导出预览、真正进程重开均通过；其它公开记录分类不变，录音文字与纪要不变。双端原有资料保持，手机已恢复原库和原外观，关闭自有测试显示。

本轮没有录音、外放、使用板卡或调用模型服务。识别和纪要质量由你安排的另一个会话继续；这份包保留原有模型逻辑。实体输入手感、硬件可靠性和正式售卖资格仍沿原任务保留。

醒来后直接从一条熟悉的录音开始，按自己的习惯查找、阅读、核对原话并带走内容即可。工程检查已先完成，整体是否清楚、精致、顺手仍由你的自然使用判断；问题集中反馈这一轮。
'''
 (stage/'交付说明.txt').write_text(explanation,encoding='utf8')
 inventory=[dict(file=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(stage.rglob('*'))if p.is_file()];save(stage/'文件校验.json',inventory)
 archive=V/'Companion-Notebook-135-158-20261114.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for p in sorted(stage.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(stage).as_posix())
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None
  for row in inventory:assert hashlib.sha256(z.read(row['file'])).hexdigest()==row['sha256']
 screens=V/'Companion-135-158-ui';screens.mkdir(exist_ok=False)
 for p in (stage/'界面').iterdir():shutil.copyfile(p,screens/p.name)
 shutil.copyfile(stage/'交付说明.txt',screens/'交付说明.txt')
 record=dict(**scope,archive=str(archive),archiveBytes=archive.stat().st_size,sha256=sha(archive),msiSha256=wp['msiSha256'],apkSha256=ab['apkSha256'],privateRemoteReadbackVerified=False,publishedPublicly=False,report=str(stage/'交付说明.txt'))
 for p in [H/'notebook135158-delivery.json',V/'Companion-Notebook-135-158-20261114-status.json']:save(p,record)
 print(json.dumps({k:record[k]for k in ['state','archive','sha256','frontendEngineeringAcceptancePassed']},ensure_ascii=False))

def protect_archive():
 p=H/'notebook135158-delivery.json';d=read(p);archive=Path(d['archive']);repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';assert sha(archive)==d['sha256'];assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate']
 release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];existing=next((a for a in release['assets']if a['name']==archive.name),None)
 if existing:assert existing['digest']=='sha256:'+d['sha256']
 else:subprocess.run(['gh','release','upload',tag,str(archive),'--repo',repo],check=True,timeout=180)
 back=Q/'private-readback';back.mkdir(exist_ok=True)
 if not(back/archive.name).exists():subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',str(back)],check=True,timeout=180)
 assert sha(back/archive.name)==d['sha256'];d.update(privateRemoteReadbackVerified=True,privateDraft=release['url'],privateReadbackSha256=d['sha256'],privateRemoteProtectedAt=now(),publishedPublicly=False)
 for dest in [p,archive.parent/'Companion-Notebook-135-158-20261114-status.json']:save(dest,d)
 print('Unified private archive fully downloaded and hash matched')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['sources','assemble','archive']);a=p.parse_args();{'sources':protect_sources,'assemble':assemble,'archive':protect_archive}[a.phase]()
