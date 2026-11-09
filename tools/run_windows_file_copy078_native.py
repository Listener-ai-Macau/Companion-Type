from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parents[2];S=Path(__file__).resolve().parents[1]
C=R/'docs/handoffs/20261109-windows-file-copy078';D=Path('E:/CodexData/Companion/.build-cache/windows051')
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
kind=sys.argv[1] if len(sys.argv)>1 else 'check'
assert kind in ['check','release']
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure()
if kind=='release':
 # Native077 measured ~2.5GiB for Rust release compilation. This build-only
 # job permits3GiB, with5%CPU/IDLE and actual Windows low-RAM stop. Model
 # workers retain their independent2GiB limit and are not started here.
 import ctypes
 from moss_windows_resource_limits_20261104 import ExtendedLimits
 native=ExtendedLimits();native.BasicLimitInformation.LimitFlags=0x2000|0x200;native.JobMemoryLimit=3*1024**3
 limits._check(limits.kernel.SetInformationJobObject(limits.job,9,ctypes.byref(native),ctypes.sizeof(native)))
 assert limits.query()['jobPrivateCommitLimitBytes']==3*1024**3
env={**os.environ,'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','CARGO_TARGET_DIR':str(D/'target'),'RAYON_NUM_THREADS':'1','TEMP':str(D),'TMP':str(D)}
pre=subprocess.run([sys.executable,str(R/'tools/check_type_build_target.py'),'--target-dir',str(D/'target'),'--project',str(S/'apps/windows/src-tauri'),'--source-dir',str(S)],capture_output=True,text=True,encoding='utf8',errors='replace')
(C/(kind+'-preflight.json')).write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
assert not pressure.low(),'Actual Windows low-RAM signal; do not start a native compile'
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip();tick=time.perf_counter();logpath=C/('native-'+kind+'-'+str(time.time_ns())+'.log')
record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'state':'RUNNING_NATIVE_'+kind.upper(),'sourceCommit':source,'kind':kind,'log':str(logpath),'limits':limits.query(),'modelsRun':False,'installed':False}
target=C/('native-'+kind+'-result.json');target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
args=['cargo','check','--lib','--offline','--locked'] if kind=='check' else ['cargo','build','--release','--offline','--locked']
with logpath.open('wb') as log:
 child=subprocess.Popen(args,cwd=S/'apps/windows/src-tauri',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 import psutil
 parent=psutil.Process(child.pid);record['pid']=child.pid;target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 while child.poll() is None:
  if pressure.low():
   record['stoppedForActualWindowsLowRam']=True
   for p in parent.children(recursive=True)[::-1]:
    try:p.terminate()
    except psutil.Error:pass
   child.terminate();child.wait();break
  time.sleep(1)
record.update(state=('PASS_NATIVE_'+kind.upper()) if child.returncode==0 else 'NATIVE_'+kind.upper()+'_FAILED_RETAINED',exitCode=child.returncode,wallSeconds=time.perf_counter()-tick,limits=limits.query())
target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');pressure.close()
print(json.dumps(record),flush=True);print(logpath.read_text(encoding='utf8',errors='replace')[-3500:],flush=True)
raise SystemExit(child.returncode or 0)
