from pathlib import Path
from datetime import datetime
import json,os,hashlib,subprocess,shutil,zipfile,copy,re,sys
W=Path(__file__).resolve().parents[1];R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';B=R/'docs/handoffs/20261112-product-closure/windows120';A=R/'docs/handoffs/20261110-android-media-import/android146';E=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/reader-clarity20261113');O=W/'outputs'
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def read(p):return json.loads(Path(p).read_bytes())
def write(p,d):Path(p).write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def update(record):
 p=R/'docs/product_backlog.json';raw=p.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112'];batch=u['readerClarityRework20261113'];at=now()
 batch.update(state=record['state'],delivery=str(H/'software-delivery.json'),engineeringReceipt=str(H/'engineering-self-acceptance.json'),windowsInstalled='0.1.120',androidInstalled='0.1.146',actualDualClientReviewCompleted=True,privateCompletePackageReadback=record['privateRemoteReadbackVerified'],ownerExperienceAccepted=False)
 u.update(state=record['state'],currentDelivery=str(H/'software-delivery.json'),noMoreOwnerPromptUntilSubstantiveRepair=False,lastHandledOwnerFeedbackId='UI116-DESIGN-FOUNDATION',lastHandledOwnerRaw=batch['ownerRaw']);u['readerRefinementsAfterActualPublicInput20261113'].update(state='INCLUDED_IN120146_READER_CLARITY_DELIVERY',sourceChangesDelivered=True,delivery=str(H/'software-delivery.json'))
 next_action='120/146已同批安装，原资料保护/实际连续保存与限定导出/真正重开、同019f已保存真实结果查看回听已核，一个完整双端软件包'+('已私有完整下载回读匹配'if record['privateRemoteReadbackVerified']else'待私有完整下载回读')+'。Owner只短做人感自然使用，整体好看/清楚/顺手仍未签收；新问题回同UI116-DESIGN-FOUNDATION集中承接。旧真人短会内容质量、实卡/鼠标/模型/硬件/售卖沿原各自最新任务，不由UI检查关闭；不为UI重复录音或模型。'
 a.update(updatedAt=at,state=record['state'],currentInstalledWindows='0.1.120',currentInstalledAndroid='0.1.146',plannedVersionsBuilt=True,next=next_action,knownJobState='120/146 build/native UI/phone/restart jobs finished. Exact current119 predecessor matched before120 upgrade; original119 Owner experience already ended10:55:38 with link closed and TURN_RELEASED. This UI batch has no live device, microphone, ASR/cloud, phone display or build worker.');c.update(updatedAt=at,currentPoint=next_action)
 m['currentBatch'].update(at=at,state=record['state'],done='120/146应用导航/列表/阅读整体重排并安装；Windows实际连续保存/来源/限定导出/日历日期/进程重开及同019f真实结果查看回听，手机实际改名/文字保存/导出入口/主题/进程重开通过；原资料保护已核。',remaining='Owner整体审美、清晰与自然好用仍未签收；原其它资格沿各自任务。',reference=str(H/'software-delivery.json'),next=next_action);m['nextBatch'].update(at=at,status=record['state'],next=next_action)
 def splice(key,before,after):
  nonlocal text
  hits=[]
  for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
   value,n=json.JSONDecoder().raw_decode(text[match.end():])
   if value==before:hits.append((match,n))
  assert len(hits)==1,key;match,n=hits[0];text=text[:match.end()]+json.dumps(after,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
 splice('activeNonmodelCompletion20261110',old,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);tmp=p.with_suffix('.reader-clarity.tmp');tmp.write_bytes(text.encode('utf8'));assert p.read_bytes()==raw;tmp.replace(p)
 return next_action
phase=sys.argv[1]
if phase=='prepare':
 assert not(H/'software-delivery.json').exists();win=read(B/'windows-verification.json');installed=read(B/'installation.json');runtime=read(B/'runtime-result.json');phone=read(A/'build-result.json');end=read(A/'end-session.json');real=read(E/'real-public019f-native/review.json')
 assert installed['sourceCommit']==runtime['appSourceCommit']==win['sourceCommit']==real['sourceCommit']and installed['dataManifestIdentical']and runtime['actualNativeProcessRestart']['previousAppExited']
 assert end['ownedAppDisplayForwardJarClosed']and end['onlyOldChangeLibraryIndex']and read(A/'library-review-result.json')['actualProcessRestartPassed']and read(A/'installation.json')['apkSha256']==phone['apkSha256']
 assert real['sourceLibraryAndAllFourOriginalAudioFilesUnchanged']and real['newAsrMinutesOrBoardRequested']is False
 msi=O/'Companion-Windows-0.1.120.msi';apk=O/'Companion-Android-0.1.146.apk';assert not msi.exists()and not apk.exists();shutil.copyfile(win['msi'],msi);shutil.copyfile(phone['apk'],apk);assert sha(msi)==win['msiSha256']and sha(apk)==phone['apkSha256']
 acceptance=dict(at=now(),state='READER120146_INSTALLED_CONTINUOUS_ENGINEERING_SELF_REVIEW_COMPLETE_OWNER_UX_OPEN',windows=dict(version='0.1.120',source=win['sourceCommit'],actualNativeRuntime=str(B/'runtime-result.json'),realPublicSavedResults=str(E/'real-public019f-native/review.json'),previousInstalledVersion=installed['previousInstalledVersion'],originalFilesUnchanged=installed['existingDataFiles'],retainsCurrent119AndTiltOnly87e6CommittedSource=True,newPhysicalPointerQualification=False),android=dict(version='0.1.146',source=phone['sourceCommit'],actualPhone=str(A/'library-review-result.json'),closed=str(A/'end-session.json'),originalFilesIdentical=end['preexistingFilesByteIdentical'],onlyPriorIndexChangedForOneNewPublicLibrary=True,allPriorLibrariesRetained=True),sourceChecks=dict(continuous=str(E/'windows-source-r1/result.json'),emptyMultipleRealPublicDeviceLayouts=str(E/'layout-review-r1/result.json'),mobile=str(E/'mobile-source-r1/result.json'),affectedComponentContracts=str(E/'customer-contracts-r3.log')),failuresRetained=['First stylesheet rewrite patch was rejected before file mutation; replaced the one existing foundation stylesheet from an owned source file.','Visual review caught inherited library-grid columns squeezing rows; corrected before native freeze.','Existing component contracts lacked matchMedia and two tests replaced the shared window mock; fixed test setup, then adapted the renamed editor control. Full affected contracts passed.','Phone146 first strict44px assertion rejected real43.9983px device-pixel quantization; native computed min-width44px and all text inside. Added0.5CSSpx tolerance; exact same APK passed, no rebuild.','Windows initial upgrade preflight correctly rejected old118 predecessor: embedded119 had independently installed. Read exact119 receipt, verified source ancestry and ended Owner controller, preserved initial folder and upgraded119→120 normally.'],limitations=['Owner aesthetics/clarity/usability acceptance remains open.','Native OS dialog/ordinary recipient operations reuse exact unchanged backend/command evidence; moved route and actual private native export reviewed.','This batch does not rerun recording, ASR/cloud, physical pointer, long-duration or whole-device/sales qualification. Prior public meeting content-quality issues remain.'],ownerAppearanceAccepted=False,saleQualified=False)
 write(H/'engineering-self-acceptance.json',acceptance)
 manifest=dict(at=now(),scope='Companion双端阅读界面集中更新',windows=dict(version='0.1.120',sourceCommit=win['sourceCommit'],installer=msi.name,sha256=sha(msi),installed=True),android=dict(version='0.1.146',sourceCommit=phone['sourceCommit'],installer=apk.name,sha256=sha(apk),installed=True),engineeringSelfReviewComplete=True,ownerExperienceAccepted=False,saleQualified=False)
 guide='''Companion · 录音与阅读界面120/146

电脑：左侧切换录音、收藏和录音卡，中间找录音，右侧阅读当前内容。
手机：从录音列表打开一条，先回听，再切换“纪要、文字、笔记”。
导出固定在当前录音顶部。文档与提问在笔记中；手机思维导图和翻译在“更多”。
管理、剪辑和其它工具放在阅读内容之后，按需要展开。未保存的修改和原始资料继续保留。
录音卡连接后沿用原后台接收；需要时再查看接收详情。

本包包含电脑MSI与Android APK，两端已安装并完成工程连续检查。
外观、清晰程度和自然使用是否顺手仍待你的实际感受；复杂功能和长时间检查由工程承担。
'''
 archive=O/'Companion-Reader-120-146-20261113.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:z.write(msi,msi.name);z.write(apk,apk.name);z.writestr('开始使用.txt',guide);z.writestr('交付身份.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 with zipfile.ZipFile(archive)as z:assert z.testzip()is None;assert hashlib.sha256(z.read(msi.name)).hexdigest()==sha(msi)and hashlib.sha256(z.read(apk.name)).hexdigest()==sha(apk)
 record=dict(at=now(),state='READER120146_INSTALLED_ENGINEERING_CHECKED_ONE_KIT_PRIVATE_READBACK_PENDING',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),windows=manifest['windows'],android=manifest['android'],engineeringReceipt=str(H/'engineering-self-acceptance.json'),privateRemoteReadbackVerified=False,ownerAppearanceAccepted=False,ownerExperienceAccepted=False,saleQualified=False)
 write(H/'software-delivery.json',record);write(O/'Companion-Reader-120-146-20261113.json',record);update(record);print(json.dumps(record,ensure_ascii=False),flush=True)
elif phase=='publish':
 record=read(H/'software-delivery.json');repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate'];release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];dest=Path('E:/CodexData/Companion/deliveries/readback-reader120146');dest.mkdir(exist_ok=False)
 for file,digest in [(Path(record['archive']),record['sha256']),(O/'Companion-Windows-0.1.120.msi',record['windows']['sha256'])]:
  assert sha(file)==digest;existing=next((x for x in release['assets']if x['name']==file.name),None)
  if existing:assert existing['digest']=='sha256:'+digest
  else:subprocess.run(['gh','release','upload',tag,str(file),'--repo',repo],check=True)
  subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',file.name,'--dir',str(dest)],check=True);assert sha(dest/file.name)==digest;print(file.name+' complete private readback matched',flush=True)
 record.update(at=now(),state='READER120146_INSTALLED_ENGINEERING_CHECKED_ONE_KIT_PRIVATE_READBACK_VERIFIED_OWNER_UX_OPEN',privateRemoteReadbackVerified=True,privateDraft=release['url'],individualWindowsMsiReadbackVerified=True);write(H/'software-delivery.json',record);write(O/'Companion-Reader-120-146-20261113.json',record);update(record)
elif phase=='protect':
 record=read(H/'software-delivery.json');assert record['privateRemoteReadbackVerified'];next_action=update(record);at=now();native=Path(read(B/'runtime-result.json')['nativeUiEvidence']).parent;real=Path(read(E/'real-public019f-native/review.json')['nativeEvidence']).parent
 for folder,source,names in [('windows',native,['result.json','product-result-light.png','product-result-dark.png','self-acceptance-device-entry.png','product-date-only-calendar.png']),('real-public019f',real,['result.json','actual019f-minutes.png','actual019f-export.png','actual019f-playback.json']),('phone146',A,['build-result.json','installation.json','library-review-result.json','process-restart.json','end-session.json','original-returned.json','actual-tab-geometry.json','actual-layout-inspection.json','review-failure.json','review-initial-subpixel-assertion.cjs','library-light.png','detail-light.png','detail-dark.png'])]:
  dest=H/folder;dest.mkdir(exist_ok=False)
  for name in names:shutil.copyfile(source/name,dest/name)
 for name in ['result.json','multiple-light-1360.png','multiple-dark-1360.png','actual-public019f-light-1360.png','actual-public019f-dark-1360.png','empty-light-1360.png','multiple-light-390.png','device-connected.png','device-pairing.png','device-storage.png']:shutil.copyfile(E/'layout-review-r1'/name,H/('source-'+name))
 for name in ['customer-contracts.log','customer-contracts-r2.log','customer-contracts-r3.log']:shutil.copyfile(E/name,H/name)
 for name in ['start_reader_clarity20261113.py','restructure_reader_clarity20261113.py','restructure_mobile_clarity20261113.py','prepare_clarity_source_review20261113.py','freeze_reader_clarity20261113.py','prepare_reader_delivery_checks20261113.py','review_reader_phone146.cjs','run_reader_phone_step20261113.py','return_reader_phone146.cjs','inspect_phone146_layout.cjs','review_real019f_native120.py','install_reader120.py','deliver_reader_clarity20261113.py']:
  dest=H/'engineering-source'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(W/'work'/name,dest)
 shutil.copyfile(E/'layout-review-r1/multiple-light-1360.png',O/'Companion-Reader-Desktop-120.png');shutil.copyfile(A/'detail-light.png',O/'Companion-Reader-Phone-146.png')
 p=H/'source-checkpoints.json';d=read(p);d['initialPreviousInstalledWindowsAssumption']=d['previousInstalledWindows'];d.update(previousInstalledWindows='0.1.119',previousInstalledCorrectedBy=str(B/'upgrade-predecessor.json'),installedWindows='0.1.120',installedAndroid='0.1.146',currentDelivery=str(H/'software-delivery.json'));write(p,d)
 agent=R/'AGENTS.md';raw=agent.read_bytes();s=raw.decode('utf8');lines=s.splitlines();i=next(i for i,x in enumerate(lines)if x.startswith('- 当前实际已装Windows'));lines[i]='- 当前实际已装Windows0.1.120 / Android0.1.146。Owner再次明确118/145仍混乱，沿UI116-DESIGN-FOUNDATION改为固定应用侧栏＋录音列表＋阅读正文；录音标题旁固定导出、回听后直接进入纪要/文字/笔记，统计卡片/二层展开和重复完成提示退出主阅读，管理剪辑放在内容后。120正常同源包实际连续保存/限定导出/日期/真正重开及同019f真实结果查看回听通过；从实际119升级、247份原资料哈希一致，保留2cbb/87e6已提交指针来源，未重验实体指针。146实际改名/文字保存/导出入口/主题/进程重开通过；5470份旧内容字节一致，唯一旧索引因新增公开库变化，所有旧库/原外观/原库已恢复，自有显示器已关。一个双端软件包已私有完整回读匹配，收据docs/handoffs/20261113-ui-foundation/reader-clarity/software-delivery.json。Owner整体好看/清晰/顺手仍未认可，后续只短做人感使用；实板沿嵌软最新830交付，旧短会内容质量、指针/模型/硬件/售卖不由本UI批次关闭。';s='\r\n'.join(lines).rstrip('\r\n')+'\r\n';tmp=agent.with_suffix('.reader.tmp');tmp.write_bytes(s.encode('utf8'));assert agent.read_bytes()==raw;tmp.replace(agent)
 p=R/'docs/handoffs/20261113-ui-foundation/reference-selection.json';d=read(p);d.update(currentState=record['state'],currentApplicationDelivery=str(H/'software-delivery.json'),next=next_action);write(p,d)
 log=R/'docs/development_log.md';raw=log.read_bytes();marker='<!-- reader120146-clarity-delivery20261113 -->';assert marker.encode()not in raw
 entry=f'''## {at}｜120／146重组阅读层级，一次双端交付；Owner自然使用仍开放

{marker}
Owner再反馈“看的东西还是有点乱……大家都不知道在干嘛”，沿原UI116-DESIGN-FOUNDATION承接，前两轮外观改善未成立，不把“随身笔记”选择当签收。本批把应用导航与当前录音工具结构分开：固定侧栏，列表只呈现名称/时间/内容；标题旁固定导出，回听后为纪要/文字/笔记；正文退出统计卡片/二层折叠，生成说明转入来源说明；笔记中按需进文档/提问，剪辑与管理放在阅读后。手机同主线、移除主标题周围重复常态说明，问题/草稿/来源/未保存保护和原数据/协议保持。

Windows作者3cb5902d、正常120冻结bc31db12672226fd7c27a98e6a35fc2c1e96b1fe；Android146源2fda58ac159328dbe3c84accf5ac05b6af023df8。120继承当前已提交119指针及87e6倾斜优先源码，没有合入并发未提交文件；不把新UI验收当实体指针通过。固定E源/shared target一轮正常release与MSI，独立核1404来源/312许可及载荷/升级身份；实际Tauri隔离站连续笔记保存、原话来源、限定导出/日期保存、真实进程退出重开通过，未变OS原生对话与普通接收沿原精确源码证据复用。同019f285.520秒已保存真人结果在120实际查看、静音回听、限定预览和真实退出重开通过；原库与4份原音不变、0新录音/模型/云/实卡操作。

正常安装前原118前置身份被守卫拒绝，未启动MSI：嵌软已独立装119。读其完整119安装与体验收尾收据，10:55:38原Owner控制器已关句柄/释放，实际EXE与当前119收据匹配，120为其后代；保留初次前置备份，未放松全局运行守卫。随后119→120于11:07:09–11:07:13正常升级，247份原资料哈希一致。146同签名包/16KiB/实际Java保存预览导出重开核验，一轮共享构建，未重编未变AAR；实机安装5471份旧文件全同。独立显示器45只开普通picker恢复的新公开库，实际改名/文字保存/导出入口/主题/真正进程重开；原索引因一个新公开库变化、5470旧内容完全同、所有旧库和原外观保留，11:59:36类时刻不推造，实际收尾时间见phone146/end-session.json，原库/自有应用/显示器/转发/jar已收尾，临时公开包按精确SHA移除。

失败与修正：首次CSS替换patch格式被拒未改产品；视觉检查发现旧grid挤窄列表，冻结前修正。旧非可视组件环境缺matchMedia、两用例覆写window，修测试环境及新编辑按钮标签后全部受影响契约通过。实机首次严格44px断言误拒43.9983px设备像素取整，实际min-width44/全部字形在框内；0.5CSSpx容差后同一APK通过、没有重包。旧返回原库桥接10秒超时条件本批未再重演：普通返回一次后以原索引ID/DOM外观核验，未读取原库内容。当前正常包已安装，一套ZIP{record['bytes']}B、SHA256 {record['sha256']}，逐成员及私有完整下载回读匹配，单独MSI亦回读匹配；没有新顾客轮次、Owner技术弹窗、前台键鼠接管或清理任务。当前构建缓存61GiB量级、80GiB/30GiB入口守卫生效，未删文件，不承诺十天增长已实测。

整批收据docs/handoffs/20261113-ui-foundation/reader-clarity/software-delivery.json。Owner整体审美/清晰/自然好用仍未签收；原真人短会片尾不确定识别/通用模型事实、实卡长录/指针/硬件/售卖沿各自原任务。下一动作：{next_action}

'''
 # Use the observed phone completion rather than an inferred clock value.
 entry=entry.replace('11:59:36类时刻不推造，实际收尾时间见phone146/end-session.json',read(A/'end-session.json')['at'])
 tmp=log.with_suffix('.reader.tmp');tmp.write_bytes(entry.replace('\n','\r\n').encode('utf8')+raw);assert log.read_bytes()==raw;tmp.replace(log)
 paths=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','docs/handoffs/20261113-ui-foundation','docs/handoffs/20261112-product-closure/windows120']
 for rel in paths[:3]:shutil.copyfile(R/rel,S/rel)
 for rel in paths[3:]:
  for p in(R/rel).rglob('*'):
   if p.is_file():q=S/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 for args in [['add','--',*paths],['diff','--cached','--check','--',*paths,':(exclude)**/*.log',':(exclude)**/*.patch'],['commit','--only','-m','Deliver installed120146 with one clear reader hierarchy and preserved original data','--',*paths]]:subprocess.run(git+args,cwd=S,check=True)
 subprocess.run(git+['push','origin','HEAD'],cwd=S,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
 latest=read(R/'docs/product_backlog.json')['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];print(json.dumps(dict(state=latest['state'],next=latest['next'],delivery=str(H/'software-delivery.json')),ensure_ascii=False),flush=True)
else:raise ValueError(phase)
