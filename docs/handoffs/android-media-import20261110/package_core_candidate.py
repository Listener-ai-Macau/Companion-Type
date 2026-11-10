"""One reviewable candidate archive; preserve previous kits and exact binaries."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,zipfile,time,sys
from release_readback import download
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/'android127';at=datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def gh(args):
 p=subprocess.run(['gh',*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr.decode(errors='replace')[-1200:];return p.stdout
if len(sys.argv)>1 and sys.argv[1]=='resume':
 record=json.loads((C/'packaged-candidate.json').read_text(encoding='utf-8'));output=Path(record['package']);assert sha(output)==record['sha256'];asset=json.loads(gh(['api','repos/Listener-ai-Macau/Companion-Type/releases/assets/'+str(record['assetId'])]));assert asset['digest']=='sha256:'+record['sha256'] and asset['size']==record['bytes']
 record['readback']=download('Listener-ai-Macau/Companion-Type',record['assetId'],output.parent/'readback'/output.name,record['bytes'],record['sha256']);record.update(state='CORE_CANDIDATE_ARCHIVE_PRIVATE_DRAFT_READBACK_IDENTICAL',finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),readbackByteIdentical=True);(C/'packaged-candidate.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:record[k] for k in ['state','package','sha256','assetId','readback']},ensure_ascii=False));sys.exit(0)
phone=json.loads((C/'reading127-delivered-result.json').read_text(encoding='utf-8'));win=json.loads((C/'windows-context-delivered-result.json').read_text(encoding='utf-8'))
assert phone['phoneSessionClosed'] and phone['ownerOriginalContentPreserved'] and phone['remoteInstallerReadbackIdentical']
apk=json.loads((O/'build-result.json').read_text());msi=win['checks']['windows-verification'];assert sha(apk['apk'])==apk['apkSha256'] and sha(msi['msi'])==msi['msiSha256']
base=Path('E:/CodexData/Companion/deliveries/20261110-unified087-android124.zip');baseSha='b429f45499915a5e6628c082b6dd2e9daf46fe6c97de5d87c1ef070513da5ff0';assert sha(base)==baseSha
output=Path('E:/CodexData/Companion/deliveries/20261110-companion-core-windows087-android127.zip');assert not output.exists();temporary=output.with_suffix('.preparing.zip');assert not temporary.exists()
files=[]
with zipfile.ZipFile(base) as old,zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
 prior=json.loads(old.read('manifest.json'));retain=['firmware/companion-update.cup','firmware/ota_manifest.json','macos/CompanionMac-candidate.zip'];claims={item['path']:item for item in prior['files']}
 for name in retain:
  expected=claims[name];digest=hashlib.sha256();count=0
  with old.open(name) as source,archive.open(name,'w') as target:
   while data:=source.read(128*1024):target.write(data);digest.update(data);count+=len(data)
  assert digest.hexdigest()==expected['sha256'] and count==expected['bytes'];files.append(expected)
 for name,path,digest in [('windows/Companion-Windows-0.1.87.msi',Path(msi['msi']),msi['msiSha256']),('android/Companion-Android-0.1.127.apk',Path(apk['apk']),apk['apkSha256'])]:
  archive.write(path,name);files.append({'path':name,'sha256':digest,'bytes':path.stat().st_size})
 manifest={'at':at,'state':'COMPANION_CORE_CANDIDATE_FROZEN_NOT_SALE_QUALIFIED','saleQualified':False,'windows':{'version':'0.1.87','sourceCommit':win['sourceCommit'],'installedExactNativeVerified':True,'receipt':'evidence/windows-image-context.json'},'android':{'version':'0.1.127','sourceCommit':apk['sourceCommit'],'backendSourceCommit':'f55f8e83b77c10ca34db442971a045eca1acfdf4','installedExactApkVerified':True,'receipt':'evidence/android-reading-context.json'},'retainedFirmware':prior['firmware'],'retainedMac':prior['macos'],'retainedComponentsRebuiltOrRetestedHere':False,'retainedKit':{'file':base.name,'sha256':baseSha},'files':files,'sourceRepository':'https://github.com/Listener-ai-Macau/Companion-Type','sourceCommits':['c9554c282056fca3aaf2340ce7ef7d2171e98ed7','cff425076be3c3c4ba8bfb2e6d1c8ba0a703520f','f55f8e83b77c10ca34db442971a045eca1acfdf4'],'scope':'Exact application installers and retained firmware/Mac candidates, without user recordings, private library indexes, credentials or signing keys.','remaining':'Original model/real meeting, physical recording/endurance, cross-platform/features, release trust/channel and business/service/customer acceptance gates remain open. Draft backup is not public release.'}
 archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 archive.writestr('SHA256SUMS.txt',''.join(item['sha256']+'  '+item['path']+'\n' for item in files))
 archive.writestr('evidence/android-reading-context.json',json.dumps(phone,ensure_ascii=False,indent=2)+'\n');archive.writestr('evidence/windows-image-context.json',json.dumps(win,ensure_ascii=False,indent=2)+'\n')
 archive.writestr('README.txt',f'''Companion 核心软件验收候选 — {at}

Windows 0.1.87 / Android 0.1.127；保留匹配来源的 FW66788 和 Mac11509eb2 候选。
manifest.json 与 SHA256SUMS.txt 列出实际来源、文件哈希、已验范围及未覆盖条件。

Windows：使用 windows/ 中的 MSI 更新当前用户应用，不卸载或清空资料。当前安装程序与本机已验证087原生程序一致。图文备注、直接时间关联、所选图文ZIP和整库恢复/精确清除已有匹配包证据。
Android：使用 android/ 中 APK 覆盖安装，不清除应用数据。此次沿既有签名的工程候选，正式商店签名/分发尚未完成。已有录音首屏、文件夹/标签/选择、人工备注搜索与定位、图文阅读和取消导入的实际范围见 evidence/。本地内容、原音与模型保留；新模型没有在本批运行。

首次使用从“录音”进入。可导入本机音频/视频，或从“设备”接收录音卡资料。转写保存在本机；AI纪要、问答及翻译使用自行配置的服务，只有主动发起时发送所选文字，可能收费。本包没有附送托管AI、额度或售后服务承诺。整库备份在“设置”；恢复生成独立资料库，可返回原有资料。图文ZIP保留所选原图，Word/PDF等文字格式保留说明与时间。

firmware/ 和 macos/ 是之前统一候选中的原字节，不是本轮新刷机或新Mac实测；固件仍为无屏现板配置/dev_only签名，Mac仍为adhoc工程包。勿将此归档当成量产刷机指令或正式售卖批准。

公开模拟体验与真人购买分开记录；真实多人与模型、当前实物长录/电源、原跨端/服务/正式分发及真实客户门仍按原任务书继续。本包没有用户录音、账号密钥、私有资料索引或签名私钥。
''')
with zipfile.ZipFile(temporary) as archive:
 assert archive.testzip() is None
 for item in files:
  with archive.open(item['path']) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256']
temporary.replace(output);digest=sha(output);repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';release=json.loads(gh(['release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft'] and not any(a['name']==output.name for a in release['assets'])
record={'at':at,'state':'CORE_CANDIDATE_ARCHIVE_LOCAL_VERIFIED_UPLOAD_IN_PROGRESS','package':str(output),'bytes':output.stat().st_size,'sha256':digest,'files':files,'draftOnly':True,'saleQualified':False,'ownerPrivateDataUploaded':False};(C/'packaged-candidate.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
gh(['release','upload',tag,output,'--repo',repo]);release=json.loads(gh(['release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft'];asset=next(a for a in release['assets'] if a['name']==output.name);assert asset['digest']=='sha256:'+digest;identity=int(asset['apiUrl'].rsplit('/',1)[1]);record.update(assetId=identity,state='CORE_CANDIDATE_ARCHIVE_UPLOADED_READBACK_IN_PROGRESS');(C/'packaged-candidate.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
record['readback']=download(repo,identity,output.parent/'readback'/output.name,output.stat().st_size,digest);record.update(state='CORE_CANDIDATE_ARCHIVE_PRIVATE_DRAFT_READBACK_IDENTICAL',finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),readbackByteIdentical=True);(C/'packaged-candidate.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:record[k] for k in ['state','package','sha256','assetId','readback']},ensure_ascii=False))
