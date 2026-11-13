from pathlib import Path
import json,os,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261110-android-media-import';W=Path(__file__).parent
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,512*1024**2)
env={**os.environ,'COMPANION_PHONE_QA_CODE':'155','NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'};env.pop('COMPANION_PHONE_QA_SESSION',None)
def run(*args):subprocess.run(list(map(str,args)),env=env,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
phase=sys.argv[1]
if phase=='setup':
 p=W/'prepare_template_phone147.py';text=p.read_text(encoding='utf8').replace('147','155').replace('android155-local-r2','android155-local')
 # Reuse the declared public-backup/owned-display workflow without an Owner prompt.
 exec(compile(text,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
 run(sys.executable,C/'software_phone_session.py','155','install')
elif phase=='display':run(sys.executable,W/'run_template_phone155.py','display')
elif phase=='remember-restore':
 for step in ['remember','restore']:run(sys.executable,W/'run_template_phone155.py',step)
elif phase in ['before-restart','after-restart']:run('node',W/'review_resumed_phone155.cjs',phase)
elif phase=='restart':run(sys.executable,W/'run_template_phone155.py','restart')
elif phase=='return-close':
 for step in ['return','close']:run(sys.executable,W/'run_template_phone155.py',step)
else:raise ValueError(phase)
