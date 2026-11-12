from pathlib import Path
from datetime import datetime
import json,hashlib,shutil,zipfile,subprocess
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');out=Path(__file__).resolve().parent.parent/'outputs';b=r/'docs/handoffs/20261112-product-closure/windows111';batch=r/'docs/handoffs/20261112-product-closure/frontend111142';batch.mkdir(exist_ok=True);a=r/'docs/handoffs/20261110-android-media-import/android142';phone=a.parent/'customer-edit142'
load=lambda p:json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
proof=load(b/'windows-verification.json');runtime=load(b/'runtime-result.json');install=load(b/'installation.json');build=load(a/'build-result.json');handoff=load(phone/'share-result.json');end=load(phone/'end-session.json')
assert install['dataManifestIdentical'] and install['installedVersion']=='0.1.111' and runtime['newDateOnlySavedAndReopened'];assert handoff['exactPublicTitleAndEntireSelectedNoteVisuallyVerified'] and handoff['exactOwnRecipientClosed'] and end['ownedAppDisplayForwardJarClosed']
msi=Path(proof['msi']);apk=Path(build['apk']);assert sha(msi)==proof['msiSha256'] and sha(apk)==build['apkSha256']
at=datetime.now().astimezone().isoformat(timespec='seconds')
windows={'at':at,'state':'WINDOWS111_MATCHED_NORMAL_LOCAL_MSI_NATIVE_COHERENT_DATE_ONLY_AND_INSTALLED_DATA_PRESERVATION_PASSED','version':'0.1.111','sourceCommit':proof['sourceCommit'],'installerSha256':proof['msiSha256'],'installerBytes':msi.stat().st_size,'windowsDeliverable':str(out/'Companion-Windows-0.1.111.msi'),'runtimeState':runtime['state'],'dateOnlyCalendarSavedAndReopened':True,'originalDataFiles':install['existingDataFiles'],'originalDataManifestIdentical':True,'localNormalReleaseBuilt':True,'hostedCiRun':None,'newNativeSaveCancelOrOrdinaryRecipientRetested':False,'unchanged109OsEvidenceReused':True,'saleQualified':False}
save(b/'windows-delivery.json',windows)
software={'at':at,'state':'FRONTEND_ACCEPTED_MEETING_PURPOSE_CLOSED_READY_FOR_LATER_BOARD_JOINT_ACCEPTANCE','windows':windows,'android':{'version':'0.1.142','sourceCommit':build['sourceCommit'],'apkSha256':build['apkSha256'],'installed':True,'previousFullSoftwarePurposePreserved':True,'actualSystemSaveTxtZipAndProcessReopenPassed':True,'actualOrdinaryWpsRecipientViewedSelectedNote':True,'systemShareCancelPreservedNotes':True,'allPreviousLibrariesRetained':end['allPreviousLibrariesRetained'],'originalContentFilesByteIdentical':end['preexistingFilesByteIdentical'],'onlyOldChangeLibraryIndex':True,'modelsMicBleUsed':False},'softwareScope':['Meeting reading/source lookup and manual follow-up with clear source boundaries','Full selected-content preview, exact per-note scope, save/reopen and actual phone ordinary-file handoff','Date-only manual confirmation without forced time; explicit add-clock behavior preserved','Default total-use entry follows current delivered Windows receipt; software-ready and current-firmware-ready are separate'],'physicalTotalAcceptancePassed':False,'modelQualityQualifiedByThisBatch':False,'saleQualified':False}
save(batch/'frontend-result.json',software)
stage=Path('E:/CodexData/Companion/deliveries/20261112-companion-frontend111142');stage.mkdir(exist_ok=False)
def copy(src,dest):
 target=stage/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target);return {'path':dest,'bytes':target.stat().st_size,'sha256':sha(target)}
files=[copy(msi,'windows/Companion-Windows-0.1.111.msi'),copy(apk,'android/Companion-Android-0.1.142.apk')]
old=load(b.parent/'windows110/complete-delivery.json');archive=Path(old['archive']);assert sha(archive)==old['sha256']
with zipfile.ZipFile(archive) as z:
 blob=z.read('macos/CompanionMac-candidate.zip');target=stage/'optional-macos/CompanionMac-candidate.zip';target.parent.mkdir();target.write_bytes(blob);expected=next(x['sha256'] for x in old['manifest']['files'] if x['path']=='macos/CompanionMac-candidate.zip');assert sha(target)==expected;files.append({'path':target.relative_to(stage).as_posix(),'bytes':target.stat().st_size,'sha256':expected})
for name in ['windows-verification.json','runtime-result.json','installation.json','windows-delivery.json','unchanged-os-handoff-evidence.json','total-use-readiness.json']:copy(b/name,'evidence/windows111/'+name)
for name in ['build-result.json','installation.json','detail-workflow.json','selected-note-result.json','selected-bundle-readback.json','detail-reopened.json','end-session.json']:copy(a/name,'evidence/android142/'+name)
for name in ['share-result.json','end-session.json','ordinary-wps-receiver.png']:copy(phone/name,'evidence/android142-ordinary-handoff/'+name)
copy(batch/'frontend-result.json','evidence/frontend-result.json')
for name in ['Companion-public-selected142.txt','Companion-public-selected142.zip']:copy(a/name,'examples/'+name)
guide='''Companion 前端集中收口版｜Windows 0.1.111 / Android 0.1.142

当前电脑与授权测试手机已经安装对应版本。安装文件分别在 windows、android；无需为查看结果重复安装。
从软件的录音资料库进入已有内容，围绕一场会议阅读纪要、核对转写或补充资料，保存自己的跟进清单，离开后回来继续；需要交接时预览所选正文，再保存文件或交给常用应用。
Windows的日期确认现已支持只选日期直接确认，不强制补时刻；已有明确时刻、主动补充时刻的要求保留。确认后仍需保存清单，应用不会替你确定会议事实或自动创建外部提醒。
手机142保留本轮已验的来源引用、草稿保留、单条范围、TXT/ZIP真实保存回读和进程重开；本次又实际通过系统分享→WPS本地查看，完整选中备注已可阅读。取消分享不改资料；打开系统面板本身不代表已发送。
examples是本轮公开样例的真实导出文件，可直接查看。它们不是你的私人录音，也不是新模型成绩。

这份软件用于接下来的集中板卡联测。工程侧联测入口已跟随当前交付版本，不再指向旧包；软件就绪和当前正常固件身份分别核对。板可用后，在同一轮完整目的中完成实际录音、正常接收、核对跟进、保存重开和带走结果，最后集中反馈，不逐功能派验收。
本批未访问板卡、未录音，也未改变原录音。原用户内容保留；测试会话、临时界面和手机占用已关闭。
Windows111在本机按正常release配置构建并独立核验MSI；本轮后台原生连续目的与日期保存重开通过。系统保存/取消和普通接收保留109相同实现的有效证据，本次111未新测该系统交接。
optional-macos仅保留旧Mac候选，未做本轮Mac真机验收。当前固件实卡可靠性、模型整体质量及正式发布服务条件保留原待办，本包不宣称正式售卖已放行。
'''
(stage/'开始使用.txt').write_text(guide,encoding='utf-8-sig')
manifest={'at':at,'state':software['state'],'entry':'开始使用.txt','files':files,'softwarePurposeClosure':software,'physicalTotalAcceptancePassed':False,'saleQualified':False,'ownerPrivateAudioOrKeysIncluded':False,'retainedMacActualHardwareQualified':False,'softwareHasNoBoardDependency':True}
save(stage/'manifest.json',manifest);checks=[(p.relative_to(stage).as_posix(),sha(p)) for p in sorted(stage.rglob('*')) if p.is_file()];(stage/'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name,digest in checks),encoding='utf-8')
target=out/'Companion-Frontend-Ready-111-142-20261112.zip';assert not target.exists()
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
 for p in sorted(stage.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(stage).as_posix())
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 for name,digest in checks:assert hashlib.sha256(z.read(name)).hexdigest()==digest
receipt={'at':at,'state':'ONE_FRONTEND111142_KIT_READY_PRIVATE_READBACK_PENDING','archive':str(target),'bytes':target.stat().st_size,'sha256':sha(target),'allArchiveMemberChecksumsMatched':True,'manifest':manifest,'privateRemoteReadbackVerified':False,'publishedPublicly':False,'physicalTotalAcceptancePassed':False,'saleQualified':False}
save(batch/'software-delivery.json',receipt);save(out/'Companion-Frontend-Ready-111-142-20261112.json',receipt);shutil.copyfile(msi,out/'Companion-Windows-0.1.111.msi');shutil.copyfile(phone/'ordinary-wps-receiver.png',out/'android142-ordinary-file-handoff.png')
print(json.dumps({k:v for k,v in receipt.items() if k!='manifest'},ensure_ascii=False))
