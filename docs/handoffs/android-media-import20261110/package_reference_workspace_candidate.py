"""Package one qualified dual-client edit batch; upload a private draft only."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
from release_readback import download
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
REPO="Listener-ai-Macau/Companion-Type";TAG="windows-0.1.78-bb1550c4-candidate";receipt=C/"reference-workspace-packaged-candidate.json"
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def gh(args):
 p=subprocess.run(["gh",*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
 assert p.returncode==0,p.stderr.decode(errors="replace")[-1000:];return p.stdout
if len(sys.argv)>1 and sys.argv[1]=="resume":
 record=json.loads(receipt.read_text(encoding="utf8"));output=Path(record["package"]);assert sha(output)==record["sha256"]
else:
 assert not receipt.exists(),"An immutable package exists; resume instead of overwriting it"
 win=json.loads((C/"windows098/windows-verification.json").read_text(encoding="utf8"))
 runtime=json.loads((C/"windows098/runtime-result.json").read_text(encoding="utf8"))
 installed=json.loads((C/"windows098/installation.json").read_text(encoding="utf8"))
 apk=json.loads((C/"android134/build-result.json").read_text(encoding="utf8"))
 phone=json.loads((C/"android134/end-session.json").read_text(encoding="utf8"))
 assert runtime["state"]=="WINDOWS098_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED"
 assert win["sourceCommit"]==runtime["appSourceCommit"]==installed["sourceCommit"]
 assert installed["dataManifestIdentical"] and installed["installedExeSha256"]==win["embeddedExeSha256"] and installed["installedDllSha256"]==win["dllSha256"]
 assert phone["ownerOriginalContentByteIdentical"] and phone["ownAppDisplayForwardAndExactTemporaryFilesClosed"]
 customer=json.loads((C/"customer-edit134/end-session.json").read_text(encoding="utf8"));assert customer["ownedAppDisplayForwardJarClosed"] and customer["onlyOldChangeLibraryIndex"] and customer["allPreviousLibrariesRetained"]
 assert sha(Path(win["msi"]))==win["msiSha256"] and sha(Path(apk["apk"]))==apk["apkSha256"]
 base=Path("E:/CodexData/Companion/deliveries/20261110-companion-fw791-win092-android129-candidate.zip")
 base_sha="3ac2b03a6e3284d6d1d78b56132deea7f48932c6734a8ec5fd4f2d786e7d9c5e";assert sha(base)==base_sha
 output=base.parent/"20261111-companion-core-windows098-android134.zip";temp=output.with_suffix(".preparing.zip")
 assert not output.exists() and not temp.exists()
 at=datetime.now().astimezone().isoformat(timespec="seconds");files=[]
 with zipfile.ZipFile(base) as old,zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  prior=json.loads(old.read("delivery.json"));claims={f["path"]:f for f in prior["files"]}
  for name in ["firmware/companion-update.cup","firmware/ota_manifest.json","macos/CompanionMac-candidate.zip"]:
   item=claims[name];digest=hashlib.sha256();size=0
   with old.open(name) as source,z.open(name,"w") as target:
    while data:=source.read(131072):target.write(data);digest.update(data);size+=len(data)
   assert digest.hexdigest()==item["sha256"] and size==item["bytes"];files.append(item)
  for name,path,digest in [("windows/Companion-Windows-0.1.98.msi",Path(win["msi"]),win["msiSha256"]),("android/Companion-Android-0.1.134.apk",Path(apk["apk"]),apk["apkSha256"])]:
   z.write(path,name);files.append({"path":name,"bytes":path.stat().st_size,"sha256":digest})
  z.writestr("evidence/retained-components-delivery.json",old.read("delivery.json"))
  manifest={"at":at,"state":"COMPANION_MEETING_REFERENCE_WORKSPACE_CORE_CANDIDATE","saleQualified":False,"files":files,
   "windows":{"version":"0.1.98","sourceCommit":win["sourceCommit"],"installedExactNativeVerified":True},
   "android":{"version":"0.1.134","sourceCommit":apk["sourceCommit"],"backendSourceCommit":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedExactApkVerified":True},
   "retainedFirmware":prior["firmware"],"retainedMac":prior["macos"],"retainedComponentsRebuiltOrRetestedHere":False,
   "retainedComponentBatch":{"file":base.name,"sha256":base_sha},"sourceRepository":"https://github.com/Listener-ai-Macau/Companion-Type",
   "scope":"Separate stable manual-note/image, document and AI panes. Ordinary source routing selects the correct pane before focus. Actual unsaved manual note and unsent AI question retained across document/source switches; mobile management/marks/audio editing grouped outside primary reading. Existing097/133 full-note/table/search behavior and unchanged096/132 native storage evidence retained. No ASR/model/cloud call.",
   "boundaries":"Private candidate, no public release or sale approval. Original real-meeting/model, physical long recording/power, cross-platform/service, release trust/channel and actual customer gates remain open. Prior firmware/Mac bytes are retained candidates, not current physical qualification."}
  z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
  z.writestr("SHA256SUMS.txt","".join(f["sha256"]+"  "+f["path"]+"\n" for f in files))
  evidence=["windows098/windows-verification.json","windows098/runtime-result.json","windows098/runtime-backend-result.json","windows098/installation.json","windows098/source-freeze.json","android134/build-result.json","android134/installation.json","android134/reader-notes.json","android134/reference-switching.json","android134/reference-tools-entry.json","android134/reader-documents.json","android134/reader-content-preserved.json","android134/reader-working-library.json","android134/reader-entry-backup.json","windows098/notes-reading-ui.json","reference-workspace-source-checks.json","reader-presentation-delivered-result.json","table-reading-delivered-result.json","android132/table-restore-bytes.json","android134/end-session.json","audio-edit-delivered-result.json","windows095/runtime-result.json","android131/editing-control-final.json"]
  for name in evidence:z.write(C/name,"evidence/"+name)
  for name in ["customer-presale.md","customer-afteruse.md","customer-presale-dispatch.txt","customer-afteruse-dispatch.txt","end-session.json"]:
   z.write(C/"customer-edit134"/name,"evidence/customer-edit134/"+name)
  z.writestr("README.txt","Companion 会后资料分区核心候选\nWindows 0.1.98 / Android 0.1.134\n\n覆盖升级保留原资料。自己的便签与图片、补充文档、AI问答与整理材料分别查看，切换视图保持原有组件及未保存输入。已有AI回文档/备注入口先选择正确区域，再回到资料；返回后未发送问题保持。手机管理、重点与音频编辑集中在录音工具，读会议时更聚焦。\n\n097/133最近/创建顺序、长备注全文/完整编辑、搜索命中全文和原单元格阅读保持。本批不改原生业务接口、原音或存储格式；096/132文档备份/恢复和095/131录音编辑资格按附带原证据明确复用。新双端普通界面和升级原资料保护范围见evidence。没有运行转写、训练或在线AI。\n\n新AI模拟使用者使用四条公开记录的独立副本，旧人工工程备注是辅助条件，不代表真人购买、声音/模型质量或长期售后。每句人工便签的持久来源链接和独立会前清单愿望仍沿原事项保留，没有冒充本批已实现。保留固件66791与Mac候选原字节，本批不增加其实物/Mac资格。正式签名/服务渠道、模型、实物长录与电源、Owner及真实顾客门仍开放。本包是私有工程候选，不是公开售卖批准，不含Owner私人录音、资料索引、令牌或密钥。\n")
 with zipfile.ZipFile(temp) as z:
  assert z.testzip() is None
  for f in files:
   with z.open(f["path"]) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==f["sha256"]
 temp.replace(output);record={"at":at,"state":"REFERENCE_WORKSPACE_COMPLETE_CANDIDATE_LOCAL_VERIFIED","package":str(output),"bytes":output.stat().st_size,"sha256":sha(output),"files":files,"draftOnly":True,"saleQualified":False,"ownerPrivateDataUploaded":False};receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"]
asset=next((a for a in release["assets"] if a["name"]==output.name),None)
if asset is None:
 gh(["release","upload",TAG,output,"--repo",REPO]);release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"];asset=next(a for a in release["assets"] if a["name"]==output.name)
assert asset["digest"]=="sha256:"+record["sha256"];record["assetId"]=int(asset["apiUrl"].rsplit("/",1)[1])
record["readback"]=download(REPO,record["assetId"],output.parent/"readback"/output.name,record["bytes"],record["sha256"])
record.update(state="REFERENCE_WORKSPACE_COMPLETE_CANDIDATE_PRIVATE_DRAFT_FULL_READBACK_IDENTICAL",finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),readbackByteIdentical=True)
receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(json.dumps({k:record[k] for k in ["state","package","bytes","sha256","assetId"]},ensure_ascii=False))
