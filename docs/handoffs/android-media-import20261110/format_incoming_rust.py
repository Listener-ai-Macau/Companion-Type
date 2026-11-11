from pathlib import Path
import subprocess,sys,json
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");S=R/"companion-device-closure055";C=Path(__file__).parent
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2)
p=subprocess.run(["rustfmt","--edition","2021",str(S/"apps/windows/src-tauri/src/backend/incoming_files.rs"),str(S/"apps/windows/src-tauri/src/incoming_commands.rs")],cwd=S,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
(C/"incoming-rust-syntax-format.log").write_bytes(p.stdout+p.stderr)
record={"exitCode":p.returncode,"nativeBuild":False,"limits":limits.query()}
(C/"incoming-rust-syntax-format.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");print(json.dumps(record));assert p.returncode==0
