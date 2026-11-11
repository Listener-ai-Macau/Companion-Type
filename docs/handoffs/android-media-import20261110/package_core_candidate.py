"""Package the current whole delivery recipe from the original task.
Previous fixed127 recipe is preserved in Git (sha256 d7a31f242b54a9ac3065e79bedabc932a3d6c2940dd198b1f7b2dfd8ded2b9cf).
No public release, source relabelling or Owner-data collection occurs here.
"""
from pathlib import Path
from datetime import datetime
import argparse,copy,hashlib,importlib.util,json,os,re,subprocess,sys,zipfile
from release_readback import download
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
REPO="Listener-ai-Macau/Companion-Type";TAG="windows-0.1.78-bb1550c4-candidate"
def sha(p):
 with Path(p).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def now():return datetime.now().astimezone().isoformat(timespec="seconds")
def gh(args):
 q=subprocess.run(["gh",*map(str,args)],capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
 if q.returncode:raise RuntimeError(q.stderr.decode(errors="replace")[-1200:])
 return q.stdout
def local(relative):
 p=(C/relative).resolve()
 if not p.is_relative_to(C.resolve()) or not p.is_file():raise ValueError("Missing evidence inside this declared delivery: "+relative)
 return p
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--current",action="store_true",required=True);args=parser.parse_args()
 sys.path.insert(0,str(R/"model-research/src"))
 from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(10,512*1024**2)
 module_path=R/"companion-device-closure055/tools/qa/core_acceptance20261109/resume_delivery.py"
 spec=importlib.util.spec_from_file_location("current_delivery",module_path);workflow=importlib.util.module_from_spec(spec);spec.loader.exec_module(workflow)
 config,work=workflow.active_execution(load(R/"docs/product_backlog.json"));assert config
 recipe=work["packageDefinition"];receipt=C/recipe["receipt"];assert receipt.resolve().parent==C.resolve()
 gates=copy.deepcopy(config);assert gates["steps"][-1]["id"]=="complete-private-package";gates["steps"]=gates["steps"][:-1]
 def query(handle):return json.loads(gh(["api","-H","Cache-Control: no-cache","repos/"+REPO+"/actions/runs/"+str(int(handle))]))
 status=workflow.current(C,gates,query)
 if status["kind"]!="BATCH_DELIVERED":raise RuntimeError("Whole delivery is not ready for packaging: "+json.dumps(status,ensure_ascii=False))
 assert re.fullmatch(r"[A-Za-z0-9._-]+\.zip",recipe["outputName"])
 output=Path("E:/CodexData/Companion/deliveries")/recipe["outputName"]
 if receipt.exists():
  record=load(receipt);assert Path(record["package"])==output and sha(output)==record["sha256"]
 else:
  assert not output.exists(),"Never replace an immutable existing delivery"
  temp=output.with_suffix(".preparing.zip");assert not temp.exists(),"Retain partial archive before deciding a retry"
  win=load(local(recipe["windows"]["verification"]));installed=load(local(recipe["windows"]["installation"]));runtime=load(local(recipe["windows"]["runtime"]))
  android=load(local(recipe["android"]["build"]));phone_install=load(local(recipe["android"]["installation"]));closed=load(local(recipe["android"]["closed"]))
  assert win["sourceCommit"]==installed["sourceCommit"]==runtime["appSourceCommit"]
  assert installed["installedExeSha256"]==win["embeddedExeSha256"] and installed["installedDllSha256"]==win["dllSha256"] and installed["dataManifestIdentical"]
  assert android["sourceCommit"]==phone_install["sourceCommit"] and android["apkSha256"]==phone_install["apkSha256"] and closed["ownedAppDisplayForwardJarClosed"] and closed["onlyOldChangeLibraryIndex"]
  clients=[(recipe["windows"]["archivePath"],Path(win["msi"]),win["msiSha256"]),(recipe["android"]["archivePath"],Path(android["apk"]),android["apkSha256"])]
  for name,file,digest in clients:assert file.resolve().is_relative_to(C.resolve()) and sha(file)==digest
  base=Path(recipe["baseArchive"]).resolve();assert base.is_relative_to(output.parent.resolve()) and sha(base)==recipe["baseSha256"]
  evidence=list(recipe["evidence"])
  for rule in recipe.get("evidenceGlobs",[]):
   directory=(C/rule["directory"]).resolve();assert directory.is_relative_to(C.resolve())
   for pattern in rule["patterns"]:evidence.extend(p.relative_to(C).as_posix() for p in directory.glob(pattern) if p.is_file())
  evidence=sorted(set(evidence));paths=[local(name) for name in evidence]
  files=[];at=now()
  with zipfile.ZipFile(base) as previous,zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
   old=load_manifest(previous);claims={row["path"]:row for row in old["files"]}
   for name in ["firmware/companion-update.cup","firmware/ota_manifest.json","macos/CompanionMac-candidate.zip"]:
    item=claims[name];digest=hashlib.sha256();size=0
    with previous.open(name) as source,z.open(name,"w") as target:
     while chunk:=source.read(131072):target.write(chunk);digest.update(chunk);size+=len(chunk)
    assert size==item["bytes"] and digest.hexdigest()==item["sha256"];files.append(item)
   for name,file,digest in clients:z.write(file,name);files.append({"path":name,"bytes":file.stat().st_size,"sha256":digest})
   manifest={"at":at,"state":recipe["manifestState"],"userResult":config["userResult"],"saleQualified":False,"files":files,
    "windows":{"version":win["version"],"sourceCommit":win["sourceCommit"],"actualMsiNativeAndUpgradeVerified":True},
    "android":{"version":closed["actualVersion"],"sourceCommit":android["sourceCommit"],"actualApkAndDeclaredUiVerified":True},
    "retainedFirmware":old.get("retainedFirmware",old.get("firmware")),"retainedMac":old.get("retainedMac",old.get("macos")),
    "retainedComponentsRebuiltOrRetestedHere":False,"baseArchive":{"file":base.name,"sha256":recipe["baseSha256"]},
    "scope":recipe["scope"],"boundaries":recipe["boundaries"],"modelsRun":False,"sourceRepository":"https://github.com/"+REPO}
   z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n");z.writestr("SHA256SUMS.txt","".join(item["sha256"]+"  "+item["path"]+"\n" for item in files))
   z.writestr("evidence/retained-core-manifest.json",json.dumps(old,ensure_ascii=False,indent=2)+"\n")
   for name,p in zip(evidence,paths):z.write(p,"evidence/"+name)
   z.writestr("README.txt",recipe["readme"])
  with zipfile.ZipFile(temp) as z:
   assert z.testzip() is None
   for item in files:
    with z.open(item["path"]) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==item["sha256"]
  temp.replace(output);record={"at":at,"state":recipe["statePrefix"]+"_LOCAL_VERIFIED","package":str(output),"bytes":output.stat().st_size,"sha256":sha(output),"files":files,"draftOnly":True,"saleQualified":False,"ownerPrivateDataUploaded":False,"sourceRecipe":"original active work item packageDefinition"};save(receipt,record)
 release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"]
 asset=next((item for item in release["assets"] if item["name"]==output.name),None)
 if asset is None:
  gh(["release","upload",TAG,output,"--repo",REPO]);release=json.loads(gh(["release","view",TAG,"--repo",REPO,"--json","isDraft,assets"]));assert release["isDraft"];asset=next(item for item in release["assets"] if item["name"]==output.name)
 assert asset["digest"]=="sha256:"+record["sha256"]
 record["assetId"]=int(asset["apiUrl"].rsplit("/",1)[1]);save(receipt,record)
 record["readback"]=download(REPO,record["assetId"],output.parent/"readback"/output.name,record["bytes"],record["sha256"])
 record.update(state=recipe["statePrefix"]+"_PRIVATE_DRAFT_FULL_READBACK_IDENTICAL",readbackByteIdentical=True,finishedAt=now(),resourceLimits=limits.query());save(receipt,record)
 print(json.dumps({key:record[key] for key in ["state","package","bytes","sha256","assetId"]}))
def load_manifest(archive):
 name="manifest.json" if "manifest.json" in archive.namelist() else "delivery.json"
 return json.loads(archive.read(name))
if __name__=="__main__":main()
