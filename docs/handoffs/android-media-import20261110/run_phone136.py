from pathlib import Path
import subprocess,sys,os
c=Path(__file__).parent;name=sys.argv[1];assert name.endswith((".cjs",".py")) and "/" not in name and "\\" not in name and (c/name).is_file()
env={**os.environ,"COMPANION_PHONE_QA_CODE":"136"};env.pop("COMPANION_PHONE_QA_SESSION",None)
q=subprocess.run(["node" if name.endswith(".cjs") else "python",str(c/name),*sys.argv[2:]],env=env);raise SystemExit(q.returncode)
