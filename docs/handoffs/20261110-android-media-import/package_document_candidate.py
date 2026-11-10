"""Freeze the complete matched document batch; retain prior component bytes.
Requires actual native runtime and installed-payload receipts. Draft only.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
from release_readback import download
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate';receipt=C/'documents-packaged-candidate.json'
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def gh(args):
 p=subprocess.run(['gh',*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr.decode(errors='replace')[-1200:];return p.stdout
if len(sys.argv)>1 and sys.argv[1]=='resume':
 record=json.loads(receipt.read_text(encoding='utf8'));output=Path(record['package']);assert sha(output)==record['sha256'];release=json.loads(gh(['release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft'];asset=next(a for a in release['assets'] if a['name']==output.name);assert asset['digest']=='sha256:'+record['sha256'];record['assetId']=int(asset['apiUrl'].rsplit('/',1)[1])
else:
 assert not receipt.exists(),'Use resume for an already frozen immutable package'
 batch=json.loads((C/'documents-delivered-result.json').read_text(encoding='utf8'));assert batch['androidDelivered'] and batch['windowsDelivered'] and batch['phoneSessionClosed'] and batch['ownerOriginalContentPreserved'];phone=json.loads((C/'documents-android129-result.json').read_text(encoding='utf8'));win=json.loads((C/'windows091/windows-verification.json').read_text(encoding='utf8'));installed=json.loads((C/'windows091/installation.json').read_text(encoding='utf8'));runtime=json.loads((C/'windows091/runtime-result.json').read_text(encoding='utf8'));assert installed['dataManifestIdentical'] and installed['installedVersion']=='0.1.91';assert runtime['state']=='WINDOWS091_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED' and runtime['appSourceCommit']==win['sourceCommit'];assert installed['installedExeSha256']==win['embeddedExeSha256'] and installed['installedDllSha256']==win['dllSha256']
 apk=json.loads((C/'android129/build-result.json').read_text(encoding='utf8'));assert sha(apk['apk'])==apk['apkSha256'] and sha(win['msi'])==win['msiSha256'];base=Path('E:/CodexData/Companion/deliveries/20261110-companion-core-windows087-android127.zip');base_sha='45f4df9b8bff84d0e3bb52e594a8e6464866ee221f88d604c22a265d67350609';assert sha(base)==base_sha
 output=base.parent/'20261110-companion-core-windows091-android129.zip';assert not output.exists();temporary=output.with_suffix('.preparing.zip');assert not temporary.exists();files=[];at=datetime.now().astimezone().isoformat(timespec='seconds')
 with zipfile.ZipFile(base) as old,zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
  prior=json.loads(old.read('manifest.json'));claims={i['path']:i for i in prior['files']}
  for name in ['firmware/companion-update.cup','firmware/ota_manifest.json','macos/CompanionMac-candidate.zip']:
   item=claims[name];digest=hashlib.sha256();count=0
   with old.open(name) as source,archive.open(name,'w') as target:
    while data:=source.read(128*1024):target.write(data);digest.update(data);count+=len(data)
   assert digest.hexdigest()==item['sha256'] and count==item['bytes'];files.append(item)
  for name,path,digest in [('windows/Companion-Windows-0.1.91.msi',Path(win['msi']),win['msiSha256']),('android/Companion-Android-0.1.129.apk',Path(apk['apk']),apk['apkSha256'])]:
   archive.write(path,name);files.append({'path':name,'sha256':digest,'bytes':path.stat().st_size})
  manifest={'at':at,'state':'COMPANION_COMPLETE_DOCUMENT_CORE_CANDIDATE_NOT_SALE_QUALIFIED','saleQualified':False,'windows':{'version':'0.1.91','sourceCommit':win['sourceCommit'],'installedExactNativeVerified':True,'receipt':'evidence/document-batch.json'},'android':{'version':'0.1.129','sourceCommit':apk['sourceCommit'],'backendSourceCommit':phone['backendSourceCommit'],'installedExactApkVerified':True,'receipt':'evidence/android-documents.json'},'retainedFirmware':prior['retainedFirmware'],'retainedMac':prior['retainedMac'],'retainedComponentsRebuiltOrRetestedHere':False,'retainedKit':{'file':base.name,'sha256':base_sha},'files':files,'sourceRepository':'https://github.com/Listener-ai-Macau/Companion-Type','sourceCommits':[apk['sourceCommit'],win['sourceCommit'],phone['backendSourceCommit']],'scope':'Exact matched application installers with real local document originals/extraction/reading/save/backup/purge evidence, and unchanged retained firmware/Mac candidates. No user recordings, private library indexes, credentials or signing keys.','onlineAiDocumentGenerationQualified':False,'remaining':'Original model/real meeting, physical long recording/power/endurance, other software parity, cross-platform/service, release trust/channel and real customer gates remain open. This private draft is not a public release.'}
  archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');archive.writestr('SHA256SUMS.txt',''.join(i['sha256']+'  '+i['path']+'\n' for i in files));archive.writestr('evidence/document-batch.json',json.dumps(batch,ensure_ascii=False,indent=2)+'\n');archive.writestr('evidence/android-documents.json',json.dumps(phone,ensure_ascii=False,indent=2)+'\n')
  for name in ['customer-presale.md','customer-afteruse.md']:archive.write(C/'android129'/name,'evidence/'+name)
  archive.writestr('README.txt',f'''Companion 核心软件验收候选 — {at}

Windows 0.1.91 / Android 0.1.129；保留原 FW66788 和 Mac11509eb2 候选字节。
manifest.json、SHA256SUMS.txt 和 evidence/ 列出实际来源、文件校验、已验范围与未覆盖条件。

Windows：使用 windows/ 中 MSI 更新，不卸载或清空资料。Android：使用 android/ 中 APK 覆盖安装，不清除应用数据。安卓沿既有工程签名，正式商店签名与公开渠道尚未完成。

录音详情中的“补充材料”可保存 PDF、DOCX、XLSX、PPTX、TXT、MD 和 CSV，每份20MB以内。先保存原件，打开材料后由你点“在本机提取文字”；不自动上传、不覆盖会议转写。材料可搜索、重开阅读及另存原件。扫描图像和图中文字暂不识别；受限制、需要密码、没有文字、复杂排版或特殊编码会明确提示。PDF读取需要受支持的系统WebView，旧组件可保留原件并提示更新。原表公式、外部链接和宏不会运行；没有已保存结果的公式不会被当成已确认数值。

在“问AI / 生成材料”中，文档默认不勾选；只有主动选择并开始整理后，才会把选中材料的提取文字发送给自行配置的AI服务。文档原件、音频和密码不随本次提问发送。人工补充与会议转写分别标明，材料中的计划不是会议已作决定。本批没有在未配置服务的手机上实际调用在线文档生成；不把来源选择验证当成在线生成质量通过。本包不附送托管AI、额度、价格或售后服务承诺。

整份备份位于“设置”；恢复生成独立资料库，可返回原有资料。补充原件与提取文字随会议备份恢复。移除材料入口会保留原件，永久清除整条录音时才回收可确认归属的材料。旧录音、图文备注、人工修订、分类标签、搜索、回听及已有交付基线继续保留。

firmware/ 和 macos/ 来自前一统一候选，本轮未新刷机或新Mac实测；固件仍为无屏现板/dev_only候选，Mac仍为adhoc工程包。此归档不是量产刷机指令、正式售卖批准或真人购买证明。模型、复杂多人、实物长录与电源、原跨端/服务/正式分发及其余对标项沿原任务继续。
''')
 with zipfile.ZipFile(temporary) as archive:
  assert archive.testzip() is None
  for item in files:
   with archive.open(item['path']) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256']
 temporary.replace(output);record={'at':at,'state':'COMPLETE_DOCUMENT_CANDIDATE_ARCHIVE_LOCAL_VERIFIED_UPLOAD_IN_PROGRESS','package':str(output),'bytes':output.stat().st_size,'sha256':sha(output),'files':files,'draftOnly':True,'saleQualified':False,'ownerPrivateDataUploaded':False};receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');release=json.loads(gh(['release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft'] and not any(a['name']==output.name for a in release['assets']);gh(['release','upload',tag,output,'--repo',repo]);release=json.loads(gh(['release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft'];asset=next(a for a in release['assets'] if a['name']==output.name);assert asset['digest']=='sha256:'+record['sha256'];record.update(assetId=int(asset['apiUrl'].rsplit('/',1)[1]),state='COMPLETE_DOCUMENT_CANDIDATE_ARCHIVE_UPLOADED_READBACK_PENDING');receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
record['readback']=download(repo,record['assetId'],output.parent/'readback'/output.name,record['bytes'],record['sha256']);record.update(state='COMPLETE_DOCUMENT_CANDIDATE_ARCHIVE_PRIVATE_DRAFT_READBACK_IDENTICAL',finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),readbackByteIdentical=True);receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:record[k] for k in ['state','package','bytes','sha256','assetId','readback']},ensure_ascii=False))
