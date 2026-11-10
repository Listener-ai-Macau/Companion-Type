"""Package one qualified dual-client edit batch; upload a private draft only."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
from release_readback import download
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
REPO="Listener-ai-Macau/Companion-Type";TAG="windows-0.1.78-bb1550c4-candidate";receipt=C/"table-reading-packaged-candidate.json"
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def gh(args):
 p=subprocess.run(["gh",*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
 assert p.returncode==0,p.stderr.decode(errors="replace")[-1000:];return p.stdout
if len(sys.argv)>1 and sys.argv[1]=="resume":
 record=json.loads(receipt.read_text(encoding="utf8"));output=Path(record["package"]);assert sha(output)==record["sha256"]
else:
 assert not receipt.exists(),"An immutable package exists; resume instead of overwriting it"
 win=json.loads((C/"windows096/windows-verification.json").read_text(encoding="utf8"))
 runtime=json.loads((C/"windows096/runtime-result.json").read_text(encoding="utf8"))
 installed=json.loads((C/"windows096/installation.json").read_text(encoding="utf8"))
 apk=json.loads((C/"android132/build-result.json").read_text(encoding="utf8"))
 phone=json.loads((C/"android132/end-session.json").read_text(encoding="utf8"))
 assert runtime["state"]=="WINDOWS096_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED"
 assert win["sourceCommit"]==runtime["appSourceCommit"]==installed["sourceCommit"]
 assert installed["dataManifestIdentical"] and installed["installedExeSha256"]==win["embeddedExeSha256"] and installed["installedDllSha256"]==win["dllSha256"]
 assert phone["ownerOriginalContentByteIdentical"] and phone["ownAppDisplayForwardAndExactTemporaryFilesClosed"]
 customer=json.loads((C/"customer-edit132/end-session.json").read_text(encoding="utf8"));assert customer["ownedAppDisplayForwardJarClosed"] and customer["onlyOldChangeLibraryIndex"] and customer["allPreviousLibrariesRetained"]
 assert sha(Path(win["msi"]))==win["msiSha256"] and sha(Path(apk["apk"]))==apk["apkSha256"]
 base=Path("E:/CodexData/Companion/deliveries/20261110-companion-fw791-win092-android129-candidate.zip")
 base_sha="3ac2b03a6e3284d6d1d78b56132deea7f48932c6734a8ec5fd4f2d786e7d9c5e";assert sha(base)==base_sha
 output=base.parent/"20261111-companion-core-windows096-android132.zip";temp=output.with_suffix(".preparing.zip")
 assert not output.exists() and not temp.exists()
 at=datetime.now().astimezone().isoformat(timespec="seconds");files=[]
 with zipfile.ZipFile(base) as old,zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  prior=json.loads(old.read("delivery.json"));claims={f["path"]:f for f in prior["files"]}
  for name in ["firmware/companion-update.cup","firmware/ota_manifest.json","macos/CompanionMac-candidate.zip"]:
   item=claims[name];digest=hashlib.sha256();size=0
   with old.open(name) as source,z.open(name,"w") as target:
    while data:=source.read(131072):target.write(data);digest.update(data);size+=len(data)
   assert digest.hexdigest()==item["sha256"] and size==item["bytes"];files.append(item)
  for name,path,digest in [("windows/Companion-Windows-0.1.96.msi",Path(win["msi"]),win["msiSha256"]),("android/Companion-Android-0.1.132.apk",Path(apk["apk"]),apk["apkSha256"])]:
   z.write(path,name);files.append({"path":name,"bytes":path.stat().st_size,"sha256":digest})
  z.writestr("evidence/retained-components-delivery.json",old.read("delivery.json"))
  manifest={"at":at,"state":"COMPANION_STRUCTURED_DOCUMENT_READING_CORE_CANDIDATE","saleQualified":False,"files":files,
   "windows":{"version":"0.1.96","sourceCommit":win["sourceCommit"],"installedExactNativeVerified":True},
   "android":{"version":"0.1.132","sourceCommit":apk["sourceCommit"],"backendSourceCommit":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedExactApkVerified":True},
   "retainedFirmware":prior["firmware"],"retainedMac":prior["macos"],"retainedComponentsRebuiltOrRetestedHere":False,
   "retainedComponentBatch":{"file":base.name,"sha256":base_sha},"sourceRepository":"https://github.com/Listener-ai-Macau/Companion-Type",
   "scope":"Structured local worksheet reading with preserved cell values and coordinates, plain text/search/paging, old extraction fallback, native reopen/backup/restore/scoped lifecycle, separate saved AI drafts and ordinary return to source documents/notes. Previously qualified editing095/131 code retained; no new ASR/model/cloud call.",
   "boundaries":"Private candidate, no public release or sale approval. Original real-meeting/model, physical long recording/power, cross-platform/service, release trust/channel and actual customer gates remain open. Prior firmware/Mac bytes are retained candidates, not current physical qualification."}
  z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
  z.writestr("SHA256SUMS.txt","".join(f["sha256"]+"  "+f["path"]+"\n" for f in files))
  evidence=["windows096/windows-verification.json","windows096/runtime-result.json","windows096/runtime-backend-result.json","windows096/installation.json","windows096/source-freeze.json","android132/build-result.json","android132/table-reading.json","android132/table-reopened.json","android132/table-backup-bytes.json","android132/table-restored.json","android132/table-restore-bytes.json","android132/end-session.json","audio-edit-delivered-result.json","windows095/runtime-result.json","android131/editing-control-final.json"]
  for name in evidence:z.write(C/name,"evidence/"+name)
  for name in ["customer-presale.md","customer-afteruse.md","customer-presale-dispatch.txt","customer-afteruse-dispatch.txt","end-session.json"]:
   z.write(C/"customer-edit132"/name,"evidence/customer-edit132/"+name)
  z.writestr("README.txt",'Companion 文档阅读核心验收候选\nWindows 0.1.96 / Android 0.1.132\n\n覆盖更新保留原资料，不卸载、不清数据。补充文档保留原件与提取文字。新提取Excel可按原行列阅读、搜索、分页、核对原始文字；FALSE、0和缺失公式结果保持明确，不运行公式或宏。旧文字缓存仍可读，可主动重新提取生成布局。过大的布局退回完整文字，不删原文。\n\n已保存AI草稿与上传文档、人工备注分开，可直接回文档和备注并保留问题输入。保存、实际进程退出后重开、原件另存、备份恢复及归属清理按附带收据覆盖。已验095/131非破坏录音编辑和任务恢复实现保留，原音、转写、纪要不随文档阅读变化。本轮没有运行转写、训练或在线AI。\n\nmanifest.json和evidence记录实际源码、哈希与验收范围。两类新AI模拟顾客只用独立公开副本；既有人工笔记为辅助条件，不代表新AI结果、硬件体验、付款或真人售后。长备注浏览、材料阅读焦点和极端长行号呈现沿原事项继续改进，不改原文事实。\n\n保留固件66791和Mac候选原字节，本轮未重新实物/Mac验收。正式签名/渠道、实际服务、模型及实物长期资格仍沿原任务。此包为私有工程候选，不是公开售卖批准。不含Owner录音、私人库索引、令牌或密钥。\n')
 with zipfile.ZipFile(temp) as z:
  assert z.testzip() is None
  for f in files:
   with z.open(f["path"]) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==f["sha256"]
 temp.replace(output);record={"at":at,"state":"TABLE_READING_COMPLETE_CANDIDATE_LOCAL_VERIFIED","package":str(output),"bytes":output.stat().st_size,"sha256":sha(output),"files":files,"draftOnly":True,"saleQualified":False,"ownerPrivateDataUploaded":False};receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"]
asset=next((a for a in release["assets"] if a["name"]==output.name),None)
if asset is None:
 gh(["release","upload",TAG,output,"--repo",REPO]);release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"];asset=next(a for a in release["assets"] if a["name"]==output.name)
assert asset["digest"]=="sha256:"+record["sha256"];record["assetId"]=int(asset["apiUrl"].rsplit("/",1)[1])
record["readback"]=download(REPO,record["assetId"],output.parent/"readback"/output.name,record["bytes"],record["sha256"])
record.update(state="TABLE_READING_COMPLETE_CANDIDATE_PRIVATE_DRAFT_FULL_READBACK_IDENTICAL",finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),readbackByteIdentical=True)
receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(json.dumps({k:record[k] for k in ["state","package","bytes","sha256","assetId"]},ensure_ascii=False))
