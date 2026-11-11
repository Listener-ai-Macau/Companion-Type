from pathlib import Path
import json,hashlib,sys,ast
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");S=R/"companion-device-closure055";C=Path(__file__).parent;O=C/"windows100"
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2)
native=json.loads((O/"build-attempt2-result.json").read_text());spec=json.loads((O/"repackage-spec.json").read_text());change=spec["packagingChange"];matched=[];bad=[]
for row in native["sourceFiles"]:
 raw=(S/row["path"]).read_bytes();variants=[raw,raw.replace(b"\r\n",b"\n"),raw.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")];hashes=[hashlib.sha256(v).hexdigest() for v in variants]
 expected=change["newSha256"] if row["path"]==change["path"] else row["sha256"]
 if row["path"]==change["path"]:assert row["sha256"]==change["oldSha256"]
 (matched if expected in hashes else bad).append(row["path"])
for name in ["tools/bundle_windows_candidate_ci.py","tools/build_windows_candidate_ci.py","tools/qa/core_acceptance20261109/run_ci.py","tools/qa/core_acceptance20261109/windows_meeting.py"]:ast.parse((S/name).read_text(encoding="utf-8"))
record={"state":"EXACT_NATIVE_INPUTS_RETAINED_ONLY_PINNED_WXS_CHANGED" if not bad else "SOURCE_REUSE_REJECTED","nativeSourceCommit":native["sourceCommit"],"matched":len(matched),"mismatches":bad,"permittedRecipeChange":change,"nativeRecompiled":False,"limits":limits.query()}
(O/"reuse-source-preflight.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps(record,ensure_ascii=False));assert not bad
