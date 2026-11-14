from pathlib import Path
from datetime import datetime
import copy,hashlib,json,os,re,shutil,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');W=Path(__file__).parent;OUT=W.parent/'outputs';BASE=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');Q=BASE/'visual-meeting20261114';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';BW=R/'docs/handoffs/20261112-product-closure/windows148';BP=R/'docs/handoffs/20261110-android-media-import/android164';O=BASE/'owner-guided148-20261114';D=Path('E:/CodexData/Companion/deliveries/20261114-ui148164');C=H/'ui148164'
read=lambda p:json.loads(p.read_bytes())
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def record(phase,review,delivery=None):
 p=R/'docs/product_backlog.json';raw=p.read_bytes();text=raw.decode('utf8');d=json.loads(text);a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);u=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112'];v=u['completeProductRework20261113']['noteReadabilityFollowup']['visualMeeting20261114']['uiCraftFollowup20261114'];at=now()
 u.update(updatedAt=at,candidateVersion='0.1.148',candidateAndroidVersion='0.1.164',installedAndEngineeringReviewed=True,softwareSelfAcceptancePassed=True,engineeringReviewReceipt=str(BW/'runtime-result.json'),installationReceipt=str(BW/'installation.json'),lastHandledOwnerRaw=v['ownerRaw'],currentDesignPreview=str(Q/'craft-r2/result.json'))
 u['preOwnerEngineeringAcceptance20261112'].update(review)
 a.update(updatedAt=at,currentInstalledWindows='0.1.148',currentInstalledAndroid='0.1.164',phoneHoldActive=False)
 v.update(updatedAt=at,state='UI148164_NORMAL_INSTALLED_AND_SCOPED_SELF_REVIEW_PASSED',selfAcceptance=str(C/'self-acceptance.json'),currentSources=str(Q/'source148164.json'),ownerAccepted=False,newAsrOrCloudRun=False)
 note='正常148/164 UI批次工程自验通过并实际安装：同一套文档语义标题、概览连续排版、字体与留白、简短助手，浅深和320/390/980/1440源阅读及资料交互验证；148真实半小时旧公开会议结果阅读/原文切换/限定导出和进程重开、完整标题可见通过，虚构文字本地HTTP回复到原生材料保存/导出/重开及长标题改名保存/取消/还原通过。没有新ASR/LLM/外放/板操作；144已有在线文字功能证据按未改实现保留。手机真实90秒旧公开会的全部原话和两项展开、主题/助手范围/模板与真正重开通过，无服务配置下未称实际手机生成/材料保存导出新通过；6548旧文件保留、6547内容一致仅索引新增公开库，原库外观恢复/显示63关/hold释放。电脑249旧资料一致。148冻结37537a9e沿正常143 cbb59d13原生输入/后台，164为2832bcdc与原AAR；其它在途指针/模型未纳入。保留146标题截断及探针失配证据，148是同批修正，不另发中间Owner验收。'
 if phase=='delivery':
  assert delivery and delivery['privateRemoteReadbackVerified'];u.update(state='UI148164_COHERENT_VISUAL_CRAFT_DELIVERED_OWNER_WHOLE_UX_OPEN',currentEngineeringReceipt=str(C/'self-acceptance.json'),currentSoftwareDelivery=str(H/'ui148164-delivery.json'),currentDelivery=str(H/'ui148164-delivery.json'),wholeSoftwareDeliveryReceipt=str(H/'ui148164-delivery.json'),privateRemoteReadbackVerified=True,ownerActuallyUsedThisCandidate=False,ownerExperienceAccepted=False)
  v.update(state='UI148164_COHERENT_VISUAL_CRAFT_PRIVATE_DELIVERY_COMPLETE_OWNER_UX_OPEN',deliveryReceipt=str(H/'ui148164-delivery.json'),archiveSha256=delivery['sha256'],privateRemoteReadbackVerified=True,next='承接本轮整段UI自然使用反馈；继续以清楚、精致、好用优先处理相关视觉/使用障碍。竞品功能、模型与硬件原待办均保留，不因UI交付关闭。')
  a.update(state='UI148164_VISUAL_CRAFT_ONE_KIT_DELIVERED_FURTHER_PRODUCT_WORK_OPEN',lastCompleteDeliveryReceipt=str(H/'ui148164-delivery.json'),lastCompletePackageSha256=delivery['sha256'],sourceCheckpoint={'windows':review['windowsSource'],'android':review['androidSource']},ownerRequestedHandoff=False,knownJobState='Normal148/164 installed, affected native reading/material/title/restart and exact private full readback passed; phone restored/hold released; unified original guide ready, no Owner popup started.',next=v['next'])
  note='148/164一份完整UI包已私有上传并全量下载SHA匹配；正常包、自验、实际浅深界面和源码冻结在同一交付内。原版统一整段体验按实际148准备就绪，沿原公开资料副本，未启动Owner窗口、没有逐功能签收。Owner高级感/整体顺手仍待真实反馈，未据工程自验关闭。原144/163基线、146截断失败与源码提交保留；只在本UI批次收敛后交一个148/164包，Phone164未重编。当前软件能力研究及项目/术语/翻译等原待办保留，模型、服务、实卡与正式售卖资格不虚关。'
 hits=[]
 for m in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
  value,n=json.JSONDecoder().raw_decode(text[m.end():])
  if value==old:hits.append((m,n))
 assert len(hits)==1;m,n=hits[0];updated=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:];assert p.read_bytes()==raw;p.write_bytes(updated.encode('utf8'))
 p=R/'docs/development_log.md';raw=p.read_bytes();text=raw.decode('utf8');marker='<!-- ui116-ui-craft20261114 -->';i=text.index(marker)+len(marker);assert p.read_bytes()==raw;p.write_bytes((text[:i]+'\r\n'+at+' '+note+'\r\n'+text[i:]).encode('utf8'))
 if phase=='delivery':
  p=R/'AGENTS.md';raw=p.read_bytes();text=raw.decode('utf8');pattern=r'(?m)^> [^\r\n]*UI116沿同批交付电脑144/手机163[^\r\n]*';assert len(re.findall(pattern,text))==1
  replacement='> '+at+' UI116沿同批交付电脑148/手机164：Owner选随身笔记并强调主要UI要高级一点；收敛文档标题/语义分区/概览连续排版/中文字体/列表留白与简短助手，浅深同层级。146原生标题截断失败保留，148自适应换行标题仍保留原单行值与保存/取消；实际长标题保存/取消/还原及退出重开通过。已有公开半小时原结果阅读/原话/限定导出/重开与手机公开90秒浅深/展开/助手/模板/重开已自验，未新ASR/LLM/录音/外放/板操作；手机无AI服务，不称本轮手机生成/材料保存导出已测。电脑249旧资料一致，手机6548保留/6547一致仅索引增公开库，原库外观恢复、自有63关/hold释放。148冻结37537a9e保留正常143原生基线，164为2832bcdc；其它在途指针/模型未覆盖。一整包收据docs/handoffs/20261113-ui-foundation/reader-clarity/ui148164-delivery.json，原版统一引导就绪未开。整体观感/顺手与竞品/服务/模型/硬件/售卖继续开放，从uiCraftFollowup20261114.next续作，01a3/019e禁读与01a7隔离继续。'
  assert p.read_bytes()==raw;p.write_bytes(re.sub(pattern,lambda _:replacement,text).encode('utf8'))
 print('ORIGINAL_UI116_UPDATED_'+phase.upper())
phase=sys.argv[1]
if phase=='record-review':
 wi=read(BW/'installation.json');public=read(BASE/'visual-meeting-native148/result.json');native=read(BASE/'software-value20261114/native148-r1/result.json');pn=Path(native['evidence']).parent;title=read(pn/'native-title-edit-save-cancel.json');phone=read(BP/'end-session.json');assert wi['installedVersion']=='0.1.148'and wi['dataManifestIdentical']and public['sourceStateAndAudioUnchanged'];assert title['originalTitleRestored']and phone['ownedAppDisplayForwardJarClosed']and phone['allPreviousLibrariesRetained'];assert read(BP/'assistant-after-restart.json')['minutesTranscriptAndPreviousNotesUnchanged']
 review=dict(at=now(),state='UI148164_COHERENT_VISUAL_CRAFT_ENGINEERING_SELF_ACCEPTANCE_PASSED',windowsVersion='0.1.148',androidVersion='0.1.164',windowsSource=wi['sourceCommit'],androidSource=read(BP/'build-result.json')['sourceCommit'],softwareSelfAcceptancePassed=True,scope='Shared notebook reading hierarchy and assistant presentation, complete source titles, ordinary title editing/save/cancel, material exact export, source reading and actual process reopen.',publicMeetingNative=str(BASE/'visual-meeting-native148/result.json'),nativeMaterial=str(BASE/'software-value20261114/native148-r1/result.json'),nativeCompleteTitle=str(pn/'native-title-edit-save-cancel.json'),phoneReading=str(BP/'reading-notice-after-restart.json'),phoneAssistant=str(BP/'assistant-after-restart.json'),sourceReading=str(Q/'craft-r2/result.json'),sourceMaterials=str(BASE/'software-value20261114/craft-r2/result.json'),sourceFullTitle=str(Q/'craft-title-r1/result.json'),oldWindowsFilesByteIdentical=249,oldPhoneFilesRetained=phone['preexistingFiles'],oldPhoneFilesByteIdentical=phone['preexistingFilesByteIdentical'],phoneOriginalLibraryAppearanceRestored=True,phoneHoldReleased=True,actualPhoneAiGenerationSaveExportTested=False,modelsOrCloudNewlyRun=False,modelQualityQualified=False,ownerPromptStarted=False,ownerAccepted=False,saleQualified=False)
 save(C/'self-acceptance.json',review);record('review',review)
elif phase=='entry':
 assert read(C/'self-acceptance.json')['softwareSelfAcceptancePassed'];prior=BASE/'owner-guided144-20261114';assert not(prior/'owner-progress.json').exists();assert not O.exists();O.mkdir()
 spec=read(prior/'review-spec.json');save(O/'previous-entry-spec.json',spec);wi=read(BW/'installation.json');spec.update(at=now(),version='0.1.148',sourceCommit=wi['sourceCommit'],verification=str(BW/'windows-verification.json'),engineeringReceipt=str(H/'ui148164-delivery.json'),scopeText='Companion · 看懂会议，留下能用的记录',ownerAccepted=False,intro='这一轮主要打磨了你选的“随身笔记”界面，电脑148、手机164已完成工程自验。\n\n点开始打开同一份公开会议副本。按自己顺手的方式读懂内容，需要时看原话、提问、留笔记或带走材料，看看整段使用是否清楚、精致、顺手。\n\n不用逐功能验收。哪里别扭就单独记一条，最后留整体感受；不会自动录音或播放声音。')
 spec['steps'][0]['message']='先用你顺手的方式了解这场公开会议。标题现在可完整换行阅读，概览、结论、待办和原话使用同一套排版；需要时切导图或按发言人查看。\n\n不用逐个入口检查，看不懂、难找或视觉别扭的地方，单独记一条即可。'
 save(O/'review-spec.json',spec);link=Path('C:/Users/Billy/Desktop/Companion整段体验.lnk');existing=link.is_file()
 if existing:shutil.copyfile(link,O/'previous-shortcut.lnk')
 import comtypes.client
 shell=comtypes.client.CreateObject('WScript.Shell',dynamic=True);shortcut=shell.CreateShortcut(str(link));script=S/'tools/qa/core_acceptance20261109/owner_saved_meeting.py';shortcut.TargetPath=str(Path(sys.executable).with_name('pythonw.exe'));shortcut.Arguments=subprocess.list2cmdline([str(script),'--spec',str(O/'review-spec.json'),'--run']);shortcut.WorkingDirectory=str(script.parent);shortcut.Description='新版随身笔记：围绕一场会议连续使用，问题逐条记录；不会自动录音播放。';shortcut.Save()
 ready=json.loads(subprocess.check_output([sys.executable,str(script),'--spec',str(O/'review-spec.json')],text=True,encoding='utf8'));save(O/'readiness.json',ready);assert ready['ready']and not ready['blockers'];save(O/'entry.json',dict(at=now(),shortcut=str(link),spec=str(O/'review-spec.json'),ready=True,previousShortcutRetained=existing,ownerPromptStarted=False,existingPublicProfileRetained=True));print('ONE_ORIGINAL_GUIDED148_ENTRY_READY_NOT_OPENED')
elif phase=='assemble':
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(5,768*1024**2);assert read(O/'entry.json')['ready']and read(O/'readiness.json')['ready'];review=read(C/'self-acceptance.json');wp=read(BW/'windows-verification.json');pb=read(BP/'build-result.json');public=Path(read(BASE/'visual-meeting-native148/result.json')['evidence']).parent;native=Path(read(BASE/'software-value20261114/native148-r1/result.json')['evidence']).parent
 stage=D/'complete-ui148164';assert not stage.exists();stage.mkdir();files={
 '程序/Companion-Windows-0.1.148.msi':Path(wp['msi']),'程序/Companion-Android-0.1.164.apk':Path(pb['apk']),
 '界面/电脑实际浅色纪要.png':public/'actual-clear-reader-light.png','界面/电脑实际深色纪要.png':public/'actual-clear-reader-dark.png','界面/电脑实际浅色展开.png':public/'actual-clear-expanded-light.png','界面/电脑实际深色展开.png':public/'actual-clear-expanded-dark.png',
 '界面/手机实际浅色纪要.png':BP/'actual-clear-reader-before-restart-light.png','界面/手机实际深色纪要.png':BP/'actual-clear-reader-before-restart-dark.png','界面/手机实际助手.png':BP/'native-assistant-before-restart-light.png',
 '自验/整套UI自验范围.json':C/'self-acceptance.json','自验/电脑正常包核对.json':BW/'windows-verification.json','自验/电脑实际升级.json':BW/'installation.json','自验/电脑连续使用.json':BW/'runtime-result.json','自验/电脑公开会议阅读.json':BASE/'visual-meeting-native148/result.json','自验/电脑完整标题.json':public/'actual-complete-title.json','自验/电脑长标题保存取消.json':native/'native-title-edit-save-cancel.json',
 '自验/手机正常包.json':BP/'build-result.json','自验/手机实际升级.json':BP/'installation.json','自验/手机浅深与原话.json':BP/'reading-notice-before-restart.json','自验/手机真正重开.json':BP/'reading-notice-after-restart.json','自验/手机助手与模板.json':BP/'assistant-after-restart.json','自验/手机原资料与结束.json':BP/'end-session.json',
 '自验/源组件宽窄与浅深.json':Q/'craft-r2/result.json','自验/源组件材料边界.json':BASE/'software-value20261114/craft-r2/result.json','自验/源组件长标题.json':Q/'craft-title-r1/result.json','源码/本批冻结来源.json':Q/'source148164.json',
 }
 for rel,p in files.items():
  assert p.is_file(),p;dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert sha(dest)==sha(p)
 guide='''Companion 随身笔记 UI 整体交付｜电脑148 / 手机164

正常包已经实际安装，本包保留对应安装文件、实际界面与明确范围的自验收据。桌面“Companion整段体验”已更新至本批，沿原引导窗口和同一份独立公开会议副本，没有自动弹窗。

这轮把高级感落实在同一套排版：中文字体、标题层级、阅读行宽与留白一致；会议概览改为连续笔记，概览/结论/待办等分区清楚；列表和控件更加克制；助手使用简短标题和一致的材料版式。浅色与深色、电脑和手机一起确认。真实原生检查发现146的单行标题截断，148已改为随内容和宽度换行，仍按原单行文字保存，原来的保存与取消保留；中间146不是本次最终整段交付。

在同一场会议里自然阅读，想核对时看原话，想整理时从“问会议”进入，确认保存后可带走指定材料。无需逐按钮签收；问题单独记，最后留整体感受。

本轮实际检查：电脑用已有的公开半小时中文会议结果核对阅读、浅深色、展开、导图/原文切换、导出和真正退出重开；另以明确虚构文字和仅本机HTTP回复检查改名/保存/取消/材料保存/指定导出/重开。手机用既有公开90秒会议检查浅深色、全部原话与其余两项展开、助手资料范围、模板预览、导图入口和真正重开。当前手机没有配置AI服务，实际手机在线生成与材料保存导出未在本轮重新验证；共享交互和既有后端证据分开保留。没有新ASR、LLM调用、外放、录音或板操作，旧结果不冒充新转写成绩。

电脑249旧资料字节一致；手机6548旧文件保留，6547内容一致，唯一变化为新增公开测试库的旧索引。原手机资料库、外观已恢复，自有显示63和占用已关闭。80GiB缓存预算、30GiB最低空闲、固定目标目录不变，没有自动清理。

UI视觉与使用感还需你的整体感受；模型质量、实卡/长期体验、账户/团队服务和正式售卖条件仍沿原待办。竞品能力研究及后续软件功能保留，当前优先UI精致与清楚。
''';(stage/'开始使用.txt').write_text(guide,encoding='utf-8-sig')
 manifest=dict(at=now(),state='ONE148164_UI_CRAFT_BUNDLE_NORMAL_INSTALLED_SELF_REVIEWED',versions={'windows':'0.1.148','android':'0.1.164'},windowsSource=wp['sourceCommit'],androidSource=pb['sourceCommit'],windowsInstallerSha256=wp['msiSha256'],androidApkSha256=pb['apkSha256'],ownerPromptStarted=False,ownerAccepted=False,newModelsOrCloudRun=False,actualPhoneAiGenerationSaveExportTested=False,saleQualified=False,phone164NormalPackageReusedAfterUnaffectedDesktopTitleFix=True,sourceFactsPreserved=True,source=str(Q/'source148164.json'),guide=str(O/'entry.json'),files=[dict(path=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(stage.rglob('*'))if p.is_file()and p.name not in['manifest.json','SHA256SUMS.txt']]);save(stage/'manifest.json',manifest)
 checks=[(p.relative_to(stage).as_posix(),sha(p))for p in sorted(stage.rglob('*'))if p.is_file()and p.name!='SHA256SUMS.txt'];(stage/'SHA256SUMS.txt').write_text(''.join(f'{h}  {n}\n'for n,h in checks),encoding='utf8');archive=OUT/'Companion-UI-148-164-20261114.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5)as z:
  for p in sorted(stage.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(stage).as_posix())
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None
  for n,h in checks:assert hashlib.sha256(z.read(n)).hexdigest()==h
 receipt=dict(at=now(),state='ONE148164_UI_BUNDLE_PRIVATE_READBACK_PENDING',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),allArchiveMemberChecksumsMatched=True,manifest=manifest,ownerEntryReady=True,ownerPromptStarted=False,privateRemoteReadbackVerified=False,saleQualified=False);save(H/'ui148164-delivery.json',receipt);save(OUT/'Companion-UI-148-164-status.json',receipt);print(json.dumps({k:v for k,v in receipt.items()if k!='manifest'},ensure_ascii=False))
elif phase=='publish':
 receipt=read(H/'ui148164-delivery.json');repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate'];release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];archive=Path(receipt['archive']);assert sha(archive)==receipt['sha256'];old=next((x for x in release['assets']if x['name']==archive.name),None)
 if old:assert old['digest']=='sha256:'+receipt['sha256']
 else:subprocess.run(['gh','release','upload',tag,str(archive),'--repo',repo],check=True)
 back=D/'private-readback';back.mkdir(exist_ok=True)
 if not(back/archive.name).exists():subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',str(back)],check=True)
 assert sha(back/archive.name)==receipt['sha256']and(back/archive.name).stat().st_size==archive.stat().st_size;receipt.update(at=now(),state='ONE148164_UI_BUNDLE_INSTALLED_AND_FULL_PRIVATE_READBACK_VERIFIED',privateRemoteReadbackVerified=True,privateDraft=release['url'],publishedPublicly=False);save(H/'ui148164-delivery.json',receipt);save(OUT/'Companion-UI-148-164-status.json',receipt);print(receipt['state'])
elif phase=='record-delivery':record('delivery',read(C/'self-acceptance.json'),read(H/'ui148164-delivery.json'))
elif phase=='protect':
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(5,1536*1024**2);receipt=read(H/'ui148164-delivery.json');assert receipt['privateRemoteReadbackVerified']and sha(Path(receipt['archive']))==receipt['sha256'];assert read(O/'readiness.json')['ready']and not(O/'owner-progress.json').exists();env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0'};G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
 def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,env=env,text=True,encoding='utf8',stderr=subprocess.STDOUT,timeout=240).strip()
 for name,p in{'source-at-freeze.json':Q/'source148164.json','source-reading-review.json':Q/'craft-r2/result.json','source-material-review.json':BASE/'software-value20261114/craft-r2/result.json','source-title-review.json':Q/'craft-title-r1/result.json','actual-public-reading.json':BASE/'visual-meeting-native148/result.json','actual-material-and-title.json':BASE/'software-value20261114/native148-r1/result.json','owner-entry.json':O/'entry.json','owner-readiness.json':O/'readiness.json','owned-picker-probe-fix.json':Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone164/restore-probe-fix.json')}.items():save(C/name,read(p))
 for name in['check_craft_title.cjs','software_material_title148_ui.cjs','run_craft_native148.py','review_ui_native148.py','review_ui_reading_phone164.cjs','review_ui_assistant_phone164.cjs','freeze_ui146164.py','freeze_craft148.py','finish_ui148164.py']:
  p=C/'qa-scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(W/name,p)
 files=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','docs/handoffs/20261113-ui-foundation/reader-clarity/ui148164-delivery.json']
 for folder in[C,R/'docs/handoffs/20261112-product-closure/windows148',R/'docs/handoffs/20261110-android-media-import/android164']:
  files += [p.relative_to(R).as_posix()for p in folder.rglob('*')if p.is_file()and(p.suffix=='.json'or folder==C)]
 for rel in sorted(set(files)):
  p=S/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/rel,p);assert sha(R/rel)==sha(p)
 paths=sorted(set(files))+['tools/qa/core_acceptance20261109/windows_real_public_ui.cjs'];git(S,'add','--',*paths);git(S,'commit','--only','-m','Deliver148164 coherent notebook UI with native title reading and restoration evidence','--',*paths);head=git(S,'rev-parse','HEAD');print('UI148164_OWN_PATHS_COMMITTED '+head,flush=True);refs=[]
 for root,commit,branch in[(S,head,'work/notebook-ui148164-complete-20261114'),(E,receipt['manifest']['windowsSource'],'work/notebook-ui148-frozen-20261114'),(A,receipt['manifest']['androidSource'],'work/notebook-ui164-phone-20261114')]:
  git(root,'push','origin',commit+':refs/heads/'+branch);assert git(root,'ls-remote','--heads','origin','refs/heads/'+branch).split()[0]==commit;refs.append(dict(branch=branch,commit=commit,remoteExact=True));print(branch+' VERIFIED',flush=True)
 proof=dict(at=now(),state='FINAL148164_THREE_REMOTE_EXACT_SOURCES_AND_ONE_WHOLE_PRIVATE_READBACK_VERIFIED',sources=refs,archiveSha256=receipt['sha256'],wholeArchivePrivateReadbackVerified=True,canonicalSnapshotHashes={rel:sha(S/rel)for rel in['AGENTS.md','docs/product_backlog.json','docs/development_log.md']},otherWorkerUncommittedChangesIncluded=False,ownerEntryReady=True,ownerPromptStarted=False,ownerAccepted=False,modelOrSaleQualified=False);save(C/'source-protection-final.json',proof);save(OUT/'Companion-UI-148-164-source-protection.json',proof);print(proof['state'])
else:raise ValueError(phase)
