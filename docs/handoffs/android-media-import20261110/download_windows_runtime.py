"""Read the successful matched edit run back without rebuilding its MSI."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,zipfile
from release_readback import download
C=Path(__file__).parent;Q=Path("E:/CodexData/Companion/.build-cache/audio-derivation20261110")
code=sys.argv[1];run_id=int(sys.argv[2]);mode=sys.argv[3] if len(sys.argv)>3 else "editing";assert mode in ["editing","documents"] and re.fullmatch(r"\d{3}",code)
O=C/("windows"+code);freeze=json.loads((O/"runtime-source-freeze.json").read_text(encoding="utf8"));v=json.loads((O/"windows-verification.json").read_text(encoding="utf8"))
def gh(args):
 p=subprocess.run(["gh",*args],capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr.decode(errors="replace")[-1000:];return p.stdout
fresh=json.loads(gh(["api","-H","Cache-Control: no-cache","repos/Listener-ai-Macau/Companion-Type/actions/runs/"+str(run_id)]));run={"status":fresh["status"],"conclusion":fresh["conclusion"],"headSha":fresh["head_sha"]}
assert run=={"conclusion":"success","headSha":freeze["sourceCommit"],"status":"completed"},run
listing=json.loads(gh(["api","repos/Listener-ai-Macau/Companion-Type/actions/runs/"+str(run_id)+"/artifacts"]))
asset=next(a for a in listing["artifacts"] if a["name"]=="companion-context-"+freeze["sourceCommit"])
archive=Q/("windows"+code+"-runtime-"+freeze["sourceCommit"][:12]+".zip");proof=download("Listener-ai-Macau/Companion-Type",asset["id"],archive,asset["size_in_bytes"],asset["digest"].removeprefix("sha256:"),kind="artifact")
dest=Q/("windows"+code+"-runtime-"+freeze["sourceCommit"][:12])
if not dest.exists():
 dest.mkdir()
 with zipfile.ZipFile(archive) as z:
  for f in z.infolist():
   assert not f.filename.startswith(("/","\\")) and ":" not in f.filename and ".." not in Path(f.filename).parts and (dest/f.filename).resolve().is_relative_to(dest.resolve())
  z.extractall(dest)
result=json.loads((dest/"result.json").read_text(encoding="utf8"));assert result["state"]=="WINDOWS"+code+("_NATIVE_AUDIO_EDIT_COMPLETE_WORKFLOW_PASSED" if mode=="editing" else "_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED")
assert result["testSourceCommit"]==freeze["sourceCommit"],"Runtime artifact belongs to another verifier source"
assert result["appSourceCommit"]==v["sourceCommit"] and result["exactMsiExeSha256"]==v["embeddedExeSha256"] and result["exactMsiDllSha256"]==v["dllSha256"] and result["frozenNativeBytesMatchedApprovedMsi"]
cases=list((dest/"workflow-evidence").iterdir())
if mode=="documents" and int(code)>=100:
 assert len(cases)==2
 case=next(folder for folder in cases if json.loads((folder/"result.json").read_text(encoding="utf8"))["stage"]=="documents")
 incoming=next(folder for folder in cases if json.loads((folder/"result.json").read_text(encoding="utf8"))["stage"]=="incoming")
 incoming_result=json.loads((incoming/"result.json").read_text(encoding="utf8"));assert incoming_result["state"]=="REAL_NATIVE_OS_INCOMING_FILE_WORKFLOW_PASSED" and incoming_result["ui"]["state"]=="REAL_TAURI_OS_INCOMING_COLD_WARM_CONFIRM_DOCUMENT_IMAGE_RETRY_CANCEL_AND_ORIGINALS_PASSED"
 assert result["incomingNativeExitCode"]==0 and result["incomingCase"]==incoming.name
 for name,target in [("result.json","incoming-case-result.json"),("incoming-ui.json","incoming-ui.json"),("incoming-files-native.png","incoming-files-native.png")]:shutil.copyfile(incoming/name,O/target)
else:
 assert len(cases)==1;case=cases[0]
backend=json.loads((case/("audio-edit-backend/result.json" if mode=="editing" else "document-backend/result.json")).read_text(encoding="utf8"))
if mode=="editing":
 assert backend["state"]=="ACTUAL_PACKAGED_AUDIO_EDIT_PCM_CANCEL_RESTART_PENDING_ONLY_RETRY_BACKUP_RESTORE_AND_SCOPED_PURGE_PASSED"
 assert backend["sourceIdentitySurvivesNewRoot"] and backend["sourceMapSurvivesAudioOnlyCleanup"] and backend["fullPurgeDeletesOnlyChildFiles"] and backend["sourceAndUnrelatedRowsUnchanged"] and backend["cancelRetrySame32Ids"] and backend["crashRetrySame32Ids"]
else:
 assert backend["state"]=="ACTUAL_PACKAGED_DOCUMENT_CONTEXT_BACKUP_RESTORE_TRASH_AND_EXACT_PURGE_PASSED"
 assert backend["sourceOriginalIndexAndAllAttachmentsUnchanged"] and backend["unrelatedRestoredControlPreserved"] and backend["removedEntranceOriginalRetainedUntilFullPurge"] and backend["audioFreeDocumentBackupSupported"] and backend["staleRevisionRejected"]
result["runtimeRun"]=run_id
(O/"runtime-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
shutil.copyfile(case/("audio-edit-backend/result.json" if mode=="editing" else "document-backend/result.json"),O/"runtime-backend-result.json")
names=["audio-edit-dark.png","audio-edit-light.png","audio-edit-ui.json","editing-checkpoints.json"] if mode=="editing" else ["documents-dark.png","documents-light.png","table-reading-dark.png","table-reading-light.png","document-checkpoints.json","preserved-desktop-input.png"]
for name in names:shutil.copyfile(case/name,O/name)
if mode=="documents":
 shutil.copyfile(case/"result.json",O/"document-ui.json")
 if int(code)>=97:
  for name in ["notes-reading-recent.png","notes-reading-created.png","notes-reading-source-search.png","notes-reading-ui.json"]:shutil.copyfile(case/name,O/name)
if mode=="documents" and int(code)>=99:
 manual=json.loads((case/"manual-followup-ui.json").read_text(encoding="utf8"))
 assert manual["state"]=="ORDINARY_PACKAGED_MANUAL_FOLLOWUP_LITERAL_EVIDENCE_REOPEN_SOURCE_REMOVAL_PASSED"
 assert backend["manualFollowup"]["noteKindChecklistAndLiteralReferencesRestoredExactly"] and backend["manualFollowup"]["selectedTextAndFullJsonEvidencePreserved"] and backend["manualFollowup"]["forgedOrMissingSourceEditRejectedWithoutStateChange"]
 for name in ["manual-followup-ui.json","manual-followup-evidence.png"]:shutil.copyfile(case/name,O/name)
(O/"runtime-artifact-readback.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf8")
print(json.dumps({"state":result["state"],"run":run_id,"appSource":v["sourceCommit"],"exactPcmOutputs":backend.get("generatedOutputRows"),"restoredFiles":backend.get("restoreFilesByteIdentical",backend.get("restoredOriginalAndExtractionFilesByteIdentical"))}))
