from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent;OUT=W.parent/'outputs';BASE=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');Q=BASE/'software-value20261114';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';D=Path('E:/CodexData/Companion/deliveries/20261114-software144163');BW=R/'docs/handoffs/20261112-product-closure/windows144';BP=R/'docs/handoffs/20261110-android-media-import/android163';O=BASE/'owner-guided144-20261114'
read=lambda p:json.loads(p.read_bytes())
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
phase=sys.argv[1]
if phase=='prepare':
 wi=read(BW/'installation.json');assert wi['installedVersion']=='0.1.144'and wi['dataManifestIdentical'];assert sha(Path('C:/Program Files/Companion Type/companion-type.exe'))==wi['installedExeSha256']
 previous=BASE/'owner-guided141-20261114';assert not(previous/'owner-progress.json').exists();assert not(O/'entry.json').exists()and not(O/'owner-progress.json').exists();O.mkdir(exist_ok=True)
 spec=read(previous/'review-spec.json');save(O/'previous141-spec.json',spec)
 spec.update(at=now(),version='0.1.144',sourceCommit=wi['sourceCommit'],verification=str(BW/'windows-verification.json'),engineeringReceipt=str(H/'software144163-delivery.json'),scopeText='Companion · 从一场会议到可用的材料',disableCloudForReview=False,ownerAccepted=False,intro='电脑144、手机163已经完成本批工程自验。\n\n点“开始”打开同一份公开中文会议的独立副本：先看懂会议，再从“问会议”提出自己关心的问题；有需要就把结果修改、保存成材料，最后带走。已配置的AI服务只在你主动开始整理后使用，不会自动录音或播放。\n\n这是连续使用的一次体验，不用逐功能签收。遇到问题单独记一条，最后留整体感受。若这个独立副本没有继承服务配置，页面会显示“设置AI服务”；可先继续看已有会议，不要求你配置服务来替工程验收。')
 spec['steps']=[dict(title='读懂这场会议',message='先用你顺手的方式了解这场公开会议讲了什么。纪要、思维导图和按发言人入口都围绕这一场会议；哪里看不懂或找不到，就单独记一条问题。'),dict(title='把关心的事变成材料',message='从“问会议”说出你真正想弄清楚的问题，也可以选择跟进草稿、整理周报或客户简报。已有可用服务时，主动点开始才会整理；先阅读结果，需要时修改，再保存为独立材料。原纪要和转写保留。若当前独立环境没有服务，记下这个使用障碍并继续看已有结果即可，不需要你配置或做技术检查。'),dict(title='带走并回来继续',message='对确认保存的材料，直接用“导出这份材料”带走所选正文。退出后可重开继续读。你只需判断：能否快速看懂、找到关心的内容并得到可用的结果；每条问题单独记录，最后留整体感受。')]
 save(O/'review-spec.json',spec)
 link=Path('C:/Users/Billy/Desktop/Companion整段体验.lnk');missing=not link.is_file()
 if not missing:shutil.copyfile(link,O/'previous141-shortcut.lnk')
 import comtypes.client
 shell=comtypes.client.CreateObject('WScript.Shell',dynamic=True);shortcut=shell.CreateShortcut(str(link));script=S/'tools/qa/core_acceptance20261109/owner_saved_meeting.py';shortcut.TargetPath=str(Path(sys.executable).with_name('pythonw.exe'));shortcut.Arguments=subprocess.list2cmdline([str(script),'--spec',str(O/'review-spec.json'),'--run']);shortcut.WorkingDirectory=str(script.parent);shortcut.Description='一场会议连续阅读、提问、保存材料和带走结果；每条问题单独记录。';shortcut.Save()
 ready=json.loads(subprocess.check_output([sys.executable,str(script),'--spec',str(O/'review-spec.json')],text=True,encoding='utf8'));assert ready['ready']and not ready['blockers'];save(O/'readiness.json',ready);save(O/'entry.json',dict(at=now(),shortcut=str(link),reviewSpec=str(O/'review-spec.json'),ready=True,priorShortcutMissingAtPreparation=missing,ownerPromptStarted=False,existingPublicProfileRetained=True,onlineGenerationOnlyOnExplicitUserAction=True))
 print('ONE_ORIGINAL_GUIDED_ENTRY144_READY_NOT_OPENED')
elif phase=='assemble':
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(5,768*1024**2)
 wp=read(BW/'windows-verification.json');wi=read(BW/'installation.json');pb=read(BP/'build-result.json');pe=read(BP/'end-session.json');pi=read(BP/'installation.json');real=read(Q/'native144-real-service-r1/result.json');local=read(Q/'native144-r2/result.json')
 assert wi['dataManifestIdentical']and wi['sourceCommit']==wp['sourceCommit'];assert pi['apkSha256']==pb['apkSha256']and pe['allPreviousLibrariesRetained']and pe['ownedAppDisplayForwardJarClosed'];assert real['configuredActualTextServiceUsed']and real['actualNativeUiStorageExportAndReopen'];assert read(BP/'assistant-after-restart.json')['minutesTranscriptAndPreviousNotesUnchanged']
 actual=read(Path(real['evidence']));native=Path(real['evidence']).parent
 assert actual['ui']['syntheticServiceFixture']is False
 # Preserve the original generic framework default and explicitly correct its
 # scope metadata for this real text-only LLM continuation, without a rerun.
 if not actual.get('functionalServiceScope'):
  save(Q/'native144-real-service-r1/framework-original-result.json',actual)
  actual.update(frameworkInitialModelsRun=actual['modelsRun'],modelsRun=True,speechAsrRun=False,functionalServiceScope='One explicit fictional meeting text sent by the real native Ask control to the already configured service; no private or acoustic audio, no quality qualification.')
  save(Path(real['evidence']),actual)
 source=read(Q/'source144162.json');source['android']=read(BP/'source.json');source.update(finalVersions={'windows':'0.1.144','android':'0.1.163'},phone162TemplateRouteFailureRetained=True);save(Q/'source144163.json',source)
 assert read(O/'entry.json')['ready']and read(O/'readiness.json')['ready']
 stage=D/'complete-material144163'
 if stage.exists():assert(H/'competitive-software20261114/retained-package-preparation-failure.json').is_file()
 stage.mkdir(exist_ok=True)
 files={
 '程序/Companion-Windows-0.1.144.msi':Path(wp['msi']),'程序/Companion-Android-0.1.163.apk':Path(pb['apk']),
 '竞品研究/官方资料与30类能力.json':H/'competitive-software20261114/research.json','竞品研究/已装基线源码核对.json':H/'competitive-software20261114/source-audit.json',
 '自验/双端源码交互与浅深宽窄.json':Q/'r3/result.json','自验/冻结源码.json':Q/'source144163.json',
 '自验/电脑正常包核验.json':BW/'windows-verification.json','自验/电脑安装与原资料.json':BW/'installation.json','自验/电脑连续使用.json':BW/'runtime-result.json','自验/电脑本地回复边界.json':Q/'native144-r2/result.json','自验/电脑实际在线服务功能.json':Q/'native144-real-service-r1/result.json','自验/电脑实际在线保存导出重开.json':Path(real['evidence']),
 '自验/手机正常包.json':BP/'build-result.json','自验/手机安装.json':BP/'installation.json','自验/手机实际入口与浅深色.json':BP/'assistant-before-restart.json','自验/手机真正重开.json':BP/'assistant-after-restart.json','自验/手机原资料与会话结束.json':BP/'end-session.json',
 '界面/电脑实际在线材料浅色.png':native/'native-material-light.png','界面/电脑实际在线材料深色.png':native/'native-material-dark.png','界面/电脑退出重开材料.png':native/'process-reopen/native-material-reopened.png',
 '界面/手机实际助手浅色.png':BP/'native-assistant-before-restart-light.png','界面/手机实际助手深色.png':BP/'native-assistant-before-restart-dark.png','界面/手机实际模板预览.png':BP/'native-template-before-restart-light.png',
 '示例/明确虚构文字-实际在线问答后导出的材料.txt':Path(actual['publicFixtureExportCache']),
 }
 for rel,p in files.items():
  assert p.is_file(),p;dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert sha(p)==sha(dest)
 guide='''Companion 软件集中交付｜电脑144 / 手机163

本批已安装。沿“随身笔记”风格，把会议阅读与问答、材料编辑保存、指定导出连起来。桌面“Companion整段体验”保留原引导窗口，准备就绪但没有自动弹窗或启动录音。

默认先看纪要，需要时查看思维导图、按发言人或原话。“问会议”直接可见；使用者主动选会议或补充文档，最多12项。可用现有AI服务整理跟进草稿、周报或客户简报；结果先阅读，需要时再编辑。确认保存后成为独立材料，可直接导出这一份，原纪要与转写保留。保存过的提问可以复用，复用不会自动调用服务。

模板预览展示实际整理要求，不伪造会议示例结果。手机从问答进入整理方式的跳转问题在真实使用中发现并修正，失败和手机162候选证据保留在原时间线。

本轮对照Plaud、Notta、Otter、Granola和飞书妙记官方公开文档，核对30类代表性核心能力，研究中明确区分已有基础、实际缺口和服务依赖；不是登录各家账户逐项试用，也不声称竞品全部功能已经做齐。

已完成的工程自验：双端真实源码的浅深色与窄宽阅读、失败保留、资料范围变化、材料身份与草稿保护；正常电脑应用通过真实原生HTTP/保存/导出/进程重开，另用现有在线服务对明确虚构的短会议文字跑通一次相同流程。示例目录就是实际导出的文件，属于虚构文字软件功能检查，不是私人会议、新录音或准确率成绩。手机真实应用核验入口、默认资料范围、模板预览、导图浏览与导图导出区分、浅深色和真正重开；手机当前未配置AI服务，因此本轮没有把手机真实生成/材料保存导出称为通过，其共享组件交互与现有原生后端证据分别保留。

电脑249旧资料字节一致；手机6493旧文件全部保留、6492内容一致，唯一变化是新增公开测试资料库的旧索引。原手机资料库与外观恢复，自有显示会话关闭、占用释放。没有新录音、ASR、板卡操作或扬声器播放，没有新模型选择/调优。原始半小时公开会议已验证的转写/纪要结果和阅读基线继续保留，未称本轮重新完成了半小时模型验收。

待继续完善：人名术语词表、双端翻译一致、可靠跨会议项目回顾与统一待办、独立常用流程库；受控分享链接、账户云同步、团队权限和外部应用连接需完整后台服务。可靠分人、语义章节与原始转写质量仍沿模型专项；实卡、长期使用和正式售卖资格不因本批UI交付而关闭。
'''
 (stage/'开始使用.txt').write_text(guide,encoding='utf-8-sig')
 manifest=dict(at=now(),state='ONE144163_SOFTWARE_VALUE_BUNDLE_SELF_ACCEPTED_AND_INSTALLED',versions={'windows':'0.1.144','android':'0.1.163'},windowsSource=wp['sourceCommit'],androidSource=pb['sourceCommit'],windowsInstallerSha256=wp['msiSha256'],androidApkSha256=pb['apkSha256'],onePurpose='会议提问→阅读/修改→独立材料保存→指定导出→重开继续',actualConfiguredTextServiceFunctionalCheck=True,textSourceExplicitlyFictional=True,newSpeechAsrRun=False,actualPhoneAiMaterialGenerationSaveExportTested=False,phoneUnconfiguredServiceStateChecked=True,modelQualityQualified=False,allCompetitorCapabilitiesImplemented=False,saleQualified=False,ownerWholeExperienceAccepted=False,ownerPromptStarted=False,guideEntry=str(O/'entry.json'),research=str(H/'competitive-software20261114/research.json'),cacheBudgetsUnchanged=True,automaticCacheDeletion=False,files=[dict(path=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(stage.rglob('*'))if p.is_file()and p.name not in ['manifest.json','SHA256SUMS.txt']])
 save(stage/'manifest.json',manifest);checks=[(p.relative_to(stage).as_posix(),sha(p))for p in sorted(stage.rglob('*'))if p.is_file()and p.name!='SHA256SUMS.txt'];(stage/'SHA256SUMS.txt').write_text(''.join(f'{h}  {n}\n'for n,h in checks),encoding='utf8')
 archive=OUT/'Companion-Software-144-163-20261114.zip'
 if archive.exists():assert sha(archive)==read(H/'competitive-software20261114/retained-checksum-preparation-failure.json')['archiveOverwriteAllowedSha256']
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5)as z:
  for p in sorted(stage.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(stage).as_posix())
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None
  for n,h in checks:assert hashlib.sha256(z.read(n)).hexdigest()==h
 receipt=dict(at=now(),state='ONE144163_SOFTWARE_VALUE_BUNDLE_PRIVATE_READBACK_PENDING',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),allArchiveMemberChecksumsMatched=True,manifest=manifest,privateRemoteReadbackVerified=False,ownerEntryReady=True,ownerPromptStarted=False,saleQualified=False)
 save(H/'software144163-delivery.json',receipt);save(OUT/'Companion-Software-144-163-status.json',receipt);print(json.dumps({k:v for k,v in receipt.items()if k!='manifest'},ensure_ascii=False))
elif phase=='publish':
 receipt=read(H/'software144163-delivery.json');repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate'];release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];archive=Path(receipt['archive']);assert sha(archive)==receipt['sha256'];assert not any(x['name']==archive.name for x in release['assets'])
 subprocess.run(['gh','release','upload',tag,str(archive),'--repo',repo],check=True);back=D/'remote-readback';back.mkdir(exist_ok=False);subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',str(back)],check=True);assert sha(back/archive.name)==receipt['sha256']and(back/archive.name).stat().st_size==archive.stat().st_size
 receipt.update(at=now(),state='ONE144163_SOFTWARE_VALUE_BUNDLE_INSTALLED_AND_FULL_PRIVATE_READBACK_VERIFIED',privateRemoteReadbackVerified=True,privateDraft=release['url'],publishedPublicly=False);save(H/'software144163-delivery.json',receipt);save(OUT/'Companion-Software-144-163-status.json',receipt);print(receipt['state'])
else:raise ValueError(phase)
