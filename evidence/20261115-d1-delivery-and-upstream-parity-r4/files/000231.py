"""Exercise real Windows limits and supervisor cancellation, without GPU work."""
from pathlib import Path
import json, os, shutil, subprocess, sys, time
import psutil

source=Path(__file__).parent
root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
test=root/'resource-control-check';test.mkdir(exist_ok=False)
for name in ['moss_windows_resource_limits_20261104.py','run_night_moss_gpu_20261104.py']:
    shutil.copy2(source/name,test/name)
# The fake worker only sleeps. Check job membership against this exact job,
# including a real grandchild; no model, torch, or GPU kernels are loaded.
(test/'moss_night_gpu_worker_20261104.py').write_text('''from pathlib import Path
import ctypes,json,subprocess,sys,time
from ctypes import wintypes as w
from moss_windows_resource_limits_20261104 import WorkerLimits
import psutil
limits=WorkerLimits(cpu_percent=5)
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW)
try:
 k=limits.kernel
 k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
 handle=k.OpenProcess(0x1000,False,child.pid)
 assert handle
 member=w.BOOL()
 limits._check(k.IsProcessInJob(handle,limits.job,ctypes.byref(member)));k.CloseHandle(handle)
 receipt=limits.query();receipt.update(childPid=child.pid,childInheritedThisJob=bool(member.value),torchImported='torch' in sys.modules)
 Path(__file__).with_name('sleeping-worker.json').write_text(json.dumps(receipt),encoding='utf8')
 assert member.value and not receipt['torchImported']
 time.sleep(60)
finally:
 if child.poll() is None:child.terminate();child.wait(timeout=3)
''',encoding='utf8')
(test/'inputs.json').write_text(json.dumps([{'meeting':'sleeping-cancellation-check','smokeOnly':True}]),encoding='utf8')
(test/'protocol.json').write_text(json.dumps({'runtime':{'python':sys.executable,'affinity':[10,14]}}),encoding='utf8')
args=[sys.executable,str(test/'run_night_moss_gpu_20261104.py'),'--control-root',str(test),
      '--inputs',str(test/'inputs.json'),'--protocol',str(test/'protocol.json'),'--run-name','sleeping-run']
with (test/'check.log').open('w',encoding='utf8') as log:
    process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    owned=[]
    try:
        deadline=time.perf_counter()+12
        while not (test/'sleeping-worker.json').exists():
            if process.poll() is not None:raise RuntimeError('Supervisor exited before sleeping worker receipt')
            if time.perf_counter()>deadline:raise TimeoutError('Sleeping-worker startup deadline')
            time.sleep(.1)
        receipt=json.loads((test/'sleeping-worker.json').read_text(encoding='utf8'))
        owned=[psutil.Process(receipt['pid']),psutil.Process(receipt['childPid'])]
        assert receipt['cpuControlFlags']==5 and receipt['cpuRate']==500
        assert receipt['cpuPriorityClass']==0x40 and receipt['gpuPriorityClass']==0
        assert receipt['childInheritedThisJob'] and not receipt['torchImported']
        stopped=time.perf_counter();(test/'stop.request').write_text('Controlled cancellation check',encoding='utf8')
        process.wait(timeout=8);elapsed=time.perf_counter()-stopped
        state=json.loads((test/'sleeping-run.json').read_text(encoding='utf8'))
        assert state['state']=='STOPPED_DURING_WORKER_EXPLICIT_REQUEST',state
        assert all(not p.is_running() for p in owned),'Experiment descendants must exit'
        assert elapsed<5
        # Repeat launch while paused: must fail before a worker/output starts.
        blocked=subprocess.run(args[:-1]+['blocked-run'],capture_output=True,text=True,timeout=5)
        assert blocked.returncode!=0 and 'paused' in blocked.stderr.lower()
        assert not (test/'blocked-run.json').exists()
        # Direct worker entry must also honor pause BEFORE imports/model setup.
        blocked_worker=subprocess.run([sys.executable,str(source/'moss_night_gpu_worker_20261104.py'),
          '--index','0','--inputs',str(test/'inputs.json'),'--protocol',str(test/'protocol.json')],
          capture_output=True,text=True,timeout=5)
        assert blocked_worker.returncode!=0 and 'paused' in blocked_worker.stderr.lower()
        report={'state':'PASS_LIGHTWEIGHT_WINDOWS_CONTROL_CHECK','worker':receipt,
          'supervisorState':state['state'],'cancellationSeconds':elapsed,'allOwnedDescendantsExited':True,
          'pausedSupervisorBlockedBeforeWorker':True,'pausedDirectWorkerBlockedBeforeImports':True,
          'mainExperimentRemainsPaused':(root/'stop.request').exists(),
          'scope':'No model import, GPU computation, CPU load benchmark, or other-app changes.'}
        assert report['mainExperimentRemainsPaused']
        (root/'resource-control-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(report))
    finally:
        # Only processes created by this check; never enumerate/kill other apps.
        if process.poll() is None:process.terminate();process.wait(timeout=3)
        for member in owned:
            try:
                if member.is_running():member.terminate();member.wait(timeout=3)
            except psutil.NoSuchProcess:pass
