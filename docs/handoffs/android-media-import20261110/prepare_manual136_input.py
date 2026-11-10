from pathlib import Path
import hashlib,json,subprocess,sys,os
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110");O=C/"android136";O.mkdir(exist_ok=True)
source=P/"phone134/Companion-public-reader134-entry.zip";old=json.loads((P/"phone134/public-entry.json").read_text());dest=P/"phone136/Companion-public-reader136-entry.zip"
assert source.exists() and not dest.exists();import shutil;shutil.copyfile(source,dest)
digest=hashlib.file_digest(dest.open("rb"),"sha256").hexdigest()
reference=json.loads((P/"phone134/public-entry.json").read_text());print("Input reused; exact SHA",digest,"bytes",dest.stat().st_size)
meta={"path":str(dest),"bytes":dest.stat().st_size,"sha256":digest,"source":"Retained public134 entry, exact same bytes; no new transcription or extraction/model result."}
(P/"phone136/public-entry.json").write_text(json.dumps(meta,indent=2)+"\n")
adb=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";remote="/sdcard/Download/"+dest.name
q=subprocess.run([str(adb),"-s","d6bd213d","push",str(dest),remote],capture_output=True,timeout=60);assert q.returncode==0,q.stderr.decode(errors="replace")
q=subprocess.run([str(adb),"-s","d6bd213d","shell","sha256sum",remote],capture_output=True,text=True,timeout=30);assert q.returncode==0 and q.stdout.split()[0]==digest
(O/"reader-external-files.json").write_text(json.dumps({"files":[{"path":remote,"sha256":digest,"bytes":dest.stat().st_size}]},indent=2)+"\n")
