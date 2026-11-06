from pathlib import Path
import json,subprocess,time,psutil,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share069'
exe=Path('E:/CodexData/Companion/.build-cache/windows-share069/ModernShareWindow.exe')
public=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff/saved/Windows067-public-transcript.pdf'
stamp=str(time.time_ns())
for name in ['modern-gui.log','modern-gui-session.json']:
 if (O/name).exists():shutil.copy2(O/name,O/(name+'.prior-'+stamp))
if (O/'stop-modern-gui').exists():(O/'stop-modern-gui').unlink()
log=(O/'modern-gui.log').open('w',encoding='utf8');p=subprocess.Popen([str(exe),str(public)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
created=psutil.Process(p.pid).create_time();meta={'pid':p.pid,'createTime':created,'exe':str(exe),'publicFile':str(public),'notInstalledProduct':True,'modelsRun':False}
(O/'modern-gui-session.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(meta),flush=True)
try:
 deadline=time.monotonic()+600
 while p.poll() is None and time.monotonic()<deadline and not (O/'stop-modern-gui').exists():time.sleep(.5)
finally:
 if p.poll() is None:
  own=psutil.Process(p.pid);assert own.create_time()==created and Path(own.exe()).resolve()==exe.resolve();p.terminate();p.wait(timeout=10)
 log.close();print('Own modern-share probe closed.',flush=True)
