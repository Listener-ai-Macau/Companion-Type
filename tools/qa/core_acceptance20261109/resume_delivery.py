"""Resume the current whole software delivery from its original backlog.
Status is read-only. --advance runs only the next recorded engineering steps;
it never builds a new product, changes scope or marks a sale gate complete.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys

CORE=("owner_module_execution","frontendWindowsMobile20261102","ownerCoreDeliveryPriority20261104",
      "ownerCoreAcceptanceCandidate20261109")

def get(value,path):
 for key in path.split("."):
  if not isinstance(value,dict) or key not in value:return None
  value=value[key]
 return value

def inside(root,relative):
 path=(root/relative).resolve()
 if not path.is_relative_to(root.resolve()):raise ValueError("Path leaves the declared delivery evidence directory")
 return path

def load(path):
 return json.loads(path.read_text(encoding="utf-8"))

def verify_step(root,step):
 path=inside(root,step["receipt"])
 if not path.is_file():return False,"receipt missing"
 value=load(path)
 for field,expected in step["equals"].items():
  if get(value,field)!=expected:return False,"receipt differs: "+field
 if "binary" in step:
  binary=step["binary"];target=Path(get(value,binary["pathField"]));expected=get(value,binary["shaField"])
  if not target.is_file():return False,"matched binary missing"
  with target.open("rb") as stream:actual=hashlib.file_digest(stream,"sha256").hexdigest()
  if actual!=expected:return False,"matched binary bytes differ"
 return True,"verified"

def observe_job(root,job,query):
 path=inside(root,job["freeze"])
 if not path.is_file():return {"kind":"ENGINEERING_ACTION","action":job["prepare"]}
 frozen=load(path);handle=frozen.get(job["runField"])
 if not handle:return {"kind":"ENGINEERING_ACTION","action":job["prepare"]}
 run=query(handle)
 if run["head_sha"]!=frozen["sourceCommit"]:return {"kind":"FAILED","action":"Resolve run/source mismatch; preserve the existing run","run":handle}
 if run["status"]!="completed":return {"kind":"VERIFIED_WAIT","run":handle,"status":run["status"],"sourceCommit":frozen["sourceCommit"]}
 if run["conclusion"]!="success":return {"kind":"FAILED","run":handle,"conclusion":run["conclusion"],"action":"Inspect retained failure before retrying; do not start a replacement from a polling timeout"}
 return {"kind":"PASSED","run":handle}

def current(root,config,query):
 passed=[]
 for step in config["steps"]:
  if "job" in step:
   status=observe_job(root,step["job"],query)
   if status["kind"]!="PASSED":return {**status,"step":step["id"],"passed":passed}
  if "receipt" not in step:
   passed.append(step["id"]);continue
  ok,reason=verify_step(root,step)
  if ok:passed.append(step["id"]);continue
  # A mismatched existing receipt is evidence to investigate, never overwrite
  # it by automatically rerunning an installation or packaging operation.
  if inside(root,step["receipt"]).exists():return {"kind":"FAILED","step":step["id"],"reason":reason,"passed":passed,"action":"Inspect the existing receipt and preserve it before deciding a retry"}
  return {"kind":"READY","step":step["id"],"command":step["command"],"passed":passed}
 return {"kind":"BATCH_DELIVERED","passed":passed,"action":config["afterDelivery"],"wholeGoalComplete":False}

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--project-root",type=Path,required=True)
 parser.add_argument("--advance",action="store_true")
 args=parser.parse_args();project=args.project_root.resolve()
 data=load(project/"docs/product_backlog.json")
 for key in CORE:data=data[key]
 point=data["next"].split(".")
 if point[0]==CORE[-1]:point=point[1:]
 config=get(data,".".join(point)+".deliveryExecution")
 if not config:raise RuntimeError("The original next work item has no frozen delivery execution yet; continue that engineering item, do not resume a retired batch")
 root=inside(project,config["evidenceRoot"])
 def query(handle):
  response=subprocess.run(["gh","api","-H","Cache-Control: no-cache","repos/Listener-ai-Macau/Companion-Type/actions/runs/"+str(int(handle))],capture_output=True,timeout=40)
  if response.returncode:raise RuntimeError("Run observation unavailable; preserve the same handle and re-observe, do not restart")
  return json.loads(response.stdout)
 attempted=set()
 if args.advance:
  sys.path.insert(0,str(project/"model-research/src"))
  from moss_windows_resource_limits_20261104 import WorkerLimits
  limits=WorkerLimits(10,768*1024**2)
 while True:
  state=current(root,config,query)
  print(json.dumps({"userResult":config["userResult"],**state},ensure_ascii=False),flush=True)
  if not args.advance or state["kind"]!="READY":return
  if state["step"] in attempted:raise RuntimeError("Step did not create matching evidence; preserve logs before retrying")
  attempted.add(state["step"]);command=state["command"]
  script=inside(root,command[0]);assert script.suffix==".py" and script.is_file()
  log=inside(root,config["logDirectory"])/("delivery-"+state["step"]+".log")
  # Append attempts to the existing batch log; never truncate a previous failure.
  with log.open("ab") as stream:
   arguments=[]
   for item in command[1:]:
    if isinstance(item,dict):arguments.append(str(get(load(inside(root,item["receipt"])),item["field"])))
    else:arguments.append(item)
   result=subprocess.run([sys.executable,str(script),*arguments],cwd=root,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
  if result.returncode:raise RuntimeError("Delivery step failed: "+state["step"]+"; retained log: "+str(log))
if __name__=="__main__":main()
