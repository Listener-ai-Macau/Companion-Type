from pathlib import Path
from datetime import datetime
import copy,hashlib,json,os,re,shutil,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');W=Path(__file__).parent;OUT=W.parent/'outputs';BASE=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');Q=BASE/'visual-meeting20261114';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';C=H/'ui154166';BW=R/'docs/handoffs/20261112-product-closure/windows154';BP=R/'docs/handoffs/20261110-android-media-import/android166';O=BASE/'owner-guided154-20261114';D=Path('E:/CodexData/Companion/deliveries/20261114-ui154166')
read=lambda p:json.loads(p.read_bytes())
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def record(final=False):
 review=read(C/'self-acceptance.json');at=now();p=R/'docs/product_backlog.json';raw=p.read_bytes();text=raw.decode('utf8');d=json.loads(text);a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);u=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112'];c=u['completeProductRework20261113']['noteReadabilityFollowup']['visualMeeting20261114']['uiCraftFollowup20261114'];v=c['simpleExperienceFollowup20261114']
 u.update(updatedAt=at,candidateVersion='0.1.154',candidateAndroidVersion='0.1.166',installedAndEngineeringReviewed=True,softwareSelfAcceptancePassed=True,engineeringReviewReceipt=str(BW/'runtime-result.json'),installationReceipt=str(BW/'installation.json'),currentEngineeringReceipt=str(C/'self-acceptance.json'),ownerActuallyUsedThisCandidate=False,ownerExperienceAccepted=False,currentDesignPreview=str(Q/'overview-r3/result.json'))
 u['preOwnerEngineeringAcceptance20261112'].update(review)
 v.update(updatedAt=at,state='NORMAL154166_INSTALLED_VISUAL_OVERVIEW_SELF_REVIEW_PASSED',selfAcceptance=str(C/'self-acceptance.json'),windowsVersion='0.1.154',androidVersion='0.1.166',ownerWholeExperienceAccepted=False,next='沿整段自然使用反馈继续打磨图形化会议阅读；逐条保留问题，不以完成体验替代整体认可。模型/竞品剩余/实卡原待办保留。')
 c.update(updatedAt=at,currentSources=str(Q/'source154166.json'),state='UI154166_GRAPHICAL_OVERVIEW_ENGINEERING_REVIEWED_OWNER_WHOLE_UX_OPEN',ownerAccepted=False,next=v['next']);a.update(updatedAt=at,currentInstalledWindows='0.1.154',currentInstalledAndroid='0.1.166',phoneHoldActive=False,next=v['next'])
 note='154/166同批正式包实际安装并自验：电脑同一已保存公开半小时会议图形首屏、五个主题逐个原文字对照、结论条件/空行动、完整纪要/返回、备注入口临时输入清空、原始/流畅转写、限定导出预览和真进程退出重开通过；手机同一公开90秒原样例六个主题、浅深/完整内容/目录展开/原话/导出入口与重开通过。无新ASR/LLM/云/外放/板操作。结果入口前移首屏、笔记旧绿色及冗长说明统一修正；电脑旧文件一致；手机旧文件全部保留，仅索引新增公开库，原库外观恢复、自有显示关闭及hold释放。手机未配AI，未声称新在线生成/材料保存导出。154保留148原生143基线；166原AAR不改。首次Windows锁被150占用按规则退出，失败保留，释放后r2复用同一目标继续，无自动清理或抬预算。'
 if final:
  delivery=read(H/'ui154166-delivery.json');assert delivery['privateRemoteReadbackVerified']
  u.update(state='UI154166_GRAPHICAL_OVERVIEW_ONE_KIT_DELIVERED_OWNER_WHOLE_UX_OPEN',currentSoftwareDelivery=str(H/'ui154166-delivery.json'),currentDelivery=str(H/'ui154166-delivery.json'),wholeSoftwareDeliveryReceipt=str(H/'ui154166-delivery.json'),privateRemoteReadbackVerified=True)
  v.update(state='UI154166_ONE_KIT_DELIVERED_148_FEEDBACK_ADDRESSED_WHOLE_UX_OPEN',deliveryReceipt=str(H/'ui154166-delivery.json'),archiveSha256=delivery['sha256'],guideEntry=str(O/'entry.json'),ownerPromptStarted=False)
  c.update(state=v['state'],deliveryReceipt=str(H/'ui154166-delivery.json'),selfAcceptance=str(C/'self-acceptance.json'));a.update(state='UI154166_GRAPHICAL_OVERVIEW_COMPLETE_UI_DELIVERY_FURTHER_WORK_OPEN',lastCompleteDeliveryReceipt=str(H/'ui154166-delivery.json'),lastCompletePackageSha256=delivery['sha256'],sourceCheckpoint={'windows':review['windowsSource'],'android':review['androidSource']},knownJobState='Normal154/166 installed; graphical overview, source/full-note/notes/export/reopen self-reviewed. One private kit fully read back. Phone restored and hold released; original guide ready, not reopened automatically.')
  note='154/166一整包已私有上传并完整下载SHA匹配；主入口改图形化主题选择、单段原文和结论/行动/待确认，完整纪要按需进入且可返回。桌面原整段体验入口更新至154，沿同一公开会与原版同窗，未再自动弹窗。148实际体验“文字太多、希望图像化”的原话/时间/未认可状态保留；visitedSteps为空，不虚记三步走完。无逐功能Owner签收要求，整体观感仍待新反馈。相关入口未发现新的阻塞；结论与后续安排已经前移首屏；手机长标题加六主题时后面主题仍需自然滚动，不声称整场内容首屏可见。其它竞品能力、模型和实卡/售卖原待办未关闭。'
 hits=[]
 for m in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
  value,n=json.JSONDecoder().raw_decode(text[m.end():])
  if value==old:hits.append((m,n))
 assert len(hits)==1;m,n=hits[0];updated=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:];assert p.read_bytes()==raw;p.write_bytes(updated.encode('utf8'))
 p=R/'docs/development_log.md';raw=p.read_bytes();text=raw.decode('utf8');assert text.count('<!-- ui116-simple-experience20261114 -->')==1;assert p.read_bytes()==raw;p.write_bytes((text+'\r\n'+at+' '+note+'\r\n').encode('utf8'))
 if final:
  p=R/'AGENTS.md';raw=p.read_bytes();text=raw.decode('utf8');pattern=r'(?m)^> [^\r\n]*UI116沿同批交付电脑148/手机164[^\r\n]*';assert len(re.findall(pattern,text))==1
  line='> '+at+' UI116沿同批交付电脑154/手机166：148由Owner实际主动开始体验并正常关闭，反馈“文字太多、更加图像化”，整体观感未认可，visitedSteps为空不记三步完成。主入口已改会议一览：可选择主题、单段纪要原文、结论/行动/待确认，完整纪要可回看和返回；浅深一致。正常154/166实际安装，电脑已有公开半小时原结果/五主题/笔记入口/原话/限定导出预览/退出重开与手机公开90秒六主题/浅深/完整内容/导出入口/重开自验通过；无新ASR/LLM/录音/外放/板操作，不称手机新在线材料保存导出。手机旧文件保留/除索引外一致，仅索引新增公开库，原库外观恢复、自有显示已关/hold释放；电脑旧资料一致。154冻结保留148/正常143原生，166为本批冻结原AAR；在途输入/模型未覆盖。整包收据docs/handoffs/20261113-ui-foundation/reader-clarity/ui154166-delivery.json；原版同窗入口已更新154，未再自动弹窗。整体UI/竞品剩余/模型/硬件/售卖保持开放，沿uiCraftFollowup20261114.simpleExperienceFollowup20261114续作，01a3/019e禁读与01a7隔离继续。'
  assert p.read_bytes()==raw;p.write_bytes(re.sub(pattern,lambda _:line,text).encode('utf8'))
 print('ORIGINAL_UI116_RECORD_UPDATED',final)
phase=sys.argv[1]
if phase=='review':
 wi=read(BW/'installation.json');native=read(BASE/'visual-meeting-native154/result.json');detail=read(Path(native['evidence']));phone=read(BP/'end-session.json');assert wi['installedVersion']=='0.1.154'and wi['dataManifestIdentical']and native['sourceStateAndAudioUnchanged']and detail['ui']['actualVisualOverviewAndNotesEntryChecked'];assert phone['ownedAppDisplayForwardJarClosed']and read(BP/'reading-notice-after-restart.json')['visualOverviewExactSourceAndReturn']
 review=dict(at=now(),state='UI154166_NORMAL_INSTALLED_GRAPHICAL_OVERVIEW_SELF_ACCEPTANCE_PASSED',softwareSelfAcceptancePassed=True,windowsVersion='0.1.154',androidVersion='0.1.166',windowsSource=wi['sourceCommit'],androidSource=read(BP/'build-result.json')['sourceCommit'],scope='Graphical meeting overview, exact topic selection, full-note/context and return, notes/transcript/export navigation, both themes and actual process reopen.',publicWindowsScope='Existing saved public30m real output; no regeneration.',publicPhoneScope='Existing saved public90s real output; no regeneration.',nativePublicEvidence=native['evidence'],sourceReview=str(Q/'overview-r3/result.json'),phoneReading=str(BP/'reading-notice-before-restart.json'),phoneReopen=str(BP/'reading-notice-after-restart.json'),oldWindowsFilesByteIdentical=wi['existingDataFiles'],oldPhoneFilesRetained=phone['preexistingFiles'],oldPhoneFilesByteIdentical=phone['preexistingFilesByteIdentical'],phoneOriginalLibraryAppearanceRestored=True,phoneHoldReleased=True,actualPhoneAiGenerationSaveExportTested=False,modelsOrCloudNewlyRun=False,modelQualityQualified=False,ownerPromptStarted=False,ownerAccepted=False,saleQualified=False)
 save(C/'self-acceptance.json',review);record()
elif phase=='entry':
 assert read(C/'self-acceptance.json')['softwareSelfAcceptancePassed'];assert not O.exists();O.mkdir();spec=read(BASE/'owner-guided148-20261114/review-spec.json');save(O/'previous-spec.json',spec);wi=read(BW/'installation.json');spec.update(at=now(),version='0.1.154',sourceCommit=wi['sourceCommit'],verification=str(BW/'windows-verification.json'),engineeringReceipt=str(H/'ui154166-delivery.json'),scopeText='Companion · 看会议脉络，按需展开内容',intro='这版把你说的“文字太多”改成了可点选的会议一览。\n\n从同一场公开会议开始，先看讨论主题；点一个主题看这一段，想深入时再打开完整纪要或原话。需要时留笔记、带走结果。无需听完30分钟或逐功能验收，不会自动录音播放。\n\n有问题就单独记一条，最后留整体感受。',ownerAccepted=False)
 spec['steps'][0]=dict(title='先看懂这场会议',message='打开《公开中文会议（30分钟）》。纪要先展示“会议一览”：选一个讨论主题看看，再按需展开讨论结论或待确认内容。\n\n想看全局关系可切思维导图，想读细节可点“阅读完整纪要”；随时能返回一览。你只需感觉这样是否更容易看懂。')
 save(O/'review-spec.json',spec);link=Path('C:/Users/Billy/Desktop/Companion整段体验.lnk');assert link.is_file();shutil.copyfile(link,O/'previous-shortcut.lnk')
 import comtypes.client
 shortcut=comtypes.client.CreateObject('WScript.Shell',dynamic=True).CreateShortcut(str(link));script=S/'tools/qa/core_acceptance20261109/owner_saved_meeting.py';shortcut.TargetPath=str(Path(sys.executable).with_name('pythonw.exe'));shortcut.Arguments=subprocess.list2cmdline([str(script),'--spec',str(O/'review-spec.json'),'--run']);shortcut.WorkingDirectory=str(script.parent);shortcut.Description='会议一览：先看主题，再按需看完整纪要。问题单独记录，同一个窗口带路。';shortcut.Save()
 ready=json.loads(subprocess.check_output([sys.executable,str(script),'--spec',str(O/'review-spec.json')],text=True,encoding='utf8'));save(O/'readiness.json',ready);assert ready['ready']and not ready['blockers'];save(O/'entry.json',dict(at=now(),shortcut=str(link),spec=str(O/'review-spec.json'),ready=True,ownerPromptStarted=False,existingPublicProfileRetained=True));print('ORIGINAL154_GUIDE_UPDATED_NOT_POPPED')
elif phase=='assemble':
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(5,768*1024**2);review=read(C/'self-acceptance.json');assert read(O/'readiness.json')['ready'];wp=read(BW/'windows-verification.json');pb=read(BP/'build-result.json');public=Path(read(BASE/'visual-meeting-native154/result.json')['evidence']).parent;stage=D/'complete-ui154166';stage.mkdir(exist_ok=False)
 files={'程序/Companion-Windows-0.1.154.msi':Path(wp['msi']),'程序/Companion-Android-0.1.166.apk':Path(pb['apk']),'界面/电脑实际浅色会议一览.png':public/'actual-visual-overview-light.png','界面/电脑实际深色会议一览.png':public/'actual-visual-overview-dark.png','界面/电脑实际完整纪要.png':public/'actual-clear-reader-light.png','界面/电脑实际笔记入口.png':public/'actual-public-notes-entry.png','界面/手机实际浅色会议一览.png':BP/'actual-visual-overview-before-restart-light.png','界面/手机实际深色会议一览.png':BP/'actual-visual-overview-before-restart-dark.png','自验/整套自验范围.json':C/'self-acceptance.json','自验/电脑正常包.json':BW/'windows-verification.json','自验/电脑实际安装.json':BW/'installation.json','自验/电脑连续使用.json':BW/'runtime-result.json','自验/电脑公开会议.json':BASE/'visual-meeting-native154/result.json','自验/手机正常包.json':BP/'build-result.json','自验/手机实际安装.json':BP/'installation.json','自验/手机浅深及原话.json':BP/'reading-notice-before-restart.json','自验/手机实际重开.json':BP/'reading-notice-after-restart.json','自验/手机结束与旧资料.json':BP/'end-session.json','自验/源组件宽窄与浅深.json':Q/'overview-r3/result.json','源码/本批冻结来源.json':Q/'source154166.json'}
 for rel,p in files.items():assert p.is_file(),p;dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert sha(dest)==sha(p)
 guide='''Companion 会议一览 UI 整体交付｜电脑154 / 手机166

本轮针对实际体验“文字太多，希望图像化”修改主入口。打开一场会议，先看到可点选的讨论主题，只展开当前这一段；结论、行动和待确认有并列入口。需要时阅读完整纪要、回原话、留笔记和导出。浅深色沿同一套风格。没有额外生成主题事实、参与人或承诺。

程序已经正常编译并实际安装。桌面“Companion整段体验”更新至本批，沿同一份公开会议副本和原版同一个引导窗口，没有再次自动弹窗。自然用一场会议即可；无需逐按钮签收，有问题单独记，最后说整体感受。

工程自验：电脑使用既有公开半小时中文会议原结果，核对图形一览、五个主题的原文字、结论条件与空行动、完整纪要/返回、笔记入口临时输入清空、原始/流畅转写、所选导出预览和实际退出重开。手机使用既有公开90秒会议，核对六主题、浅深色、完整内容/原话、导出入口与真正重开。两端原纪要和转写保持原样，无新ASR/LLM/云调用、外放、录音或实卡操作。

未改的材料确认保存/指定导出和系统接收路径沿已验证版本与相同源码证据保留；没有称这轮重新走了系统接收方。手机未配置AI服务，不称本轮实际手机在线生成、材料保存导出已验证。结论与后续安排已前移首屏；手机较长标题和六主题时仍需滚动看后面主题。UI整体美感与顺手仍需实际反馈，模型、实卡可靠性、竞品剩余能力与正式售卖资格沿原待办继续。

旧电脑资料字节一致；手机旧文件全部保留、除库索引外内容一致，唯一旧变化是新增公开测试库的索引。原手机库和外观恢复、自有测试显示关闭、占用释放。沿固定目标与80GiB缓存/30GiB空闲约束，无自动清理。
''';(stage/'开始使用.txt').write_text(guide,encoding='utf-8-sig')
 manifest=dict(at=now(),state='UI154166_ONE_COHERENT_GRAPHICAL_OVERVIEW_DELIVERY',versions={'windows':'0.1.154','android':'0.1.166'},windowsSource=wp['sourceCommit'],androidSource=pb['sourceCommit'],windowsInstallerSha256=wp['msiSha256'],androidApkSha256=pb['apkSha256'],sourceFactsPreserved=True,ownerPromptStarted=False,ownerAccepted=False,modelsOrCloudNewlyRun=False,saleQualified=False,files=[dict(path=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(stage.rglob('*'))if p.is_file()]);save(stage/'manifest.json',manifest)
 checks=[(p.relative_to(stage).as_posix(),sha(p))for p in sorted(stage.rglob('*'))if p.is_file()];(stage/'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n'for name,digest in checks),'utf8');archive=OUT/'Companion-UI-154-166-20261114.zip';assert not archive.exists()
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5)as z:
  for p in sorted(stage.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(stage).as_posix())
 with zipfile.ZipFile(archive)as z:
  assert z.testzip()is None
  for name,digest in checks:assert hashlib.sha256(z.read(name)).hexdigest()==digest
 receipt=dict(at=now(),state='UI154166_ONE_KIT_LOCAL_CHECKED_PRIVATE_READBACK_PENDING',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),allArchiveMemberChecksumsMatched=True,manifest=manifest,ownerEntryReady=True,ownerPromptStarted=False,privateRemoteReadbackVerified=False,saleQualified=False);save(H/'ui154166-delivery.json',receipt);save(OUT/'Companion-UI-154-166-status.json',receipt);print(receipt['state'],receipt['sha256'])
elif phase=='publish':
 receipt=read(H/'ui154166-delivery.json');repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate'];release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];archive=Path(receipt['archive']);assert sha(archive)==receipt['sha256'];old=next((x for x in release['assets']if x['name']==archive.name),None)
 if old:assert old['digest']=='sha256:'+receipt['sha256']
 else:subprocess.run(['gh','release','upload',tag,str(archive),'--repo',repo],check=True)
 back=D/'private-readback';back.mkdir(exist_ok=True)
 if not(back/archive.name).exists():subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',str(back)],check=True)
 assert sha(back/archive.name)==receipt['sha256'];receipt.update(at=now(),state='UI154166_ONE_KIT_INSTALLED_SELF_REVIEWED_FULL_PRIVATE_READBACK_VERIFIED',privateRemoteReadbackVerified=True,privateDraft=release['url'],publishedPublicly=False);save(H/'ui154166-delivery.json',receipt);save(OUT/'Companion-UI-154-166-status.json',receipt);print(receipt['state'])
elif phase=='record-final':record(True)
elif phase=='protect':
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(5,1536*1024**2);receipt=read(H/'ui154166-delivery.json');assert receipt['privateRemoteReadbackVerified']and sha(Path(receipt['archive']))==receipt['sha256'];assert read(O/'readiness.json')['ready']and not(O/'owner-progress.json').exists()
 for name,p in {'source-at-freeze.json':Q/'source154166.json','source-review.json':Q/'overview-r3/result.json','actual-public-reading.json':BASE/'visual-meeting-native154/result.json','owner-entry.json':O/'entry.json','owner-readiness.json':O/'readiness.json','retained-first-build-lock-failure.json':Path('E:/CodexData/Companion/deliveries/20261114-ui152165/windows152-local/result.json')}.items():save(C/name,read(p))
 for name in ['check_visual_overview.cjs','run_visual_overview.py','freeze_final_overview154166.py','record_overview154_runtime.py','review_ui_native154.py','review_overview_phone166.cjs','finish_overview154166.py']:
  dest=C/'qa-scripts'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(W/name,dest)
 files=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','docs/handoffs/20261113-ui-foundation/reader-clarity/ui154166-delivery.json']
 for folder in [C,BW,BP]:files += [p.relative_to(R).as_posix()for p in folder.rglob('*')if p.is_file()and(p.suffix=='.json'or folder==C)]
 for rel in sorted(set(files)):dest=S/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/rel,dest);assert sha(R/rel)==sha(dest)
 env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0'};G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
 def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,env=env,text=True,encoding='utf8',stderr=subprocess.STDOUT,timeout=240).strip()
 paths=sorted(set(files));git(S,'add','--',*paths);git(S,'commit','--only','-m','Deliver154166 graphical meeting overview with actual public reading and restoration evidence','--',*paths);head=git(S,'rev-parse','HEAD');print('OWN_PATHS_COMMITTED',head,flush=True);refs=[]
 for root,commit,branch in [(S,head,'work/notebook-ui154166-complete-20261114'),(E,receipt['manifest']['windowsSource'],'work/notebook-ui154-frozen-20261114'),(A,receipt['manifest']['androidSource'],'work/notebook-ui166-phone-20261114')]:
  git(root,'push','origin',commit+':refs/heads/'+branch);assert git(root,'ls-remote','--heads','origin','refs/heads/'+branch).split()[0]==commit;refs.append(dict(branch=branch,commit=commit,remoteExact=True));print(branch,'VERIFIED',flush=True)
 proof=dict(at=now(),state='UI154166_THREE_EXACT_REMOTE_SOURCES_AND_WHOLE_ARCHIVE_READBACK_VERIFIED',sources=refs,archiveSha256=receipt['sha256'],wholeArchivePrivateReadbackVerified=True,canonicalSnapshotHashes={rel:sha(S/rel)for rel in ['AGENTS.md','docs/product_backlog.json','docs/development_log.md']},otherWorkerUncommittedChangesIncluded=False,ownerPromptStarted=False,ownerAccepted=False,saleQualified=False);save(C/'source-protection-final.json',proof);save(OUT/'Companion-UI-154-166-source-protection.json',proof);print(proof['state'])
else:raise ValueError(phase)
