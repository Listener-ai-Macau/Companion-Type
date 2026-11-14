from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');Q=O/'whole-delivery133156';W=Path(__file__).parent;V=W.parent/'outputs';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';B=R/'docs/handoffs/20261112-product-closure/windows133';P=R/'docs/handoffs/20261110-android-media-import/android157'
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m'];ENV={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0'}
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def read(p):return json.loads(Path(p).read_bytes())
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,env=ENV,text=True,encoding='utf8',timeout=180).strip()

def protect_sources():
 expected=[(E,'work/notebook133-frozen-20261114',read(B/'frozen-source.json')['sourceCommit']),(A,'work/notebook157-frontend-20261114',read(P/'source.json')['frontendSourceCommit'])]
 results=[]
 for root,branch,commit in expected:
  assert git(root,'rev-parse','HEAD')==commit and not git(root,'status','--porcelain');git(root,'push','origin',commit+':refs/heads/'+branch);actual=git(root,'ls-remote','origin','refs/heads/'+branch).split()[0];assert actual==commit;results.append(dict(branch=branch,commit=commit,remote=actual))
 save(Q/'source-protection.json',dict(at=now(),state='FINAL_UI_ONLY133157_SOURCES_REMOTE_VERIFIED',heads=results,modelsChanged=False));print('Final133/157 sources privately protected')

def assemble():
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(5,1024**3)
 sys.path.insert(0,str(R.parent/'ai-collaboration-workflow/scripts'));from development_storage import preflight
 win=read(B/'installation.json');wp=read(B/'windows-verification.json');ab=read(O/'android157-local/result.json');pe=read(P/'end-session.json');pi=read(P/'installation.json');pr=read(P/'reading-notice-after-restart.json');pb=read(P/'reading-notice-before-restart.json');reader=read(O/'note-readability-native133/result.json');native=read(reader['evidence']);images=Path(reader['evidence']).parent;source=read(Q/'source-protection.json')
 assert win['installedVersion']=='0.1.133' and win['dataManifestIdentical'] and sha('C:/Program Files/Companion Type/companion-type.exe')==win['installedExeSha256'];assert pe['actualVersion']=='0.1.157' and pe['ownedAppDisplayForwardJarClosed'] and pe['allPreviousLibrariesRetained']
 assert pr['originalAndReadableTranscriptSwitchChecked'] and pb['unifiedMoreMenuAndExportChecked'];assert not pr['modelsRun'] and pr['cloudCalls']==0;assert native['processRestart']['previousAppExited'];assert sha(wp['msi'])==wp['msiSha256'] and sha(ab['apk'])==ab['apkSha256']==pi['apkSha256']
 storage=preflight(Path('E:/CodexData/Companion/.build-cache'),reserve_gib=.25);save(Q/'storage-final.json',storage)
 stage=Q/'complete-notebook133157';stage.mkdir(exist_ok=False)
 files={
  '电脑/Companion-Windows-0.1.133.msi':Path(wp['msi']),'手机/Companion-Android-0.1.157.apk':Path(ab['apk']),
  '公开会议示例/完整纪要与原始转写.txt':images/'actual019f-ui-readable-preview.txt','公开会议示例/流畅阅读文字.txt':images/'actual-readable-transcript.txt',
  '界面/电脑实际-纪要浅色.png':images/'actual-public-minutes-light-viewport.png','界面/电脑实际-纪要深色.png':images/'actual-public-minutes-dark-viewport.png','界面/电脑实际-流畅阅读.png':images/'actual-readable-transcript-viewport.png',
  '界面/手机实际-纪要浅色.png':P/'reading-notice-before-restart-light.png','界面/手机实际-纪要深色.png':P/'reading-notice-before-restart-dark.png','界面/手机实际-文字切换.png':P/'readable-transcript-before-restart.png',
  '自验/电脑升级.json':B/'installation.json','自验/电脑连续使用.json':B/'runtime-result.json','自验/真实公开会议阅读.json':O/'note-readability-native133/result.json','自验/电脑排版.json':images/'actual-notebook-polish-layout.json',
  '自验/手机升级.json':P/'installation.json','自验/手机阅读及重开.json':P/'reading-notice-after-restart.json','自验/手机收尾.json':P/'end-session.json','自验/来源保护.json':Q/'source-protection.json','自验/固定缓存预算.json':Q/'storage-final.json',
 }
 for rel,path in files.items():
  assert path.is_file(),path;dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest);assert sha(path)==sha(dest)
 scope=dict(at=now(),state='NOTEBOOK133157_UI_INSTALLED_CONTINUOUS_NATIVE_REVIEW_AND_DATA_PROTECTION_PASSED_OWNER_TASTE_OPEN',windowsVersion='0.1.133',androidVersion='0.1.157',windowsSource=wp['sourceCommit'],androidSource=ab['sourceCommit'],windowsOldDataFilesIdentical=win['existingDataFiles'],phoneOldContentFilesIdentical=pe['preexistingFilesByteIdentical'],phoneAllPreviousLibrariesRetained=True,phoneOriginalLibraryAndAppearanceRestored=True,ownPhoneDisplayClosed=True,
  scope='Coherent frontend UI delivery. Windows uses prior real public30m saved results; phone uses declared public90s saved recording for the actual reading journey. No new model or physical capture qualification.',
  references=[dict(name='Granola official note layout and grouped reading',url='https://www.granola.ai/'),dict(name='Granola official source checking',url='https://docs.granola.ai/help-center/taking-notes/ai-enhanced-notes')],
  engineering=dict(actualWindowsSaveSourceSelectedExportDateAndTrueProcessReopen=True,actualWindowsPublicMinutesThemesTranscriptSwitchMutedReplayAndSourceDataUnchanged=True,actualPhoneMoreMenuOrganizationMindmapExportThemesTranscriptSwitchAndTrueProcessReopen=True,actualPhoneFinalCssLayerVerified=True,phoneAiConfigured=pr['phoneAiConfigured'],newModelsRunAfterOwnerAssignment=False,modelLogicChangedInDelivery=False,modelWorkOwnerAssignedOtherChat=True,noSpeakerBoardMicrophoneThisBatch=True),
  visualChanges=['Compact title/replay/export header and earlier reading content on desktop.','Shared paper, ink, type and spacing; dark theme no longer inherits older purple/blue palettes.','Phone idle replay occupies one row; inherited title padding removed; duplicate minutes/AI entry consolidated in More.','Existing overview supplies library snippet; literal raw-source search and complete originals remain available.','Outline closes after selection/Escape; retained keyboard focus and narrow-screen layouts.'],
  internalAndroid156RejectedAndFixed='Actual app exposed CSS import-order and specificity conflicts absent from a standalone reader preview. Final157 corrects the source order; original156 failure and artifacts retained.',
  remaining=['Owner对完整UI的清晰、精致和顺手感尚未最终签收。','模型/转写/纪要事实质量由Owner安排的另一个会话继续；本轮保留132/155模型逻辑。','手机AI配置与实体输入手感、硬件可靠性、整机售卖资格不由本UI批次关闭。'],frontendEngineeringAcceptancePassed=True,ownerAccepted=False,fullAcceptancePassed=False,saleQualified=False,privateOrMixedRoomAudioTextIncluded=False,rawAudioModelsKeysCredentialsIncluded=False,ownerPopupSent=False)
 save(stage/'自验/本轮范围.json',scope)
 explanation='''Companion 前端完整交付｜2026-11-14

电脑133、手机157已正常升级。这次把界面、交互入口、真实程序自验和安装包作为一个批次交付。

使用逻辑
从“我的录音”打开一条内容，主要区域固定为“纪要、文字、笔记”。需要核对时切到文字；回听和导出在录音上方。手机的问答、整理方式、思维导图和翻译集中在“更多”，不再重复堆在正文前面。

界面变化
参考Granola官方笔记布局，延续已许可的shadcn导航；标题、元信息和正文有固定层次，桌面阅读列保持合适宽度。统一纸色、墨色、字体与间距，减少互相竞争的强调色。手机压缩闲置播放器和标题空白，正文更早出现；深色模式也使用同一套笔记配色。没有导入对方闭源代码、字体或品牌素材。

已自行检查
实际电脑程序：连续保存、查来源、限定内容导出、日期保存、真正退出重开，以及同一公开30分钟会议的纪要/文字切换、深浅色、静音回听控件、原资料保护。实际手机：公开资料打开、更多菜单的整理入口与导图、导出入口、深浅色、原始/流畅读取、真正进程重开。最终手机已恢复原资料库和外观，关闭自有测试显示。原有电脑249份资料一致；手机旧内容保持一致，旧资料库都保留。

本轮没有改变识别或纪要模型。模型质量由你安排的另一个会话负责；包中的会议内容是已有实际结果，未为了展示界面人工重写。手机尚未配置AI服务，本轮未声称手机云端生成已通过。硬件手感和整机售卖资格仍沿原任务保留。

接下来完整体验
直接打开一条你熟悉的录音，按自己的习惯读纪要、核对原话，再带走需要的内容即可。工程路径已先检查；你主要判断整体是否一眼看懂、是否顺手，无需逐项承担工程验收。问题集中反馈到这一轮。
'''
 (stage/'交付说明.txt').write_text(explanation,encoding='utf8')
 inventory=[dict(file=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(stage.rglob('*'))if p.is_file()];save(stage/'文件校验.json',inventory)
 archive=V/'Companion-Notebook-133-157-20261114.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for p in sorted(stage.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(stage).as_posix())
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None
  for row in inventory:assert hashlib.sha256(z.read(row['file'])).hexdigest()==row['sha256']
 screens=V/'Companion-133-157-ui';screens.mkdir(exist_ok=False)
 for p in (stage/'界面').iterdir():shutil.copyfile(p,screens/p.name)
 shutil.copyfile(stage/'交付说明.txt',screens/'交付说明.txt')
 record=dict(**scope,archive=str(archive),archiveBytes=archive.stat().st_size,sha256=sha(archive),msiSha256=wp['msiSha256'],apkSha256=ab['apkSha256'],privateRemoteReadbackVerified=False,publishedPublicly=False,report=str(stage/'交付说明.txt'))
 for p in [H/'notebook133157-delivery.json',V/'Companion-Notebook-133-157-20261114-status.json']:save(p,record)
 print(json.dumps({k:record[k]for k in ['state','archive','sha256','frontendEngineeringAcceptancePassed']},ensure_ascii=False))

def protect_archive():
 p=H/'notebook133157-delivery.json';d=read(p);archive=Path(d['archive']);repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';assert sha(archive)==d['sha256'];assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate']
 release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];existing=next((a for a in release['assets']if a['name']==archive.name),None)
 if existing:assert existing['digest']=='sha256:'+d['sha256']
 else:subprocess.run(['gh','release','upload',tag,str(archive),'--repo',repo],check=True,timeout=180)
 back=Q/'private-readback';back.mkdir(exist_ok=True)
 if not(back/archive.name).exists():subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',str(back)],check=True,timeout=180)
 assert sha(back/archive.name)==d['sha256'];d.update(privateRemoteReadbackVerified=True,privateDraft=release['url'],privateReadbackSha256=d['sha256'],privateRemoteProtectedAt=now(),publishedPublicly=False)
 for dest in [p,archive.parent/'Companion-Notebook-133-157-20261114-status.json']:save(dest,d)
 print('Unified private archive fully downloaded and hash matched')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['sources','assemble','archive']);a=p.parse_args();{'sources':protect_sources,'assemble':assemble,'archive':protect_archive}[a.phase]()
