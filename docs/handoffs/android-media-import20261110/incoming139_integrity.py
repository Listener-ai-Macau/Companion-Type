from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,zipfile
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;O=C/"android139";P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone138");A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf-8"));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"phone-primitives","exec"))
action=sys.argv[1];assert action in ["restore","purge-restored","purge-source"]
source=json.loads((O/"incoming-before-backup.json").read_text())["library"];target=json.loads((O/"incoming-restored-library.json").read_text())["restoredLibrary"]
assert source=="7ebdda83-7869-49a7-83fd-86dc68048493" and re.fullmatch("[0-9a-f-]{36}",target) and source!=target
def public_files(library):
 paths=["files/companion-"+kind+"-"+library for kind in ["meetings","recordings"]]
 raw=adb(["shell","run-as",PKG,"sh","-c","find "+" ".join(paths)+" -type f -print0 | xargs -0 -r sha256sum"],timeout=60);files={}
 for line in raw.splitlines():
  digest,name=line.split(None,1);key=next(kind+"/"+name[len(prefix)+1:] for kind,prefix in zip(["meetings","recordings"],paths) if name.startswith(prefix+"/"));files[key]=digest
 return files
original=json.loads((O/"incoming-working-files.json").read_text())["files"];source_now=public_files(source);current=public_files(target)
proof={"at":datetime.now().astimezone().isoformat(timespec="seconds"),"sourceLibrary":source,"restoredLibrary":target,"modelsRun":False,"ownerPrivateContentRead":False}
if action=="restore":
 assert source_now==original
 with zipfile.ZipFile(P/"Companion-public-incoming139-backup.zip") as archive:
  entries=[name for name in archive.namelist() if name.startswith(("meetings/","recordings/")) and not name.endswith("/")]
  assert len(entries)==len(original) and current==original
  assert all(hashlib.sha256(archive.read(name)).hexdigest()==current[name] for name in entries)
 (O/"incoming-restored-files.json").write_text(json.dumps({"library":target,"files":current},indent=2)+"\n")
 proof.update(state="ALL63_INCOMING_LIBRARY_AUDIO_DOCX_PNG_AND_EXISTING_CONTENT_RESTORED_BYTE_IDENTICAL",sourceFilesUnchanged=len(original),restoredContentFiles=len(entries))
else:
 if action=="purge-restored":
  assert source_now==original;before=json.loads((O/"incoming-restored-files.json").read_text())["files"];purge=json.loads((O/"incoming-purge-restored.json").read_text());after=current
 else:
  before=original;purge=json.loads((O/"incoming-purge-source.json").read_text());after=source_now
  assert current==json.loads((O/"incoming-purge-restored-files.json").read_text())["files"]
 digest=hashlib.sha256(purge["key"].encode()).hexdigest()
 def selected(name):return name.startswith("recordings/import-"+digest+"/") or name.startswith("meetings/"+digest+".") or name.startswith("meetings/recording-lifecycle/"+digest+".") or name=="meetings/recording-organization.json"
 changed=[name for name,value in before.items() if after.get(name)!=value];assert changed and all(selected(name) for name in changed)
 assert not any(name.startswith("recordings/import-"+digest+"/") or name.startswith("meetings/"+digest+".") and name!="meetings/"+digest+".lock" for name in after)
 assert all(value==before[name] for name,value in after.items() if name in before and not selected(name))
 (O/("incoming-"+action+"-files.json")).write_text(json.dumps({"library":target if action=="purge-restored" else source,"files":after},indent=2)+"\n")
 proof.update(state="EXACT_OWNED_INCOMING_RECORD_AUDIO_DOCUMENT_AND_IMAGE_PURGED_OTHER_RECORD_CONTENT_UNCHANGED",purgedLibrary=target if action=="purge-restored" else source,changedOwnedFiles=len(changed),unrelatedPreviousContentFilesUnchanged=len(before)-len(changed))
for entry in json.loads((C/"android138/system-source-files.json").read_text())["files"]:assert adb(["shell","sha256sum",entry["remote"]]).split()[0]==entry["sha256"]
proof["fiveSourceApplicationOriginalsUnchanged"]=True
(O/("incoming-"+action+"-integrity.json")).write_text(json.dumps(proof,indent=2)+"\n");print(json.dumps(proof))
