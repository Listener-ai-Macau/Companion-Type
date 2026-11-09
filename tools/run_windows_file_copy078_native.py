from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parents[2];S=Path(__file__).resolve().parents[1]
C=R/'docs/handoffs/20261109-windows-file-copy078';D=Path('E:/CodexData/Companion/.build-cache/windows051')
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
kind=sys.argv[1] if len(sys.argv)>1 else 'check'
assert kind in ['check','release','release-lowram','release-paged']
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure()
if kind in ['release','release-paged']:
 # Native077 measured ~2.5GiB for Rust release compilation. This build-only
 # job permits3GiB, with5%CPU/IDLE and actual Windows low-RAM stop. Model
 # workers retain their independent2GiB limit and are not started here.
 import ctypes
 from moss_windows_resource_limits_20261104 import ExtendedLimits
 native=ExtendedLimits();native.BasicLimitInformation.LimitFlags=0x2000|0x200;native.JobMemoryLimit=3*1024**3
 limits._check(limits.kernel.SetInformationJobObject(limits.job,9,ctypes.byref(native),ctypes.sizeof(native)))
 assert limits.query()['jobPrivateCommitLimitBytes']==3*1024**3
working_sets={};peak_family_rss=0
def bound_working_set(process):
 import ctypes
 from ctypes import wintypes as w
 # This build's own descendants only. Unlike the private-commit ceiling,
 # HARDWS_MAX limits resident physical pages; Windows may page this compiler
 # to the existing page file. No page-file/global/other-app setting changes.
 key=(process.pid,process.create_time())
 if key in working_sets:return
 kernel=limits.kernel
 kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
 kernel.SetProcessWorkingSetSizeEx.argtypes=[w.HANDLE,ctypes.c_size_t,ctypes.c_size_t,w.DWORD];kernel.SetProcessWorkingSetSizeEx.restype=w.BOOL
 kernel.GetProcessWorkingSetSizeEx.argtypes=[w.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(w.DWORD)];kernel.GetProcessWorkingSetSizeEx.restype=w.BOOL
 handle=kernel.OpenProcess(0x100|0x400,False,process.pid)
 if not handle:raise ctypes.WinError(ctypes.get_last_error())
 try:
  limits._check(kernel.SetProcessWorkingSetSizeEx(handle,1024**2,512*1024**2,0x2|0x4))
  minimum=ctypes.c_size_t();maximum=ctypes.c_size_t();flags=w.DWORD()
  limits._check(kernel.GetProcessWorkingSetSizeEx(handle,ctypes.byref(minimum),ctypes.byref(maximum),ctypes.byref(flags)))
  assert maximum.value==512*1024**2 and flags.value&0x4
  working_sets[key]={'pid':process.pid,'name':process.name(),'maximumBytes':maximum.value,'flags':flags.value}
 finally:kernel.CloseHandle(handle)
env={**os.environ,'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','CARGO_TARGET_DIR':str(D/'target'),'RAYON_NUM_THREADS':'1','TEMP':str(D),'TMP':str(D)}
pre=subprocess.run([sys.executable,str(R/'tools/check_type_build_target.py'),'--target-dir',str(D/'target'),'--project',str(S/'apps/windows/src-tauri'),'--source-dir',str(S)],capture_output=True,text=True,encoding='utf8',errors='replace')
(C/(kind+'-preflight.json')).write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
assert not pressure.low(),'Actual Windows low-RAM signal; do not start a native compile'
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip();tick=time.perf_counter();logpath=C/('native-'+kind+'-'+str(time.time_ns())+'.log')
record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'state':'RUNNING_NATIVE_'+kind.upper(),'sourceCommit':source,'kind':kind,'log':str(logpath),'limits':limits.query(),'modelsRun':False,'installed':False}
target=C/('native-'+kind+'-result.json');target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
args=['cargo','check','--lib','--offline','--locked'] if kind=='check' else ['cargo','build','--release','--offline','--locked']
if kind=='release-lowram':
 # Keep dependency optimizations and the release safety/panic settings. Only
 # this application's large crate uses smaller/basic optimization units for
 # a bounded local candidate. The prior normal release stopped on Windows'
 # actual low-memory notification; preserve it, do not overwrite its receipt.
 # This is not a model/ASR change or a claimed performance improvement.
 args.extend(['--config','profile.release.package.companion-type.opt-level=1',
              '--config','profile.release.package.companion-type.codegen-units=256'])
 record['applicationBuildOverrides']={'optLevel':1,'codegenUnits':256,'dependencyProfilesUnchanged':True,'runtimePerformanceQualified':False}
child=None
try:
 with logpath.open('wb') as log:
  child=subprocess.Popen(args,cwd=S/'apps/windows/src-tauri',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
  import psutil
  parent=psutil.Process(child.pid);record['pid']=child.pid;target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
  if kind=='release-paged':bound_working_set(psutil.Process())
  while child.poll() is None:
   if kind=='release-paged':
    family=[parent,*parent.children(recursive=True)]
    for process in family:
     try:bound_working_set(process)
     except (psutil.NoSuchProcess,psutil.ZombieProcess):pass
    rss=0
    for process in family:
     try:rss+=process.memory_info().rss
     except psutil.Error:pass
    peak_family_rss=max(peak_family_rss,rss)
   if pressure.low():
    record['stoppedForActualWindowsLowRam']=True
    for p in parent.children(recursive=True)[::-1]:
     try:p.terminate()
     except psutil.Error:pass
    child.terminate();child.wait();break
   time.sleep(.2 if kind=='release-paged' else 1)
except BaseException as error:
 # In particular Toolhelp/psutil itself can fail on an OS/quota allocation.
 # Retain a terminal receipt; the existing KILL_ON_JOB_CLOSE also terminates
 # any unenumerable children when this controller exits. Never leave RUNNING.
 record.update(state='CONTROLLER_FAILED_RETAINED',controllerError=repr(error),wallSeconds=time.perf_counter()-tick,physicalWorkingSetLimits=list(working_sets.values()),sampledPeakCargoFamilyResidentBytes=peak_family_rss)
 try:record['limits']=limits.query()
 except BaseException:record['limitsReadbackUnavailable']=True
 target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');pressure.close()
 raise
record.update(state=('PASS_NATIVE_'+kind.upper()) if child.returncode==0 else 'NATIVE_'+kind.upper()+'_FAILED_RETAINED',exitCode=child.returncode,wallSeconds=time.perf_counter()-tick,limits=limits.query())
if kind=='release-paged':record.update(physicalWorkingSetLimits=list(working_sets.values()),sampledPeakCargoFamilyResidentBytes=peak_family_rss,applicationBuildOverrides=None,pageFileOrOtherApplicationsChanged=False)
target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');pressure.close()
print(json.dumps(record),flush=True);print(logpath.read_text(encoding='utf8',errors='replace')[-3500:],flush=True)
raise SystemExit(child.returncode or 0)
