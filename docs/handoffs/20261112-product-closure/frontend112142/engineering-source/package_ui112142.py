"""One installed UI repair batch, preserving historical111 and unchanged Android142."""
from pathlib import Path
from datetime import datetime
import json,hashlib,shutil,zipfile,sys,copy
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=Path(__file__).resolve().parent.parent/'outputs';B=R/'docs/handoffs/20261112-product-closure/windows112';F=B.parent/'frontend112142';F.mkdir(exist_ok=False)
A=R/'docs/handoffs/20261110-android-media-import/android142';P=A.parent/'customer-edit142';U=B.parent/'ui-usability';N=U/'guide-native-preview-r7'
read=lambda p:json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
sys.path.insert(0,str(S/'tools/qa/core_acceptance20261109'))
from owner_total_guide import STEPS,native_multiline
from owner_total import os_handoff_reuse_ready
proof=read(B/'windows-verification.json');runtime=read(B/'runtime-result.json');installed=read(B/'installation.json');guide=read(N/'result.json');build=read(A/'build-result.json');phone=read(P/'share-result.json');end=read(P/'end-session.json')
assert proof['version']==installed['installedVersion']=='0.1.112' and installed['dataManifestIdentical']
assert proof['sourceCommit']==runtime['appSourceCommit']==installed['sourceCommit'] and runtime['newDateOnlySavedAndReopened']
assert os_handoff_reuse_ready(runtime['unchangedOsHandoffEvidence'])
assert native_multiline('操作\n\n应看到')=='操作\r\n\r\n应看到'
negative=[]
for field in ['exactCommittedFiles','exactCommandBlocks','currentNativeUiRouteRechecked','currentNativeUiEvidence']:
 changed=copy.deepcopy(runtime['unchangedOsHandoffEvidence']);changed.pop(field);assert not os_handoff_reuse_ready(changed);negative.append(field)
changed=copy.deepcopy(runtime['unchangedOsHandoffEvidence']);changed['uiExportStateAndOperations']['priorNormalizedLfSha256']='0'*64;assert not os_handoff_reuse_ready(changed);negative.append('changed export operation digest')
assert guide['state']=='ORIGINAL_GUIDE_CURRENT_STEP_VISIBILITY_AND_PRIVATE_MODELESS_RENDERING_PASSED' and guide['ownerClipboardSequenceUnchangedAtObservation']
assert phone['exactPublicTitleAndEntireSelectedNoteVisuallyVerified'] and phone['exactOwnRecipientClosed'] and end['ownedAppDisplayForwardJarClosed']
msi=Path(proof['msi']);apk=Path(build['apk']);assert sha(msi)==proof['msiSha256'] and sha(apk)==build['apkSha256']
at=datetime.now().astimezone().isoformat(timespec='seconds')
engineering=dict(at=at,state='UI112_PRODUCT_AND_GUIDANCE_REPAIR_INSTALLED_ENGINEERING_REVIEWED_OWNER_REVIEW_PENDING',uiFeedbackId='owner-ui-usability20261112',windowsVersion='0.1.112',androidUnchanged='0.1.142',productSourceCommit=proof['sourceCommit'],productUiChangeCommit='fe8b1de1e29e52b8c9264a6a3ab67cf14dd7409b',nativeJourney=runtime['nativeUiEvidence'],sourceBrowserEvidence='E:/CodexData/Companion/.build-cache/product-closure20261112/ui-usability-source-r5',actualGuideRender=str(N/'result.json'),guideRenderHostingInstrumentation=guide['engineeringHostInstrumentation'],originalModalOwnerRuntimeNotNewlyProved=True,guidanceMultilineNativeCrLfConfirmed=True,affectedLifecycleTestsPassed=12,actualOsReuseEvidenceAccepted=True,rejectedIncompleteOrChangedEvidenceCases=negative,ownerExperienceAccepted=False,physicalTotalAcceptancePassed=False,saleQualified=False)
write(B/'engineering-review.json',engineering)
windows=dict(at=at,state='WINDOWS112_UI_REPAIR_NORMAL_LOCAL_MSI_INSTALLED_AND_COHERENT_NATIVE_JOURNEY_PASSED',version='0.1.112',sourceCommit=proof['sourceCommit'],installerSha256=proof['msiSha256'],installerBytes=msi.stat().st_size,windowsDeliverable=str(O/'Companion-Windows-0.1.112.msi'),runtimeState=runtime['state'],dateOnlyCalendarSavedAndReopened=True,originalDataFiles=installed['existingDataFiles'],originalDataManifestIdentical=True,localNormalReleaseBuilt=True,hostedCiRun=None,newNativeSaveCancelOrOrdinaryRecipientRetested=False,unchangedOsBackendAndOperationsEvidenceReused=True,currentUiExportRouteRechecked=True,ownerExperienceAccepted=False,saleQualified=False)
write(B/'windows-delivery.json',windows)
software=dict(at=at,state='UI112142_INSTALLED_COHERENT_REPAIR_DELIVERY_OWNER_GUIDED_REVIEW_PENDING',windows=windows,android=dict(version='0.1.142',sourceCommit=build['sourceCommit'],apkSha256=build['apkSha256'],installed=True,reusedUnchanged=True,priorFullSoftwarePurposePreserved=True,actualSystemSaveTxtZipAndProcessReopenPassed=True,actualOrdinaryWpsRecipientViewedSelectedNote=True,systemShareCancelPreservedNotes=True,allPreviousLibrariesRetained=end['allPreviousLibrariesRetained'],originalContentFilesByteIdentical=end['preexistingFilesByteIdentical']),engineeringReview=engineering,ownerExperienceAccepted=False,physicalTotalAcceptancePassed=False,modelQualityQualifiedByThisBatch=False,saleQualified=False)
write(F/'frontend-result.json',software)
stage=Path('E:/CodexData/Companion/deliveries/20261112-companion-ui112142');stage.mkdir(exist_ok=False)
files=[]
def put(src,name):
 target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target);files.append(dict(path=name,bytes=target.stat().st_size,sha256=sha(target)))
put(msi,'windows/Companion-Windows-0.1.112.msi');put(apk,'android/Companion-Android-0.1.142.apk')
old=read(B.parent/'windows110/complete-delivery.json');assert sha(Path(old['archive']))==old['sha256']
with zipfile.ZipFile(old['archive']) as z:
 blob=z.read('macos/CompanionMac-candidate.zip');target=stage/'optional-macos/CompanionMac-candidate.zip';target.parent.mkdir();target.write_bytes(blob)
 expected=next(x['sha256'] for x in old['manifest']['files'] if x['path']=='macos/CompanionMac-candidate.zip');assert sha(target)==expected;files.append(dict(path=target.relative_to(stage).as_posix(),bytes=target.stat().st_size,sha256=expected))
for name in ['frozen-source.json','windows-verification.json','runtime-result.json','installation.json','windows-delivery.json','unchanged-os-handoff-evidence.json','engineering-review.json']:put(B/name,'evidence/windows112/'+name)
for name in ['build-result.json','installation.json','detail-workflow.json','selected-note-result.json','selected-bundle-readback.json','detail-reopened.json','end-session.json']:put(A/name,'evidence/android142/'+name)
for name in ['share-result.json','end-session.json','ordinary-wps-receiver.png']:put(P/name,'evidence/android142-ordinary-handoff/'+name)
for name in ['Companion-public-selected142.txt','Companion-public-selected142.zip']:put(A/name,'examples/'+name)
put(O/'Companion-Acceptance-Supplement.txt','examples/Companion-Acceptance-Supplement.txt')
native=Path(runtime['nativeUiEvidence']).parent
for src,dest in [(native/'product-result-light.png','界面/新版纪要.png'),(native/'product-handoff-light.png','界面/新版导出.png'),(N/'connect.png','界面/带验窗口.png')]:put(src,dest)
instructions='Companion 整轮带验说明｜Windows112 / 手机142\n\n这一轮由原验收窗口逐步带领，每次显示操作和预期结果。用“下一步／上一步”切换说明，问题保留在同一窗口，最后一起提交。下面是回看文本，无需自行按文档逐项验收。\n\n'
instructions+='\n\n'.join(f'{i+1}. {step[0]}\n{step[1]}' for i,step in enumerate(STEPS))+'\n'
(O/'Companion-Guided-Whole-Acceptance.txt').write_text(instructions,encoding='utf-8-sig');put(O/'Companion-Guided-Whole-Acceptance.txt','带验说明.txt')
start='''Companion 界面与带验集中修复版｜Windows 0.1.112 / Android 0.1.142

电脑112已实际安装，升级保留原有资料；手机继续使用已安装的142。无需为查看新版再装一次。

从“设备与同步”连接录音卡，从“我的记录”找内容。打开一条记录后，按“纪要 / 录音与文字 / 笔记与资料 / 导出”找对应内容。已有纪要直接展开；还没生成纪要的录音直接显示原音和文字。配对、诊断、电脑录音等放在需要时展开的区域。
导出先看所选范围，再保存文件；复制内容和更多分享方式保留。清单勾选、引用和保存重开继续可用。

整轮验收由原窗口带领：说明现在点哪里、做什么、应看到什么；可以前后查看步骤，最后一起提交结论。带验说明.txt只供回看，不要求你自己读工程资料。录音由你按实体卡片键开始与停止。

软件工程复核已完成，Owner尚未体验本次新UI。实卡整轮需要原嵌软当前正常固件收尾、核对匹配身份并释放实际占用；这不影响本次软件安装与交付。本包不表示实卡可靠性、模型整体质量或正式售卖已通过。
工程复核使用公开样例，未上传私人录音。手机142复用原已验的系统保存、重开及WPS本地接收证据，本次没有再操作手机。Windows112重新核对了实际新界面的保存/重开/导出路线；系统保存/取消与普通接收的未变底层实现复用109证据，本次未重跑对应系统操作。
optional-macos保留旧Mac候选，未做本轮Mac真机验收。
'''
(stage/'开始使用.txt').write_text(start,encoding='utf-8-sig')
manifest=dict(at=at,state=software['state'],entry='开始使用.txt',files=files,softwarePurposeClosure=software,ownerPrivateAudioOrKeysIncluded=False,softwareHasNoBoardDependency=True,ownerExperienceAccepted=False,physicalTotalAcceptancePassed=False,saleQualified=False)
write(stage/'manifest.json',manifest);checks=[(p.relative_to(stage).as_posix(),sha(p)) for p in sorted(stage.rglob('*')) if p.is_file()];(stage/'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name,digest in checks),encoding='utf8')
target=O/'Companion-UI-112-142-20261112.zip';assert not target.exists()
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
 for p in sorted(stage.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(stage).as_posix())
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 for name,digest in checks:assert hashlib.sha256(z.read(name)).hexdigest()==digest
receipt=dict(at=at,state='ONE_UI112142_KIT_INSTALLED_REMOTE_READBACK_PENDING',archive=str(target),bytes=target.stat().st_size,sha256=sha(target),allArchiveMemberChecksumsMatched=True,manifest=manifest,privateRemoteReadbackVerified=False,publishedPublicly=False,ownerExperienceAccepted=False,physicalTotalAcceptancePassed=False,saleQualified=False)
write(F/'software-delivery.json',receipt);write(O/'Companion-UI-112-142-20261112.json',receipt);shutil.copyfile(msi,O/'Companion-Windows-0.1.112.msi')
for src,dest in [(native/'product-handoff-light.png','Companion-112-export.png'),(N/'connect.png','Companion-112-guidance.png')]:shutil.copyfile(src,O/dest)
print(json.dumps({k:v for k,v in receipt.items() if k!='manifest'},ensure_ascii=False))
