from pathlib import Path
from datetime import datetime,timezone,timedelta
import copy,hashlib,json,os,re,shutil,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent;O=W.parent/'outputs';E=Path('E:/CodexData/Companion/.build-cache/product-closure20261112');B=R/'docs/handoffs/20261112-product-closure/windows118';A=R/'docs/handoffs/20261110-android-media-import/android145';H=R/'docs/handoffs/20261113-ui-foundation/application-foundation'
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m'];now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
read=lambda p:json.loads(p.read_bytes())
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def update(state,delivery):
 P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf-8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112'];at=now()
 next_action='118/145随身笔记这一批已安装并完成实际Windows连续保存/限定导出/真正重开、手机公开库改名/文字保存/导出入口/主题和真正重开，原资料保护已核。'+('一个完整软件包已私有完整回读匹配。'if delivery.get('privateRemoteReadbackVerified') else '正在完成一个完整软件包的私有回读。')+'Owner整体外观/自然使用仍未通过，后续只短做人感体验，问题按原稳定ID集中承接；不把软件自验当Owner满意。固件长录/鼠标/独立模型/售卖沿原各自最新待办；不重启已由Owner要求停止的117长录。'
 if 'previous116144BeforeNotebook118145' not in u:u['previous116144BeforeNotebook118145']={k:copy.deepcopy(u.get(k)) for k in ['state','currentSoftwareDelivery','currentWindowsBuild','currentAndroidBuild','currentEngineeringReceipt']}
 u.update(updatedAt=at,state=state,candidateVersion='0.1.118',candidateAndroidVersion='0.1.145',deliveredVersions=dict(windows='0.1.118',android='0.1.145'),installedAndEngineeringReviewed=True,softwareSelfAcceptancePassed=True,currentSoftwareDelivery=str(H/'software-delivery.json'),currentEngineeringReceipt=str(H/'engineering-self-acceptance.json'),ownerAppearanceAccepted=False,ownerExperienceAccepted=False,noMoreOwnerPromptUntilSubstantiveRepair=False)
 u['designFoundationRework20261113'].update(state=state,selectedDirection='随身笔记',delivery=str(H/'software-delivery.json'),engineeringSelfAcceptance=str(H/'engineering-self-acceptance.json'),nativeInstalled=True,ownerAppearanceAccepted=False)
 u['currentWindowsBuild']=dict(state='NORMAL118_INSTALLED_NATIVE_UI_AND_ACTUAL_REOPEN_CHECKED',version='0.1.118',completed=True,installed=True,sourceCommit=delivery['windows']['sourceCommit'],receipt=str(B/'windows-verification.json'),runtime=str(B/'runtime-result.json'),installation=str(B/'installation.json'),worker=None)
 u['currentAndroidBuild']=dict(state='NORMAL145_INSTALLED_ACTUAL_PUBLIC_PHONE_UI_AND_PROCESS_REOPEN_CHECKED',version='0.1.145',completed=True,installed=True,sourceCommit=delivery['android']['sourceCommit'],installation=str(A/'installation.json'),runtime=str(A/'library-review-result.json'),endSession=str(A/'end-session.json'),worker=None)
 u['preOwnerEngineeringAcceptance20261112']=dict(windowsVersion='0.1.118',androidVersion='0.1.145',softwareSelfAcceptancePassed=True,actualNativeProcessRestartPassed=True,actualPhoneReviewed=True,currentReceipt=str(H/'engineering-self-acceptance.json'),privateRemoteReadbackVerified=delivery.get('privateRemoteReadbackVerified',False),ownerPromptStarted=False,ownerExpectedExperience='Short natural aesthetic/clarity/use feedback, no technical checklist.')
 for issue in u['issueReports']:
  if issue['id'] in ['UI116-DESIGN-FOUNDATION','UI115-001','UI114-APPEARANCE']:issue.update(state='NOTEBOOK118145_IMPLEMENTED_INSTALLED_ENGINEERING_CHECKED_OWNER_UX_OPEN',delivery=str(H/'software-delivery.json'),ownerAccepted=False)
 a.update(updatedAt=at,state=state,currentInstalledWindows='0.1.118',currentInstalledAndroid='0.1.145',plannedWindowsVersion='0.1.118',plannedAndroidVersion='0.1.145',plannedVersionsBuilt=True,sourceCheckpoint=delivery['windows']['sourceCommit'],lastCompleteDeliveryReceipt=str(H/'software-delivery.json'),lastCompletePackageSha256=delivery['sha256'],lastWindowsSoftwareDeliveryReceipt=str(B/'windows-verification.json'),lastAndroidSoftwareDeliveryReceipt=str(A/'library-review-result.json'),phoneHoldActive=False,allNonmodelComplete=False,frontendAcceptedPurposeClosed=False,next=next_action,knownJobState='Own118 build/isolated native UI/upgrade and145 build/owned-phone UI/restart/return/close complete; no own live device/MIC/model or Owner prompt. Software delivery private readback '+('complete'if delivery.get('privateRemoteReadbackVerified')else'in progress')+'. Separate117 long stopped09:22:40 by Owner before standard118 upgrade09:23:25; this UI batch did not stop it or infer its qualification.')
 a.update(sourceState='Notebook118 frozen on current117 core;145 Android frozen independently. Both installed with real UI/process restart evidence; Owner aesthetics/use unaccepted.',deliveryExecution=dict(state=state,receipt=str(H/'software-delivery.json'),windowsSource=delivery['windows']['sourceCommit'],androidSource=delivery['android']['sourceCommit'],softwareSelfAcceptancePassed=True,ownerExperienceAccepted=False))
 u['ownerAcceptanceScope20261112'].update(engineeringCurrentDelivery=str(H/'software-delivery.json'),complexPhysicalChecksRemainEngineeringResponsibility=True,currentUiBatchNewAsrOrCloudRun=False)
 c.update(updatedAt=at,state=state,currentPoint=next_action,sourceCommit=delivery['windows']['sourceCommit'],appSourceCommit=delivery['windows']['sourceCommit'],nativeBuilt=True,installed=True,buildKind='normal-local',nativeWholeSoftwareJourneyPassed=True,nativeSoftwareClosureEvidenceAccepted=True,nativeVerification=str(B/'windows-verification.json'),runtimeRun=str(B/'runtime-result.json'),installationReceipt=str(B/'installation.json'),currentSoftwareDeliveryReceipt=str(H/'software-delivery.json'),currentSoftwareDeliverySha256=delivery['sha256'],currentSoftwareDeliveryArchive=delivery['archive'],privateRemoteDeliveryReadbackMatched=delivery.get('privateRemoteReadbackVerified',False),ownerTotalStatus=state,coherentSoftwarePurposeComplete=False,frontendAcceptedPurposeClosed=False)
 c.update(testSourceCommit=read(B/'runtime-result.json')['testSourceCommit'],windowsDeliveryReceipt=str(B/'windows-verification.json'),androidDeliveryReceipt=str(A/'library-review-result.json'),engineeringCoherentSoftwarePurposePassed=True,nativeSoftwareEvidenceScope='Exact118 Tauri continuous saved-note/source/selected-export/date-only/restart, exact145 ordinary public-phone rename/transcript save/export entry/themes/restart; prior unchanged OS-dialog implementation evidence reused. No new physical/model qualification.')
 c['physicalAcceptanceDependency'].update(softwareWindowsVersion='0.1.118',softwareAndroidVersion='0.1.145',softwareReadyForLaterJointTest=True,ownerFunctionalChecklistRequired=False,ownerLongRecordingRequired=False,engineeringOwnsComplexPhysicalChecks=True)
 m['currentBatch'].update(at=at,state=state,remaining='整批118/145已安装/工程自验；Owner观感和自然使用未认可，原物理/模型/完整产品/售卖要求保留。',next=next_action);m['nextBatch'].update(at=at,status=state,next=next_action)
 def splice(key,before,after):
  nonlocal text
  hits=[]
  for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
   value,n=json.JSONDecoder().raw_decode(text[match.end():])
   if value==before:hits.append((match,n))
  assert len(hits)==1,key;match,n=hits[0];text=text[:match.end()]+json.dumps(after,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
 splice('activeNonmodelCompletion20261110',old,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf-8'))
 return next_action

phase=sys.argv[1]
if phase=='prepare':
 proof=read(B/'windows-verification.json');runtime=read(B/'runtime-result.json');installation=read(B/'installation.json');android=read(A/'build-result.json');phone=read(A/'library-review-result.json');end=read(A/'end-session.json')
 assert proof['version']==installation['installedVersion']=='0.1.118'and proof['sourceCommit']==runtime['appSourceCommit']==installation['sourceCommit']
 assert installation['dataManifestIdentical'] and runtime['actualNativeProcessRestart']['allPublicLibraryRowsUnchanged']
 assert phone['actualPhoneReviewed'] and phone['actualProcessRestartPassed'] and end['onlyOldChangeLibraryIndex'] and end['ownedAppDisplayForwardJarClosed']
 assert sha('C:/Program Files/Companion Type/companion-type.exe')==proof['embeddedExeSha256']
 retained=[]
 for rel in ['apps/windows/src-tauri/src','packages/core/src']:
  refs=[subprocess.check_output(git+['rev-parse',commit+':'+rel],cwd=S,text=True).strip()for commit in ['bdfeed4cfce5a5f6ad104c4d876c9ed0e577a69e',proof['sourceCommit']]];assert refs[0]==refs[1];retained.append(dict(path=rel,current117CoreTree=refs[0],delivered118Tree=refs[1]))
 engineering=dict(at=now(),state='NOTEBOOK118145_INSTALLED_ENGINEERING_CONTINUOUS_SOFTWARE_JOURNEY_PASSED',windows=dict(proof=str(B/'windows-verification.json'),runtime=runtime,installation=installation,unchangedCurrent117Core=retained),android=dict(build=android,phone=phone,endSession=end),sourceChecks=dict(windows=str(E/'notebook-foundation20261113/windows-source-final3/result.json'),android=str(E/'notebook-foundation20261113/mobile-source-final2/result.json')),limitations=['Engineering UI and scoped software contracts only; Owner final aesthetics/usability unaccepted.','No new microphone, recording-card, ASR, cloud or general quality run in this UI batch.','Actual native OS dialog/ordinary-recipient code proven unchanged and prior evidence reused; current UI routes and save/export preview/restart checked.','Owner clipboard sequence changed during isolated native test observation; do not claim its global sequence remained unchanged. No Owner keyboard/focus/clipboard content used.'],failuresRetained=['Mobile source synthetic bridge initially returned null AI materials; fixture contracts corrected, no product-null response claimed.','Phone first tab-count check ran before detail loaded; await corrected without rebuild.','Phone ordinary return final10s readback timed out after original activation; independent native index and DOM appearance plus close data guards confirmed return. Original failure retained.','A temporary scoped installer exemption was prepared while117 ran, but no Companion process was running at actual installation. It was unused and removed; original standard guard retained. Initial receipt state label corrected with prior record kept.'],ownerAppearanceAccepted=False,saleQualified=False)
 write(H/'engineering-self-acceptance.json',engineering)
 O.mkdir(exist_ok=True);msi=O/'Companion-Windows-0.1.118.msi';apk=O/'Companion-Android-0.1.145.apk';archive=O/'Companion-Notebook-118-145-20261113.zip'
 assert not any(p.exists() for p in [msi,apk,archive]);shutil.copyfile(proof['msi'],msi);shutil.copyfile(android['apk'],apk);assert sha(msi)==proof['msiSha256']and sha(apk)==android['apkSha256']
 manifest=dict(at=now(),product='Companion',batch='随身笔记界面118/145',windows=dict(version='0.1.118',sourceCommit=proof['sourceCommit'],installer=msi.name,sha256=sha(msi),installed=True,actualNativeUiReviewed=True,actualProcessRestartPassed=True),android=dict(version='0.1.145',sourceCommit=android['sourceCommit'],installer=apk.name,sha256=sha(apk),installed=True,actualPhoneUiReviewed=True,actualProcessRestartPassed=True),engineeringSelfAcceptancePassed=True,ownerAppearanceAccepted=False,ownerExperienceAccepted=False,modelsRun=False,physicalTotalAcceptancePassed=False,saleQualified=False)
 guide='''Companion · 随身笔记界面118/145

打开后先看“录音”。电脑左侧找录音，右侧阅读；手机点进一条录音，再返回列表。
录音名称、日期和已有内容帮助你找回记录。没有文字的录音会显示转写入口；已有纪要直接阅读。
当前录音内，回听听原音，“纪要”看整理结果，“文字”看原文，“补充”放自己的备注、文档和提问。手机的思维导图与翻译在“更多”里。
导出在当前录音的固定位置。先确认所选内容，再保存或交给常用应用。
录音卡入口在电脑顶栏和手机“设备”中。正常接上后继续原有后台接收；需要查看时再打开详情。
设置集中管理外观和已有服务。你填写的文字修改需要保存；切换录音前会保护未保存输入。

本包包含电脑MSI和Android APK。两端正常包已安装并完成工程连续检查；原资料保护已核验。
界面好不好看、是否顺手，仍待你的自然使用反馈。功能和复杂/长时间检查由工程负责，你只需像平时一样简单使用，指出看不懂或不顺的地方。
实体录音、长时间可靠性、独立模型质量及正式售卖资格按各自实际记录，不由这次界面检查替代。
'''
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  z.write(msi,msi.name);z.write(apk,apk.name);z.writestr('开始使用.txt',guide);z.writestr('交付身份.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None;assert hashlib.sha256(z.read(msi.name)).hexdigest()==sha(msi);assert hashlib.sha256(z.read(apk.name)).hexdigest()==sha(apk)
 record=dict(at=now(),state='NOTEBOOK118145_INSTALLED_CHECKED_ONE_KIT_PRIVATE_READBACK_PENDING',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),windows=manifest['windows'],android=manifest['android'],manifest=manifest,privateRemoteReadbackVerified=False,engineeringReceipt=str(H/'engineering-self-acceptance.json'),ownerAppearanceAccepted=False,ownerExperienceAccepted=False,saleQualified=False)
 write(H/'software-delivery.json',record);write(O/'Companion-Notebook-118-145-20261113.json',record);update(record['state'],record);print(json.dumps(record,ensure_ascii=False))
elif phase=='publish':
 record=read(H/'software-delivery.json');repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate']
 release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];back=Path('E:/CodexData/Companion/deliveries/readback-notebook118145');back.mkdir(exist_ok=False)
 for file,digest in [(Path(record['archive']),record['sha256']),(O/'Companion-Windows-0.1.118.msi',record['windows']['sha256'])]:
  assert sha(file)==digest;old=next((x for x in release['assets']if x['name']==file.name),None)
  if old:assert old['digest']=='sha256:'+digest
  else:subprocess.run(['gh','release','upload',tag,str(file),'--repo',repo],check=True)
  subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',file.name,'--dir',str(back)],check=True);assert sha(back/file.name)==digest and(back/file.name).stat().st_size==file.stat().st_size;print(file.name+' private complete readback matched',flush=True)
 record.update(at=now(),state='NOTEBOOK118145_INSTALLED_ENGINEERING_CHECKED_ONE_KIT_PRIVATE_READBACK_VERIFIED_OWNER_UX_OPEN',privateRemoteReadbackVerified=True,privateDraft=release['url'],individualWindowsMsiRemoteReadbackVerified=True);write(H/'software-delivery.json',record);write(O/'Companion-Notebook-118-145-20261113.json',record);update(record['state'],record)
elif phase=='protect':
 record=read(H/'software-delivery.json');assert record['privateRemoteReadbackVerified'];at=now();next_action=update(record['state'],record)
 references=R/'docs/handoffs/20261113-ui-foundation/reference-selection.json';value=read(references);value.update(currentState=record['state'],currentApplicationDelivery=str(H/'software-delivery.json'),selectedDirection='随身笔记',next=next_action);write(references,value)
 for rel in ['AGENTS.md','docs/product_backlog.json','docs/development_log.md']:assert(R/rel).exists()
 agent=R/'AGENTS.md';raw=agent.read_bytes();lines=raw.decode('utf-8-sig').splitlines();idx=next(i for i,x in enumerate(lines)if x.startswith('- 当前实际已装Windows'));lines[idx]='- 当前实际已装Windows0.1.118 / Android0.1.145。沿UI116-DESIGN-FOUNDATION，Owner选“随身笔记”但明确仅稍好/整体仍不合格；真实双端已重组录音→内容阅读、固定回听/导出与补充/更多入口，旧连续外观补丁入口已替换。118保留当前117完整core，正常包同源载荷/实际隔离连续保存导出/真正重开、升级247份原资料不变；145实机公开库改名/文字修改保存/固定导出/主题/真正重开及5413份旧内容不变（仅新公开库使原索引变化）已核，一个软件包私有完整回读匹配。收据docs/handoffs/20261113-ui-foundation/application-foundation/software-delivery.json。Owner最终外观/好用未认可，不把工程自验写成签收；只短做人感体验，功能/复杂长录由工程负责。原117长录由Owner于09:22:40要求停止，先于118正常升级，无本批MIC/设备动作；长录/完整IMU/独立模型/最终硬件/售卖继续按各自原待办。';assert agent.read_bytes()==raw;agent.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 log=R/'docs/development_log.md';raw=log.read_bytes();marker='<!-- notebook118145-coherent-foundation-installed-delivery20261113 -->';assert marker.encode()not in raw
 entry=f'''{marker}
{at} Owner续原话：“也行吧，然后你看一下哪一种比较好一点呢？感觉这个好像比之前的稍微好一点点。你看一下再怎么样做会好一点，主要是这个 ui 要有逻辑清晰的，然后人家能用的，是那个太乱了，乱糟糟的，完全不合格。”沿原UI116-DESIGN-FOUNDATION承接，选随身笔记但不算Owner通过。实际应用按录音→当前内容重组：桌面持久列表/阅读、初次打开上次所选、未保存修改拦住换录音；设备收进固定顶栏，纪要/文字/补充分清，导出独立固定。手机同一主线，3个阅读选择、思维导图/翻译进入更多，名称只显示一遍且与列表一致，原始转写默认阅读/精简为主动选项，导入与接收细节按需打开。Windows旧3份外观补丁导入替换为一个基础样式，手机替换旧两份外观补丁；原数据/静默收取/草稿与恢复保留。

Windows源4ca0f750重组、正常冻结3151a46c76b310443fc95b9e2e531a5e53893d62（118），基于当前117 bdfeed4c，整个生产backend/core树逐一相同，没有回退117共用核心。一次固定E源/shared target正常release，1403源码/312许可/载荷/升级身份独立核；同包真实Tauri隔离连续笔记保存、来源、所选导出、日期清单与实际退出重开通过，原生OS对话/普通接收未变范围复用旧证据。实际118升级116，247份原资料清单完全一致。隔离native观察Owner clipboard sequence发生变化，仅记录事实，不声称全局序列未变；未占Owner桌面/键鼠/读取剪贴板原内容。早先117长录进程已由Owner09:22:40要求停止，标准升级检查09:23:25无Companion进程；准备过的精确CLI例外未使用且已撤掉，原全局运行守卫保留，初始收据状态标签修正并保留原件，不宣称安装时它仍在运行。

Android145源fbb10d1ee34c241d96829c8307e0cbb5441957b0，一次共享原生构建、签名/载荷/16KiB/实际Java保存预览导出回读通过；实际同包安装后5414份旧文件全同。原公共恢复库经普通picker创建，在独立手机显示器实际改名/修订保存/导出入口/主题、真正进程重开后内容可回找；最终仅原库索引因新增公开库变化，5413份旧内容字节一致、所有旧库保留，原资料/原外观已核后关闭自有应用/显示器/端口/jar并精确移除公开临时包。首次实机检查未等详情加载即数tab，修等待后通过，无重编；返回原库的最终10s接口回读超时，实际原索引已提交，独立native索引＋DOM外观和收尾资料守卫核实，未重放返回动作。源码合成bridge空AI材料导致的初次失败、渲染标题被导航遮挡修正、准备脚本匹配/转义失败均保留，不当产品功能进展。

一个118/145软件包{record['bytes']}B，SHA256 {record['sha256']}，逐成员及私有完整下载回读匹配，单独MSI亦回读匹配。两端正常包已装/工程软件自验完成；Owner整体美观与自然好用仍未认可。原物理长录、鼠标、独立模型质量、最终硬件/售卖保持各自原待办，不由本UI批次关闭。本批没有新MIC/BLE/模型/云/Owner技术弹窗或模拟顾客；构建继续固定源/共享缓存和80GiB/30GiB入口，删除0。下一动作：{next_action}

''';assert log.read_bytes()==raw;log.write_bytes(entry.replace('\n','\r\n').encode('utf-8')+raw)
 for name in ['result.json','desktop-current-source.png','result-light.png','result-dark.png','narrow-library.png']:shutil.copyfile(E/'notebook-foundation20261113/windows-source-final3'/name,H/('windows-'+name))
 for name in ['result.json','library-light.png','detail-light.png','detail-dark.png']:shutil.copyfile(E/'notebook-foundation20261113/mobile-source-final2'/name,H/('mobile-source-'+name))
 for name in ['build-result.json','installation.json','process-restart.json','library-review-result.json','end-session.json','original-returned.json','return-readback-timeout.txt','library-light.png','detail-light.png','detail-dark.png']:shutil.copyfile(A/name,H/('phone145-'+name))
 for name in ['deliver_notebook11814520261113.py','review_notebook_phone145.cjs','run_notebook_phone_step20261113.py','confirm_phone145_return20261113.cjs','freeze_notebook11820261113.py']:
  p=H/'engineering-source'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(W/name,p)
 for from_path,to_name in [(E/'notebook-foundation20261113/windows-source-final3/desktop-current-source.png','Companion-Notebook-Desktop-118.png'),(A/'detail-light.png','Companion-Notebook-Phone-145.png')]:shutil.copyfile(from_path,O/to_name)
 paths=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','docs/handoffs/20261113-ui-foundation','docs/handoffs/20261112-product-closure/windows118']
 for rel in paths[:3]:shutil.copyfile(R/rel,S/rel)
 for rel in paths[3:]:
  for p in(R/rel).rglob('*'):
   if p.is_file():q=S/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 checks=git+['-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
 for args in [['add','--',*paths],['diff','--cached','--check','--',*paths,':(exclude)**/*.log',':(exclude)**/*.patch'],['commit','--only','-m','Deliver notebook118145 as one installed and reviewed software batch','--',*paths]]:subprocess.run(checks+args,cwd=S,check=True)
 subprocess.run(git+['push','origin','HEAD'],cwd=S,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
 latest=read(R/'docs/product_backlog.json')['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];print(json.dumps(dict(state=latest['state'],installedWindows=latest['currentInstalledWindows'],installedAndroid=latest['currentInstalledAndroid'],next=latest['next'],ownerExperienceAccepted=False),ensure_ascii=False))
else:raise ValueError(phase)
