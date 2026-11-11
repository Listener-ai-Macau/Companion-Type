"""Package one qualified dual-client edit batch; upload a private draft only."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
from release_readback import download
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
REPO="Listener-ai-Macau/Companion-Type";TAG="windows-0.1.78-bb1550c4-candidate";receipt=C/"reader-presentation-packaged-candidate.json"
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def gh(args):
 p=subprocess.run(["gh",*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
 assert p.returncode==0,p.stderr.decode(errors="replace")[-1000:];return p.stdout
if len(sys.argv)>1 and sys.argv[1]=="resume":
 record=json.loads(receipt.read_text(encoding="utf8"));output=Path(record["package"]);assert sha(output)==record["sha256"]
else:
 assert not receipt.exists(),"An immutable package exists; resume instead of overwriting it"
 win=json.loads((C/"windows097/windows-verification.json").read_text(encoding="utf8"))
 runtime=json.loads((C/"windows097/runtime-result.json").read_text(encoding="utf8"))
 installed=json.loads((C/"windows097/installation.json").read_text(encoding="utf8"))
 apk=json.loads((C/"android133/build-result.json").read_text(encoding="utf8"))
 phone=json.loads((C/"android133/end-session.json").read_text(encoding="utf8"))
 assert runtime["state"]=="WINDOWS097_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED"
 assert win["sourceCommit"]==runtime["appSourceCommit"]==installed["sourceCommit"]
 assert installed["dataManifestIdentical"] and installed["installedExeSha256"]==win["embeddedExeSha256"] and installed["installedDllSha256"]==win["dllSha256"]
 assert phone["ownerOriginalContentByteIdentical"] and phone["ownAppDisplayForwardAndExactTemporaryFilesClosed"]
 customer=json.loads((C/"customer-edit133/end-session.json").read_text(encoding="utf8"));assert customer["ownedAppDisplayForwardJarClosed"] and customer["onlyOldChangeLibraryIndex"] and customer["allPreviousLibrariesRetained"]
 assert sha(Path(win["msi"]))==win["msiSha256"] and sha(Path(apk["apk"]))==apk["apkSha256"]
 base=Path("E:/CodexData/Companion/deliveries/20261110-companion-fw791-win092-android129-candidate.zip")
 base_sha="3ac2b03a6e3284d6d1d78b56132deea7f48932c6734a8ec5fd4f2d786e7d9c5e";assert sha(base)==base_sha
 output=base.parent/"20261111-companion-core-windows097-android133.zip";temp=output.with_suffix(".preparing.zip")
 assert not output.exists() and not temp.exists()
 at=datetime.now().astimezone().isoformat(timespec="seconds");files=[]
 with zipfile.ZipFile(base) as old,zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  prior=json.loads(old.read("delivery.json"));claims={f["path"]:f for f in prior["files"]}
  for name in ["firmware/companion-update.cup","firmware/ota_manifest.json","macos/CompanionMac-candidate.zip"]:
   item=claims[name];digest=hashlib.sha256();size=0
   with old.open(name) as source,z.open(name,"w") as target:
    while data:=source.read(131072):target.write(data);digest.update(data);size+=len(data)
   assert digest.hexdigest()==item["sha256"] and size==item["bytes"];files.append(item)
  for name,path,digest in [("windows/Companion-Windows-0.1.97.msi",Path(win["msi"]),win["msiSha256"]),("android/Companion-Android-0.1.133.apk",Path(apk["apk"]),apk["apkSha256"])]:
   z.write(path,name);files.append({"path":name,"bytes":path.stat().st_size,"sha256":digest})
  z.writestr("evidence/retained-components-delivery.json",old.read("delivery.json"))
  manifest={"at":at,"state":"COMPANION_RECENT_NOTES_AND_DOCUMENT_READING_CORE_CANDIDATE","saleQualified":False,"files":files,
   "windows":{"version":"0.1.97","sourceCommit":win["sourceCommit"],"installedExactNativeVerified":True},
   "android":{"version":"0.1.133","sourceCommit":apk["sourceCommit"],"backendSourceCommit":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedExactApkVerified":True},
   "retainedFirmware":prior["firmware"],"retainedMac":prior["macos"],"retainedComponentsRebuiltOrRetestedHere":False,
   "retainedComponentBatch":{"file":base.name,"sha256":base_sha},"sourceRepository":"https://github.com/Listener-ai-Macau/Companion-Type",
   "scope":"Recent/created note reading with reversible long-note disclosure, complete original edit and search target; document reader/list focus and one-line worksheet row coordinates. Native functional sources unchanged from qualified096/132. Explicit unchanged native storage/backup evidence retained, not requalified by UI-only changes. No new ASR/model/cloud call.",
   "boundaries":"Private candidate, no public release or sale approval. Original real-meeting/model, physical long recording/power, cross-platform/service, release trust/channel and actual customer gates remain open. Prior firmware/Mac bytes are retained candidates, not current physical qualification."}
  z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
  z.writestr("SHA256SUMS.txt","".join(f["sha256"]+"  "+f["path"]+"\n" for f in files))
  evidence=["windows097/windows-verification.json","windows097/runtime-result.json","windows097/runtime-backend-result.json","windows097/installation.json","windows097/source-freeze.json","android133/build-result.json","android133/installation.json","android133/reader-notes.json","android133/reader-documents.json","android133/reader-content-preserved.json","android133/reader-working-library.json","android133/reader-entry-backup.json","windows097/notes-reading-ui.json","reader-presentation-source-checks.json","table-reading-delivered-result.json","android132/table-restore-bytes.json","android133/end-session.json","audio-edit-delivered-result.json","windows095/runtime-result.json","android131/editing-control-final.json"]
  for name in evidence:z.write(C/name,"evidence/"+name)
  for name in ["customer-presale.md","customer-afteruse.md","customer-presale-dispatch.txt","customer-afteruse-dispatch.txt","end-session.json"]:
   z.write(C/"customer-edit133"/name,"evidence/customer-edit133/"+name)
  z.writestr("README.txt",'Companion 长备注与材料阅读核心候选\nWindows 0.1.97 / Android 0.1.133\n\n覆盖升级保留原资料。长备注默认按最近更新阅读，可切回创建时间；旧长备注可展开全文，编辑仍加载完整原文，搜索命中直接显示完整内容。打开文档自动进入阅读，材料列表入口可以返回；表格长行号保持一行，说明与横向阅读提示保持在可见宽度内。\n\n本批只改相关前端呈现。实际普通界面操作、精确安装包与数据保留范围见evidence。后端功能源码与已验096/132一致，复用原存储/备份/恢复范围；095/131录音编辑和任务恢复实现保持。没有运行转写、训练或在线AI。\n\nAI模拟客户使用四条公开记录的独立副本，旧人工工程备注是辅助条件；没有真人订单、真实录音质量或长期售后结论。保留固件66791与Mac候选原字节，本批不增加其验收范围。原模型、实物长录/电源、跨端服务、正式签名/渠道与支持门仍开放。此包是私有工程候选，不是公开售卖批准。不含Owner录音、私人资料索引、令牌或密钥。\n')
 with zipfile.ZipFile(temp) as z:
  assert z.testzip() is None
  for f in files:
   with z.open(f["path"]) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==f["sha256"]
 temp.replace(output);record={"at":at,"state":"READER_PRESENTATION_COMPLETE_CANDIDATE_LOCAL_VERIFIED","package":str(output),"bytes":output.stat().st_size,"sha256":sha(output),"files":files,"draftOnly":True,"saleQualified":False,"ownerPrivateDataUploaded":False};receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"]
asset=next((a for a in release["assets"] if a["name"]==output.name),None)
if asset is None:
 gh(["release","upload",TAG,output,"--repo",REPO]);release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"];asset=next(a for a in release["assets"] if a["name"]==output.name)
assert asset["digest"]=="sha256:"+record["sha256"];record["assetId"]=int(asset["apiUrl"].rsplit("/",1)[1])
record["readback"]=download(REPO,record["assetId"],output.parent/"readback"/output.name,record["bytes"],record["sha256"])
record.update(state="READER_PRESENTATION_COMPLETE_CANDIDATE_PRIVATE_DRAFT_FULL_READBACK_IDENTICAL",finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),readbackByteIdentical=True)
receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(json.dumps({k:record[k] for k in ["state","package","bytes","sha256","assetId"]},ensure_ascii=False))
