"""Package one actual dual-client manual-followup candidate; never publish it."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
from release_readback import download
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
REPO="Listener-ai-Macau/Companion-Type";TAG="windows-0.1.78-bb1550c4-candidate";receipt=C/"manual-followup-packaged-candidate.json"
def sha(p):
 with Path(p).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def gh(args):
 q=subprocess.run(["gh",*map(str,args)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert q.returncode==0,q.stderr.decode(errors="replace")[-1200:];return q.stdout
if len(sys.argv)>1 and sys.argv[1]=="resume":
 record=json.loads(receipt.read_text());output=Path(record["package"]);assert sha(output)==record["sha256"]
else:
 assert not receipt.exists(),"An immutable group archive already exists; use resume."
 win=json.loads((C/"windows099/windows-verification.json").read_text());runtime=json.loads((C/"windows099/runtime-result.json").read_text());backend=json.loads((C/"windows099/runtime-backend-result.json").read_text());installed=json.loads((C/"windows099/installation.json").read_text());ui=json.loads((C/"windows099/manual-followup-ui.json").read_text())
 apk=json.loads((C/"android136/build-result.json").read_text());phone=json.loads((C/"android136/end-session.json").read_text());visual=json.loads((C/"android136/manual-native-layout.json").read_text());reopen=json.loads((C/"android136/manual-reopened.json").read_text());customer=json.loads((C/"customer-edit136/end-session.json").read_text())
 assert runtime["state"]=="WINDOWS099_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED"
 assert win["sourceCommit"]==runtime["appSourceCommit"]==installed["sourceCommit"]
 assert installed["dataManifestIdentical"] and installed["installedExeSha256"]==win["embeddedExeSha256"] and installed["installedDllSha256"]==win["dllSha256"]
 assert ui["state"]=="ORDINARY_PACKAGED_MANUAL_FOLLOWUP_LITERAL_EVIDENCE_REOPEN_SOURCE_REMOVAL_PASSED"
 assert backend["manualFollowup"]["noteKindChecklistAndLiteralReferencesRestoredExactly"] and backend["manualFollowup"]["selectedTextAndFullJsonEvidencePreserved"] and backend["manualFollowup"]["forgedOrMissingSourceEditRejectedWithoutStateChange"]
 assert phone["ownerOriginalContentByteIdentical"] and phone["ownAppDisplayForwardAndExactTemporaryFilesClosed"] and "PASSED" in visual["state"] and "PASSED" in reopen["state"]
 assert customer["ownedAppDisplayForwardJarClosed"] and customer["onlyOldChangeLibraryIndex"] and customer["allPreviousLibrariesRetained"]
 restored135=json.loads((C/"android135/manual-restore-integrity.json").read_text());exported135=json.loads((C/"android135/manual-export-readback.json").read_text());purged135=json.loads((C/"android135/manual-purge-integrity.json").read_text())
 assert restored135["allBackupContentFilesByteIdentical"]==56 and restored135["originalImageBytesExact"]
 assert exported135["notesExact"] and exported135["referenceCount"]==3 and exported135["originalImageCount"]==2 and exported135["generatedMinutesNotIncluded"]
 assert purged135["sourceAndOwnerLibrariesNotPurged"] and purged135["changedOwnedTargetFiles"]==30 and purged135["allOtherRestoredFilesByteIdentical"]==26
 assert sha(Path(win["msi"]))==win["msiSha256"] and sha(Path(apk["apk"]))==apk["apkSha256"]
 base=Path("E:/CodexData/Companion/deliveries/20261110-companion-fw791-win092-android129-candidate.zip");base_sha="3ac2b03a6e3284d6d1d78b56132deea7f48932c6734a8ec5fd4f2d786e7d9c5e";assert sha(base)==base_sha
 output=base.parent/"20261111-companion-core-windows099-android136.zip";temp=output.with_suffix(".preparing.zip");assert not output.exists() and not temp.exists()
 at=datetime.now().astimezone().isoformat(timespec="seconds");files=[]
 with zipfile.ZipFile(base) as old,zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  prior=json.loads(old.read("delivery.json"));claims={item["path"]:item for item in prior["files"]}
  for name in ["firmware/companion-update.cup","firmware/ota_manifest.json","macos/CompanionMac-candidate.zip"]:
   item=claims[name];digest=hashlib.sha256();size=0
   with old.open(name) as source,z.open(name,"w") as target:
    while raw:=source.read(131072):target.write(raw);digest.update(raw);size+=len(raw)
   assert digest.hexdigest()==item["sha256"] and size==item["bytes"];files.append(item)
  for name,path,digest in [("windows/Companion-Windows-0.1.99.msi",Path(win["msi"]),win["msiSha256"]),("android/Companion-Android-0.1.136.apk",Path(apk["apk"]),apk["apkSha256"])]:
   z.write(path,name);files.append({"path":name,"bytes":path.stat().st_size,"sha256":digest})
  z.writestr("evidence/retained-components-delivery.json",old.read("delivery.json"))
  manifest={"at":at,"state":"COMPANION_HUMAN_FOLLOWUP_LITERAL_EVIDENCE_CORE_CANDIDATE","saleQualified":False,"files":files,
   "windows":{"version":"0.1.99","sourceCommit":win["sourceCommit"],"installedExactNativeVerified":True},
   "android":{"version":"0.1.136","sourceCommit":apk["sourceCommit"],"backendSourceCommit":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedExactApkVerified":True,"unchangedFunctionalNativeBaseline":{"version":"0.1.135","sourceCommit":"71b33214443bb7e66e675ea77151bbd8b721f46e","scope":"Actual literal sources/images,56-file backup/restore, notes-onlyTXT/ZIP, scoped30-file purge.135 visual failure retained,136 actual rendering and restart verified."}},
   "retainedFirmware":prior["firmware"],"retainedMac":prior["macos"],"retainedComponentsRebuiltOrRetestedHere":False,"retainedComponentBatch":{"file":base.name,"sha256":base_sha},"sourceRepository":"https://github.com/Listener-ai-Macau/Companion-Type",
   "scope":"Local human follow-up with literal checklist markers and saved transcript/document/table evidence. Capture preserves manual draft. Identity-bound source return and explicit stale/missing source preserve old excerpts. Full editing, selected exports, backup/restore/lifecycle. Repaired actual native checkbox geometry and duplicate body; original authored line order retained. No model or cloud call.",
   "boundaries":"Private candidate; not public sale approval. Model/real hardware, long recording/power, retained Mac qualification, formal service/signing/channel and actual Owner/customer gates stay separate. AI simulations do not prove real demand or payment."}
  z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n");z.writestr("SHA256SUMS.txt","".join(item["sha256"]+"  "+item["path"]+"\n" for item in files))
  evidence=["windows099/windows-verification.json","windows099/runtime-result.json","windows099/runtime-backend-result.json","windows099/manual-followup-ui.json","windows099/manual-followup-evidence.png","windows099/installation.json","windows099/source-freeze.json","windows099/runtime-source-freeze.json","android136/build-result.json","android136/installation.json","android136/manual-followup.json","android136/manual-speech.json","android136/manual-native-layout.json","android136/manual-native-layout-dark.png","android136/manual-native-layout-light.png","android136/manual-reopened.json","android136/end-session.json","android135/manual-image.json","android135/manual-source-removed.json","android135/manual-process-reopened.json","android135/manual-backup-readback.json","android135/manual-restore-integrity.json","android135/manual-export-readback.json","android135/manual-purge-integrity.json","android135/manual-visual-block.json","android135/manual-followup-evidence.png","android135/end-session.json","manual-followup-android136-result.json","manual-complete-source-checks.json","manual-current-store-checks.json","manual-followup-ui-source-checks.json","manual-layout/result.json","manual-layout/typecheck.json","reference-workspace-delivered-result.json","audio-edit-delivered-result.json","table-reading-delivered-result.json"]
  for name in evidence:z.write(C/name,"evidence/"+name)
  for name in ["customer-presale.md","customer-afteruse.md","customer-presale-dispatch.txt","customer-afteruse-dispatch.txt","end-session.json"]:z.write(C/"customer-edit136"/name,"evidence/customer-edit136/"+name)
  z.writestr("README.txt","Companion 人工跟进与原文依据核心候选\nWindows 0.1.99 / Android 0.1.136\n\n自己的待跟进清单与录音转写、人工文档、表格原行放在一起。先阅读依据再加入备注草稿，不清空已输入的文字；保存后可逐项勾选、编辑、回来接续并查看当前依据。引用保留来源身份、提取版本、原始字面文字和位置。来源更新或移除会明确提示，旧摘录仍保留，不自动匹配其它录音或资料库。\n\n人工跟进和保存时摘录与会议决定/AI结论区分。原录音、转写、纪要保留；清单正文只显示一次，夹在事项间的原说明仍按原顺序显示，编辑与导出保留字面原文。136修复135真实截图中的复选框巨大与正文重复问题，两主题和进程重开在真实App确认。135的原生保存、原图、56文件备份恢复、所选TXT/ZIP与恢复副本精确清理按未变Java/AAR源复用，失败截图和实际版本同时保留，未冒充136重复全测。\n\nWindows匹配MSI已验证普通保存/勾选/重开/来源移除/原文返回、所选文字/JSON、完整备份恢复和仅归属记录清除；覆盖升级前后用户资料校验一致。原098/134资料分区与草稿保留、097/133阅读和搜索、096/132原件/表格、095/131录音编辑功能沿未受影响证据保留。\n\n独立AI模拟者只用全新公开资料副本，旧工程人工备注是辅助条件，完整原话附包；没有真人付款/长期售后证明，也没有本批声音/模型/云AI/真实硬件资格。固件66791和Mac候选保持原字节，不增加其资格。正式服务/签名渠道、模型、实物长录与电源、Owner及真人顾客门仍开放。本包只作私有工程候选，不是公开售卖批准，不含Owner私人录音、原资料索引、令牌或密钥。\n")
 with zipfile.ZipFile(temp) as z:
  assert z.testzip() is None
  for item in files:
   with z.open(item["path"]) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==item["sha256"]
 temp.replace(output);record={"at":at,"state":"MANUAL_FOLLOWUP_COMPLETE_CANDIDATE_LOCAL_VERIFIED","package":str(output),"bytes":output.stat().st_size,"sha256":sha(output),"files":files,"draftOnly":True,"saleQualified":False,"ownerPrivateDataUploaded":False};receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"]
asset=next((item for item in release["assets"] if item["name"]==output.name),None)
if asset is None:
 gh(["release","upload",TAG,output,"--repo",REPO]);release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"];asset=next(item for item in release["assets"] if item["name"]==output.name)
assert asset["digest"]=="sha256:"+record["sha256"];record["assetId"]=int(asset["apiUrl"].rsplit("/",1)[1]);record["readback"]=download(REPO,record["assetId"],output.parent/"readback"/output.name,record["bytes"],record["sha256"])
record.update(state="MANUAL_FOLLOWUP_COMPLETE_CANDIDATE_PRIVATE_DRAFT_FULL_READBACK_IDENTICAL",finishedAt=datetime.now().astimezone().isoformat(timespec="seconds"),readbackByteIdentical=True);receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps({k:record[k] for k in ["state","package","bytes","sha256","assetId"]}))
