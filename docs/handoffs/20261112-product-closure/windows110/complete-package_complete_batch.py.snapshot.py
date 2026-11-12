"""One current product kit, retaining proven platform payloads and honest scope."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys,zipfile

root=Path('C:/Users/Billy/Desktop/Denzic/Companion')
sys.path.insert(0,str(root/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,384*1024**2)
batch=root/'docs/handoffs/20261112-product-closure/windows110'
base=Path('E:/CodexData/Companion/deliveries/20261111-companion-core-windows108-android141.zip')
stage=Path('E:/CodexData/Companion/deliveries/20261112-companion-complete-batch110802141')
out=Path('outputs');archive=out/'Companion-Complete-Candidate-20261112.zip'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not stage.exists() and not archive.exists(),'Preserve an existing assembled kit'
assert shutil.disk_usage(stage.parent).free>30*1024**3+200*1024**2
assert sha(base)=='9cf86b4b2cadbfe31ca505a895a0930a85b42ee9a99b5e5dd646f370ca45fa15'
windows=read(batch/'windows-delivery.json');native=read(batch/'windows-verification.json');runtime=read(batch/'runtime-result.json')
firmware_dir=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/fw66802-package')
firmware=read(firmware_dir/'ota_manifest.json')
install_path=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/install802/result.json');installed=read(install_path)
assert installed['result']=='DEVELOPMENT_IN_PLACE_INSTALLED_AND_BOOT_VERIFIED' and installed['ownHandlesClosed'] is True
assert installed['package']['firmware']==firmware['firmware_version']==66802
assert installed['package']['packageSha256']==firmware['sha256']
identity=installed['postPhysicalIdle']['sections']['ID'];assert int(identity['fw'],16)==66802 and identity['ui']=='85'
assert installed['postPhysicalIdle']['sections']['AUDIO']['mic_run']=='0'
assert installed['originalAudioReads']==installed['originalAudioWrites']==installed['bootWrites']==0
assert windows['version']=='0.1.110' and windows['originalDataManifestIdentical']
stage.mkdir()
def copy(p,name,expected=None):
 target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
 if expected:assert sha(target)==expected,name
 return target
with zipfile.ZipFile(base)as previous:
 old=json.loads(previous.read('manifest.json'))
 retained=['android/Companion-Android-0.1.141.apk','macos/CompanionMac-candidate.zip']
 for name in retained:
  expected=next(row for row in old['files']if row['path']==name)
  target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
  with previous.open(name)as src,target.open('wb')as dst:shutil.copyfileobj(src,dst,128*1024)
  assert target.stat().st_size==expected['bytes'] and sha(target)==expected['sha256']
 for name in ['build-result.json','installation.json','source-freeze.json','detail-workflow.json','detail-reopened.json']:
  target=stage/'evidence/android141'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(previous.read('evidence/android141/'+name))
copy(Path(windows['windowsDeliverable']),'windows/Companion-Windows-0.1.110.msi',windows['installerSha256'])
copy(firmware_dir/firmware['file'],'firmware/companion-update.cup',firmware['sha256'])
copy(firmware_dir/'ota_manifest.json','firmware/ota_manifest.json')
for name in ['windows-delivery.json','windows-verification.json','runtime-result.json','installation.json','unchanged-os-handoff-evidence.json','hosted-runtime-not-started.json','matched-firmware-preparation.json']:
 copy(batch/name,'evidence/windows110/'+name)
copy(out/'Companion-disk-growth-fix-20261112.json','evidence/development-storage.json')
fw_proof=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state=installed['result'],firmware=66802,ui=85,packageSha256=firmware['sha256'],firmwareSourceCommit=read(batch/'matched-firmware-preparation.json')['firmwareSourceCommit'],bootAndNormalApplicationVerified=True,microphoneRunningAtObservation=False,recordingFaultAtObservation=installed['postPhysicalIdle']['sections']['STORAGE']['rec_fault'],pairingAndRecordingMetadataPreserved=installed['pairingAndRecordingMetadataPreserved'],bootWrites=0,originalAudioReads=0,originalAudioWrites=0,allInstallerHandlesClosed=True,sourceReceiptSha256=sha(install_path),deviceUidAndRecordingCatalogExcluded=True,actualNewLongRecordingQualified=False,cpuImprovementPhysicallyMeasured=False)
write(stage/'evidence/firmware802-installation-scoped.json',fw_proof)
write(batch/'ordinary-firmware-installed.json',fw_proof)
board=read(root/'docs/board_turn.json')
guide='''Companion 本轮完整核心候选

主用版本：Windows 0.1.110，录音卡 FW66802 / UI85。
随包保留 Android 0.1.141 和原 Mac 候选。它们沿用原交付范围，Mac 真机资格尚未确认。

开始使用
Windows：安装 windows 目录中的 Companion-Windows-0.1.110.msi，再从开始菜单打开 Companion Type。本机已经升级到这一版，无需重复安装。
录音卡：本机这块板已恢复普通 FW66802 并确认正常启动。firmware 目录保留对应升级包；正在录音、同步或升级时不要重复升级。
Android：android 目录是现有 0.1.141 安装包，已使用该版时无需重复安装。

完成自己的事
按平时的方式录下一场需要保留的内容，在 Companion 接收后看纪要与待办；需要核对时回到原文，留下补充与跟进，再预览和带走自己选择的结果。保存后可以重开继续。
转文字和整理使用应用中的现有配置；首次使用按应用提示准备服务或模型。本包不包含私人服务密钥和大型模型权重。

这一轮的结论
Windows 110 的实际升级、资料保护、后台连续阅读/编辑/保存重开/预览/文件生成已通过；系统保存对话框和普通接收复用109相同实现的有效证据。
固件已恢复普通版并确认启动；当前实卡长录、整条真实会议体验以及CPU优化后的实际降幅尚未通过本轮验收。
后续只集中完成一轮真实使用并反馈一次，包含原定至少2小时实卡录音；无需逐功能打勾。原验收窗口会说明开始时机，未点击开始不会自动录音。
详细来源和实际未验范围见 manifest.json 与 evidence。此为私有核心候选，尚未标记整机售卖合格。
'''
(stage/'开始使用.txt').write_text(guide,encoding='utf-8-sig')
payload_names=['windows/Companion-Windows-0.1.110.msi','firmware/companion-update.cup','firmware/ota_manifest.json',*retained]
files=[dict(path=n,bytes=(stage/n).stat().st_size,sha256=sha(stage/n))for n in payload_names]
manifest=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='COMPANION_COMPLETE_FROZEN_CORE_CANDIDATE_PHYSICAL_TOTAL_PENDING',userResult='同一套版本完成录音、正常接收、纪要/出处核对、跟进、重开与带走结果；集中一次整体反馈。',entry='开始使用.txt',primaryPlatform='Windows',windows=dict(version='0.1.110',sourceCommit=windows['sourceCommit'],installed=True,originalUserDataFiles=windows['originalDataFiles'],originalDataHashIdentical=True,privateContinuousPurposePassed=True,newNativeSystemDialogAndRecipientRetested=False,unchanged109OsEvidenceReused=True),firmware=fw_proof,android=old['android'],retainedMac=old['retainedMac'],files=files,retainedComponentsRebuilt=False,previousVerifiedPackageSha256=sha(base),modelsRunHere=False,ownerPrivateAudioOrPrivateKeysIncluded=False,physicalTotalAcceptancePassed=False,saleQualified=False,remaining=['Current physical full-purpose and >=2h recording coverage','Real CPU improvement/concurrent reliability and unknown pointer hand feel','Android current-real-card full chain and actual Mac qualification','Independent model/facts, paused scopes and formal public sale/service gates'],actualBoardOperation=dict(holder=board.get('holder'),item=board.get('item')),knownHostedTestCondition='GitHub110 native system workflow did not start due account billing; current110 private-station purpose passed, unchanged OS implementation evidence reused from109.')
write(stage/'manifest.json',manifest)
all_files=sorted(p for p in stage.rglob('*')if p.is_file())
(stage/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.relative_to(stage).as_posix()+'\n'for p in all_files),encoding='utf-8')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1)as z:
 for p in sorted(stage.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(stage).as_posix())
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None
 for line in z.read('SHA256SUMS.txt').decode('utf-8').splitlines():
  expected,name=line.split('  ',1)
  with z.open(name)as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==expected,name
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ONE_COMPLETE_CANDIDATE_ARCHIVE_ASSEMBLED_AND_ALL_MEMBERS_VERIFIED',archive=str(archive.resolve()),bytes=archive.stat().st_size,sha256=sha(archive),manifest=manifest,allArchiveMemberChecksumsMatched=True,privateRemoteReadbackVerified=False,physicalTotalAcceptancePassed=False,saleQualified=False)
write(batch/'complete-delivery.json',record);write(out/'Companion-Complete-Candidate-20261112.json',record)
print(json.dumps({k:v for k,v in record.items()if k!='manifest'},ensure_ascii=False,indent=2))
