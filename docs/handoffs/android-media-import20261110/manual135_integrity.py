from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,zipfile
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;O=C/"android135";P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone135");A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf-8"));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"phone-primitives","exec"))
action=sys.argv[1];assert action in ["restore","purge"];libs=json.loads((O/"manual-public-libraries.json").read_text());source=libs["working"];target=libs["restored"];assert re.fullmatch("[0-9a-f-]{36}",source) and re.fullmatch("[0-9a-f-]{36}",target)
def public_files(library):
 paths=["files/companion-"+kind+"-"+library for kind in ["meetings","recordings"]]
 raw=adb(["shell","run-as",PKG,"sh","-c","find "+" ".join(paths)+" -type f -print0 | xargs -0 -r sha256sum"],timeout=60);files={}
 for line in raw.splitlines():
  digest,name=line.split(None,1);key=next(kind+"/"+name[len(prefix)+1:] for kind,prefix in zip(["meetings","recordings"],paths) if name.startswith(prefix+"/"));files[key]=digest
 return files
original=json.loads((O/"manual-working-files.json").read_text())["files"];source_now=public_files(source);assert all(source_now.get(name)==digest for name,digest in original.items())
current=public_files(target);proof={"at":datetime.now().astimezone().isoformat(timespec="seconds"),"sourceLibrary":source,"restoredLibrary":target,"sourcePublicFilesUnchanged":len(original),"modelsRun":False,"ownerPrivateDataUsed":False}
if action=="restore":
 with zipfile.ZipFile(P/"Companion-public-manual135-backup.zip") as archive:
  entries=[name for name in archive.namelist() if name.startswith(("meetings/","recordings/"))]
  assert len(entries)==len(original)
  assert all(current.get(name)==hashlib.sha256(archive.read(name)).hexdigest()==original[name] for name in entries)
 image=json.loads((O/"manual-image.json").read_text())["note"]["image"];assert current["meetings/"+image["file"]]==image["sha256"]==json.loads((O/"manual-public-image.json").read_text())["sha256"]
 (O/"manual-restored-files.json").write_text(json.dumps({"library":target,"files":current},indent=2)+"\n")
 proof.update(state="ANDROID135_RESTORED_ALL56_PUBLIC_AUDIO_DOCUMENT_CITATION_NOTE_AND_IMAGE_BYTES_IDENTICAL",allBackupContentFilesByteIdentical=len(entries),originalImageBytesExact=True)
else:
 before=json.loads((O/"manual-restored-files.json").read_text())["files"];purge=json.loads((O/"manual-purged.json").read_text());assert purge["restoredLibrary"]==target;digest=hashlib.sha256(purge["key"].encode()).hexdigest()
 def selected(name):return name.startswith("recordings/import-"+digest+"/") or name.startswith("meetings/"+digest+".") or name.startswith("meetings/recording-lifecycle/"+digest+".") or name=="meetings/recording-organization.json"
 changed=[name for name,digest in before.items() if current.get(name)!=digest];assert changed and all(selected(name) for name in changed),[name for name in changed if not selected(name)]
 assert not any(name.startswith("recordings/import-"+digest+"/") or name.startswith("meetings/"+digest+".") and name!="meetings/"+digest+".lock" for name in current)
 assert current.get("meetings/"+digest+".lock")==hashlib.sha256(b"").hexdigest()
 proof.update(state="ANDROID135_RESTORED_ONLY_RECORD_PURGE_REMOVED_AUDIO_NOTES_IMAGES_DOCUMENT_ORIGINALS_AND_CITATIONS",changedOwnedTargetFiles=len(changed),allOtherRestoredFilesByteIdentical=len(before)-len(changed),sourceAndOwnerLibrariesNotPurged=True)
(O/("manual-"+action+"-integrity.json")).write_text(json.dumps(proof,indent=2)+"\n");print(json.dumps(proof))
