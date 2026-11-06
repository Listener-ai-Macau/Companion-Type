from pathlib import Path
import json,os,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share068'
exe=Path('E:/CodexData/Companion/.build-cache/windows051/target/debug/companion-share068-probe.exe')
public=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff/saved/Windows067-public-transcript.pdf'
mode='populate' if '--populate' in sys.argv else 'baseline';env={**os.environ}
if mode=='populate':env['COMPANION_QA_POPULATE_REQUEST']='1'
else:env.pop('COMPANION_QA_POPULATE_REQUEST',None)
log=(O/('probe-gui-'+mode+'.log')).open('w',encoding='utf8')
p=subprocess.Popen([str(exe),str(public),'--gui'],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
created=psutil.Process(p.pid).create_time();meta={'pid':p.pid,'createTime':created,'exe':str(exe),'mode':mode,'modelsRun':False,'publicSyntheticFixture':True,'notInstalledProduct':True}
(O/'probe-gui-session.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(meta),flush=True)
try:p.wait(timeout=300)
finally:
 if p.poll() is None:
  own=psutil.Process(p.pid);assert own.create_time()==created and Path(own.exe()).resolve()==exe.resolve();p.terminate();p.wait(timeout=10)
 log.close()
 print('Own native probe closed.',flush=True)
