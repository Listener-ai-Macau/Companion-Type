"""Package one qualified dual-client edit batch; upload a private draft only."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
from release_readback import download
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
REPO="Listener-ai-Macau/Companion-Type";TAG="windows-0.1.78-bb1550c4-candidate";receipt=C/"audio-edit-packaged-candidate.json"
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def gh(args):
 p=subprocess.run(["gh",*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
 assert p.returncode==0,p.stderr.decode(errors="replace")[-1000:];return p.stdout
if len(sys.argv)>1 and sys.argv[1]=="resume":
 record=json.loads(receipt.read_text(encoding="utf8"));output=Path(record["package"]);assert sha(output)==record["sha256"]
else:
 assert not receipt.exists(),"An immutable package exists; resume instead of overwriting it"
 win=json.loads((C/"windows093/windows-verification.json").read_text(encoding="utf8"))
 runtime=json.loads((C/"windows093/runtime-result.json").read_text(encoding="utf8"))
 installed=json.loads((C/"windows093/installation.json").read_text(encoding="utf8"))
 apk=json.loads((C/"android131/build-result.json").read_text(encoding="utf8"))
 phone=json.loads((C/"android131/end-session.json").read_text(encoding="utf8"))
 assert runtime["state"]=="WINDOWS093_NATIVE_AUDIO_EDIT_COMPLETE_WORKFLOW_PASSED"
 assert win["sourceCommit"]==runtime["appSourceCommit"]==installed["sourceCommit"]
 assert installed["dataManifestIdentical"] and installed["installedExeSha256"]==win["embeddedExeSha256"] and installed["installedDllSha256"]==win["dllSha256"]
 assert phone["ownerOriginalContentByteIdentical"] and phone["ownAppDisplayForwardAndExactTemporaryFilesClosed"]
 assert sha(Path(win["msi"]))==win["msiSha256"] and sha(Path(apk["apk"]))==apk["apkSha256"]
 base=Path("E:/CodexData/Companion/deliveries/20261110-companion-core-windows091-android129.zip")
 base_sha="a86747698f8e868901cbf6b0cc600620f50f3af9357e560ae7a1a00ebf286824";assert sha(base)==base_sha
 output=base.parent/"20261111-companion-core-windows093-android131.zip";temp=output.with_suffix(".preparing.zip")
 assert not output.exists() and not temp.exists()
 at=datetime.now().astimezone().isoformat(timespec="seconds");files=[]
 with zipfile.ZipFile(base) as old,zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  prior=json.loads(old.read("manifest.json"));claims={f["path"]:f for f in prior["files"]}
  for name in ["firmware/companion-update.cup","firmware/ota_manifest.json","macos/CompanionMac-candidate.zip"]:
   item=claims[name];digest=hashlib.sha256();size=0
   with old.open(name) as source,z.open(name,"w") as target:
    while data:=source.read(131072):target.write(data);digest.update(data);size+=len(data)
   assert digest.hexdigest()==item["sha256"] and size==item["bytes"];files.append(item)
  for name,path,digest in [("windows/Companion-Windows-0.1.93.msi",Path(win["msi"]),win["msiSha256"]),("android/Companion-Android-0.1.131.apk",Path(apk["apk"]),apk["apkSha256"])]:
   z.write(path,name);files.append({"path":name,"bytes":path.stat().st_size,"sha256":digest})
  manifest={"at":at,"state":"COMPANION_NON_DESTRUCTIVE_AUDIO_EDIT_CORE_CANDIDATE","saleQualified":False,"files":files,
   "windows":{"version":"0.1.93","sourceCommit":win["sourceCommit"],"installedExactNativeVerified":True},
   "android":{"version":"0.1.131","sourceCommit":apk["sourceCommit"],"backendSourceCommit":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedExactApkVerified":True},
   "retainedFirmware":prior["retainedFirmware"],"retainedMac":prior["retainedMac"],"retainedComponentsRebuiltOrRetestedHere":False,
   "priorSoftwareBatch":{"file":base.name,"sha256":base_sha},"sourceRepository":"https://github.com/Listener-ai-Macau/Companion-Type",
   "scope":"Exact local trim/split/reordered merge, independent result IDs and source maps, original source return, cancel/pending-only retry, actual process-exit recovery, full backup/restore and scoped cleanup. Original models/ASR are unchanged and not run here.",
   "boundaries":"Private candidate, no public release or sale approval. Original real-meeting/model, physical long recording/power, cross-platform/service, release trust/channel and actual customer gates remain open. Prior firmware/Mac bytes are retained candidates, not current physical qualification."}
  z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
  z.writestr("SHA256SUMS.txt","".join(f["sha256"]+"  "+f["path"]+"\n" for f in files))
  evidence=["windows093/windows-verification.json","windows093/runtime-result.json","windows093/runtime-backend-result.json","windows093/installation.json","windows093/source-freeze.json","android131/build-result.json","android131/editing-control-final.json","android131/editing-control-pcm.json","android131/end-session.json","android130/editing-backup-bytes.json","android130/editing-split-merge-pcm.json"]
  for name in evidence:z.write(C/name,"evidence/"+name)
  z.writestr("README.txt","Companion 核心录音编辑验收候选\nWindows 0.1.93 / Android 0.1.131\n\n通过覆盖更新保留原有资料，不卸载、不清数据。详情内可裁剪、按时间切分或重排合并完整本机音频，另存独立录音。成品保留原音范围；旧原件、转写和纪要不变。成品使用16kHz单声道本机格式，不把多场会议当成连续发生。重新转写与AI整理需另行主动操作，本批没有调用模型或云AI。\n\n处理中可停止剩余片段，已保存部分保留；中断后核对任务并只重试未完成片段。完整资料库备份包含原音及来源映射。移入回收站可恢复，永久清除只删除所选记录的归属文件。\n\nmanifest.json 与 evidence/ 记录实际源码、校验和及验收范围。保留的固件仍为前批开发候选，Mac仍为adhoc候选，本轮未重新实物/Mac验收。正式签名/渠道、实际服务、模型与实物长期资格仍沿原任务，本包不是公开售卖批准。不含Owner录音、私人库索引、访问令牌或签名密钥。\n")
 with zipfile.ZipFile(temp) as z:
  assert z.testzip() is None
  for f in files:
   with z.open(f["path"]) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==f["sha256"]
 temp.replace(output);record={"at":at,"state":"AUDIO_EDIT_COMPLETE_CANDIDATE_LOCAL_VERIFIED","package":str(output),"bytes":output.stat().st_size,"sha256":sha(output),"files":files,"draftOnly":True,"saleQualified":False,"ownerPrivateDataUploaded":False};receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"]
asset=next((a for a in release["assets"] if a["name"]==output.name),None)
if asset is None:
 gh(["release","upload",TAG,output,"--repo",REPO]);release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"];asset=next(a for a in release["assets"] if a["name"]==output.name)
assert asset["digest"]=="sha256:"+record["sha256"];record["assetId"]=int(asset["apiUrl"].rsplit("/",1)[1])
record["readback"]=download(REPO,record["assetId"],output.parent/"readback"/output.name,record["bytes"],record["sha256"])
record.update(state="AUDIO_EDIT_COMPLETE_CANDIDATE_PRIVATE_DRAFT_FULL_READBACK_IDENTICAL",finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),readbackByteIdentical=True)
receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(json.dumps({k:record[k] for k in ["state","package","bytes","sha256","assetId"]},ensure_ascii=False))
