"""Package the complete, matched incoming-file lifecycle candidate; private draft only."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
from release_readback import download
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
REPO="Listener-ai-Macau/Companion-Type";TAG="windows-0.1.78-bb1550c4-candidate";receipt=C/"incoming-lifecycle-packaged-candidate.json"
def sha(p):
 with Path(p).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def gh(args):
 q=subprocess.run(["gh",*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert q.returncode==0,q.stderr.decode(errors="replace")[-1200:];return q.stdout
if len(sys.argv)>1 and sys.argv[1]=="resume":
 record=json.loads(receipt.read_text());output=Path(record["package"]);assert sha(output)==record["sha256"]
else:
 assert not receipt.exists(),"An immutable group archive already exists; use resume."
 win=json.loads((C/"windows105/windows-verification.json").read_text());runtime=json.loads((C/"windows105/runtime-result.json").read_text());backend=json.loads((C/"windows105/runtime-backend-result.json").read_text());installed=json.loads((C/"windows105/installation.json").read_text());incoming=json.loads((C/"windows105/incoming-ui.json").read_text())
 apk=json.loads((C/"android139/build-result.json").read_text());phone=json.loads((C/"android139/end-session.json").read_text());phone_install=json.loads((C/"android139/installation.json").read_text());restore=json.loads((C/"android139/incoming-restore-integrity.json").read_text());purge=json.loads((C/"android139/incoming-purge-source-integrity.json").read_text());reopen=json.loads((C/"android139/incoming-restarted.json").read_text())
 assert runtime["state"]=="WINDOWS105_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED"
 assert incoming["state"]=="REAL_TAURI_OS_INCOMING_COLD_WARM_CONFIRM_DOCUMENT_IMAGE_RETRY_CANCEL_AND_ORIGINALS_PASSED"
 assert win["sourceCommit"]==runtime["appSourceCommit"]==installed["sourceCommit"]
 assert installed["dataManifestIdentical"] and installed["installedExeSha256"]==win["embeddedExeSha256"] and installed["installedDllSha256"]==win["dllSha256"]
 assert backend["state"]=="ACTUAL_PACKAGED_DOCUMENT_CONTEXT_BACKUP_RESTORE_TRASH_AND_EXACT_PURGE_PASSED"
 assert phone_install["apkSha256"]==apk["apkSha256"] and phone_install["sourceCommit"]==apk["sourceCommit"] and phone_install["version"]==139 and phone_install["existingFilesByteIdentical"]==4865
 assert phone["actualVersion"]=="0.1.139" and phone["onlyOldChangeLibraryIndex"] and phone["preexistingFilesByteIdentical"]==phone["preexistingFiles"]-1
 assert phone["ownedAppDisplayForwardJarClosed"] and phone["allPreviousLibrariesRetained"] and not phone["ownerMainDisplayOperated"]
 assert restore["restoredContentFiles"]==63 and restore["sourceFilesUnchanged"]==63 and restore["fiveSourceApplicationOriginalsUnchanged"]
 assert purge["changedOwnedFiles"]==7 and purge["unrelatedPreviousContentFilesUnchanged"]==56 and reopen["deletedRecordNotResurrected"]
 assert sha(Path(win["msi"]))==win["msiSha256"] and sha(Path(apk["apk"]))==apk["apkSha256"]
 base=Path("E:/CodexData/Companion/deliveries/20261110-companion-fw791-win092-android129-candidate.zip");base_sha="3ac2b03a6e3284d6d1d78b56132deea7f48932c6734a8ec5fd4f2d786e7d9c5e";assert sha(base)==base_sha
 output=base.parent/"20261111-companion-core-windows105-android139.zip";temp=output.with_suffix(".preparing.zip");assert not output.exists() and not temp.exists()
 at=datetime.now().astimezone().isoformat(timespec="seconds");files=[]
 with zipfile.ZipFile(base) as old,zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  prior=json.loads(old.read("delivery.json"));claims={item["path"]:item for item in prior["files"]}
  for name in ["firmware/companion-update.cup","firmware/ota_manifest.json","macos/CompanionMac-candidate.zip"]:
   item=claims[name];digest=hashlib.sha256();size=0
   with old.open(name) as source,z.open(name,"w") as target:
    while raw:=source.read(131072):target.write(raw);digest.update(raw);size+=len(raw)
   assert digest.hexdigest()==item["sha256"] and size==item["bytes"];files.append(item)
  for name,path,digest in [("windows/Companion-Windows-0.1.105.msi",Path(win["msi"]),win["msiSha256"]),("android/Companion-Android-0.1.139.apk",Path(apk["apk"]),apk["apkSha256"])]:
   z.write(path,name);files.append({"path":name,"bytes":path.stat().st_size,"sha256":digest})
  z.writestr("evidence/retained-components-delivery.json",old.read("delivery.json"))
  manifest={"at":at,"state":"COMPANION_INCOMING_FILE_LIFECYCLE_CORE_CANDIDATE","saleQualified":False,"files":files,
   "windows":{"version":"0.1.105","sourceCommit":win["sourceCommit"],"installedExactNativeVerified":True,"includesCardFirstSource":"16c2738d22d236c2223c979953e3cd0d33f06793","cardAutomaticAsrHardwareQualifiedHere":False},
   "android":{"version":"0.1.139","sourceCommit":apk["sourceCommit"],"backendSourceCommit":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedExactApkVerified":True,"nativeBackendModelsAndDecoderChanged":False},
   "retainedFirmware":prior["firmware"],"retainedMac":prior["macos"],"retainedComponentsRebuiltOrRetestedHere":False,"retainedComponentBatch":{"file":base.name,"sha256":base_sha},"sourceRepository":"https://github.com/Listener-ai-Macau/Companion-Type",
   "scope":"Ordinary OS incoming audio/document/image flow, explicit save/target, original bytes, source-expiry/regrant/retry, invalid media, actual generated two-hour PCM cancel, durable terminal reason, scoped record/receipt purge, dismissal and process reopen. Actual ordinary backup/restore and retained manual/source reading. Incoming mutable Windows receipt snapshots reuse established bounded publication; real transient and persistent reader regressions included.",
   "retainedCore":"Windows099/Android136 notes, reference panes, reading/search, selected exports, non-destructive editing and corresponding previous qualification remain traceable through the original delivered receipts; no claim of repeating unchanged scopes.",
   "customerReview":"Previous136 independent AI simulated presale/after-use feedback retained; next new review follows the coherent complete meeting-detail visual batch. No real demand/payment or new customer qualification claimed here.",
   "boundaries":"Private software candidate only. No new model training/ASR/cloud/microphone/board run in this batch. Source integration of104 automatic local-only card processing and first-use UI is not physical end-to-end ASR qualification. Model accuracy, complex meetings, long recording/power, retained Mac, formal service/signing/channel and Owner/real-customer gates remain separate."}
  z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n");z.writestr("SHA256SUMS.txt","".join(item["sha256"]+"  "+item["path"]+"\n" for item in files))
  evidence=["windows105/windows-verification.json","windows105/runtime-result.json","windows105/runtime-backend-result.json","windows105/incoming-ui.json","windows105/incoming-case-result.json","windows105/incoming-files-native.png","windows105/installation.json","windows105/source-freeze.json","windows105/runtime-source-freeze.json","windows105/remote-candidate-backup.json","windows103/runtime-attempt1-decision.json","android139/build-result.json","android139/installation.json","android139/source-freeze.json","android139/remote-candidate-backup.json","android139/incoming-document-expired.json","android139/ordinary-files-warm-reshare.json","android139/incoming-document-retried.json","android139/incoming-bad.json","android139/incoming-long-cancel.json","android139/incoming-terminal-reasons.json","android139/incoming-backup-readback.json","android139/incoming-restore-integrity.json","android139/incoming-purge-restored-integrity.json","android139/incoming-purge-source-integrity.json","android139/incoming-dismissed.json","android139/incoming-restarted.json","android139/incoming-original-returned.json","android139/end-session.json","android139/public-backup-remote.json","manual-followup-delivered-result.json","reference-workspace-delivered-result.json","audio-edit-delivered-result.json","table-reading-delivered-result.json"]
  for name in evidence:z.write(C/name,"evidence/"+name)
  z.writestr("README.txt","Companion 双端外部文件接收完整核心候选\nWindows 0.1.105 / Android 0.1.139\n\n从系统文件或其它应用分享音频、文档和图片进入应用，确认后保存到新录音或指定会议。原件与来源保留；权限失效可在重新分享后沿原目标重试；取消和坏文件各自保留原因。清理接收记录不会误删已保存的录音。会议精确清除仅回收当前资料库归属内容及绑定接收记录，恢复副本不会误清原库。备份恢复、重开和原有资料保护已有对应实际结果。两小时用例为公开生成PCM的取消验证，不是两小时真实会议或转写质量证明。\n\nWindows105同时保留最新实体录音卡优先引导、全新卡录音的本地自动处理策略与功能说明。它们的源码/原生检查与本批普通文件接收资格分开；本批未操作板卡、录音、运行模型或调用云服务，不能据此宣称自动卡录音整链已验。\n\n前批人工跟进、原文依据、文档/表格、图文备注、分类搜索、内容导出和无损原件保护沿未受影响的原收据保留。整体视觉仍待集中打磨，当前候选不代表高级感或全产品售卖资格通过。原模型质量、实物长录/供电、正式签名与渠道、账号服务/费用和Owner/真人客户门保留。固件66791和Mac候选仅复用原字节，不新增资格。\n\n仅私有工程候选；不含Owner私人录音、原资料索引、令牌或密钥。\n")
 with zipfile.ZipFile(temp) as z:
  assert z.testzip() is None
  for item in files:
   with z.open(item["path"]) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==item["sha256"]
 temp.replace(output);record={"at":at,"state":"INCOMING_LIFECYCLE_COMPLETE_CANDIDATE_LOCAL_VERIFIED","package":str(output),"bytes":output.stat().st_size,"sha256":sha(output),"files":files,"draftOnly":True,"saleQualified":False,"ownerPrivateDataUploaded":False};receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"]
asset=next((item for item in release["assets"] if item["name"]==output.name),None)
if asset is None:
 gh(["release","upload",TAG,output,"--repo",REPO]);release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"];asset=next(item for item in release["assets"] if item["name"]==output.name)
assert asset["digest"]=="sha256:"+record["sha256"];record["assetId"]=int(asset["apiUrl"].rsplit("/",1)[1]);record["readback"]=download(REPO,record["assetId"],output.parent/"readback"/output.name,record["bytes"],record["sha256"])
record.update(state="INCOMING_LIFECYCLE_COMPLETE_CANDIDATE_PRIVATE_DRAFT_FULL_READBACK_IDENTICAL",finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),readbackByteIdentical=True);receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({k:record[k] for k in ["state","package","bytes","sha256","assetId"]}))
