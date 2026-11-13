from pathlib import Path
import subprocess,sys,os
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-android-media-import');W=Path(__file__).parent
env={**os.environ,'COMPANION_PHONE_QA_CODE':'145','NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'};env.pop('COMPANION_PHONE_QA_SESSION',None)
step=sys.argv[1];extra=sys.argv[2:]
commands={'display':['python',str(C/'software_phone_session.py'),'145','display'],'remember':['node',str(C/'software_phone_return.cjs'),'remember-appearance'],'restore':['python',str(C/'software_phone_restore.py'),'145',*extra],'review':['node',str(W/'review_notebook_phone145.cjs'),*extra],'restart':['python',str(C/'software_phone_session.py'),'145','restart'],'return':['node',str(C/'software_phone_return.cjs')],'close':['python',str(C/'software_phone_session.py'),'145','close']}
raise SystemExit(subprocess.call(commands[step],env=env))
