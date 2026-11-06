from pathlib import Path
import hashlib,json,os,psutil,subprocess,time,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share069'
proof=json.loads((O/'dual-probe-result.json').read_text(encoding='utf8'));exe=Path(proof['probeExe']);assert hashlib.sha256(exe.read_bytes()).hexdigest()==proof['probeExeSha256']
public=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff/saved/Windows067-public-transcript.pdf'
stamp=str(time.time_ns())
for name in ['dual-gui.log','dual-gui-session.json']:
 if (O/name).exists():shutil.copy2(O/name,O/(name+'.prior-'+stamp))
if (O/'stop-dual-gui').exists():(O/'stop-dual-gui').unlink()
log=(O/'dual-gui.log').open('w',encoding='utf8');p=subprocess.Popen([str(exe),str(public),'--gui'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
created=psutil.Process(p.pid).create_time();record={'pid':p.pid,'createTime':created,'exe':str(exe),'notInstalledProduct':True,'publicFixture':True,'modelsRun':False,'ownerResumedLimitedUi':True}
(O/'dual-gui-session.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
try:
 deadline=time.monotonic()+900
 while p.poll() is None and time.monotonic()<deadline and not (O/'stop-dual-gui').exists():time.sleep(.5)
finally:
 if p.poll() is None:
  own=psutil.Process(p.pid);assert own.create_time()==created and Path(own.exe()).resolve()==exe.resolve();p.terminate();p.wait(timeout=10)
 log.close();print('Owned dual probe closed.',flush=True)
