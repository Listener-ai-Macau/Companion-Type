"""Read the successful matched edit run back without rebuilding its MSI."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys,zipfile
from release_readback import download
C=Path(__file__).parent;Q=Path("E:/CodexData/Companion/.build-cache/audio-derivation20261110")
code=sys.argv[1];run_id=int(sys.argv[2]);mode=sys.argv[3] if len(sys.argv)>3 else "editing";assert mode in ["editing","documents"] and re.fullmatch(r"\d{3}",code)
O=C/("windows"+code);freeze=json.loads((O/"runtime-source-freeze.json").read_text(encoding="utf8"));v=json.loads((O/"windows-verification.json").read_text(encoding="utf8"))
def gh(args):
 p=subprocess.run(["gh",*args],capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr.decode(errors="replace")[-1000:];return p.stdout
run=json.loads(gh(["run","view",str(run_id),"--repo","Listener-ai-Macau/Companion-Type","--json","status,conclusion,headSha"]))
assert run=={"conclusion":"success","headSha":freeze["sourceCommit"],"status":"completed"},run
listing=json.loads(gh(["api","repos/Listener-ai-Macau/Companion-Type/actions/runs/"+str(run_id)+"/artifacts"]))
asset=next(a for a in listing["artifacts"] if a["name"]=="companion-context-"+freeze["sourceCommit"])
archive=Q/("windows"+code+"-runtime.zip");proof=download("Listener-ai-Macau/Companion-Type",asset["id"],archive,asset["size_in_bytes"],asset["digest"].removeprefix("sha256:"),kind="artifact")
dest=Q/("windows"+code+"-runtime")
if not dest.exists():
 dest.mkdir()
 with zipfile.ZipFile(archive) as z:
  for f in z.infolist():
   assert not f.filename.startswith(("/","\\")) and ":" not in f.filename and ".." not in Path(f.filename).parts and (dest/f.filename).resolve().is_relative_to(dest.resolve())
  z.extractall(dest)
result=json.loads((dest/"result.json").read_text(encoding="utf8"));assert result["state"]=="WINDOWS"+code+("_NATIVE_AUDIO_EDIT_COMPLETE_WORKFLOW_PASSED" if mode=="editing" else "_NATIVE_DOCUMENT_CONTEXT_UI_BACKUP_RESTORE_AND_EXACT_PURGE_PASSED")
assert result["appSourceCommit"]==v["sourceCommit"] and result["exactMsiExeSha256"]==v["embeddedExeSha256"] and result["exactMsiDllSha256"]==v["dllSha256"] and result["frozenNativeBytesMatchedApprovedMsi"]
cases=list((dest/"workflow-evidence").iterdir());assert len(cases)==1;case=cases[0]
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
(O/"runtime-artifact-readback.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf8")
print(json.dumps({"state":result["state"],"run":run_id,"appSource":v["sourceCommit"],"exactPcmOutputs":backend.get("generatedOutputRows"),"restoredFiles":backend.get("restoreFilesByteIdentical",backend.get("restoredOriginalAndExtractionFilesByteIdentical"))}))
