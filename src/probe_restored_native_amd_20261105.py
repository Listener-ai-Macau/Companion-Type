"""A bounded native RX6800XT check; no speech model, references or training."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys,os,json,time,subprocess
sys.path.insert(0,str(Path(__file__).parent))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
root=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261105-model-resume')
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
if '--worker' in sys.argv:
    receipt=root/'native-amd-probe-worker-r3.json';assert not receipt.exists()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    state={'at':now(),'state':'IMPORTING_PINNED_NATIVE_FRAMEWORK','speechModelLoaded':False,'trainingRun':False,'resourceLimits':limits.receipt}
    def save():
        t=receipt.with_suffix('.tmp');t.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');t.replace(receipt)
    save();begin=time.perf_counter()
    try:
        import torch
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        assert torch.__version__=='2.11.0+rocm10.0.0' and torch.version.hip
        devices=[{'index':i,'name':torch.cuda.get_device_properties(i).name,'architecture':torch.cuda.get_device_properties(i).gcnArchName,'reportedMemoryBytes':torch.cuda.get_device_properties(i).total_memory} for i in range(torch.cuda.device_count())]
        candidates=[d for d in devices if 'RX 6800 XT' in d['name']];assert len(candidates)==1
        chosen=candidates[0];assert chosen['architecture'].startswith('gfx1030');torch.cuda.set_device(chosen['index']);device=torch.device('cuda',chosen['index'])
        state.update(state='CHECKING_TINY_NATIVE_GPU_OPERATORS',torchVersion=torch.__version__,hipVersion=torch.version.hip,devices=devices,chosen=chosen);save()
        checks=[]
        for dtype in [torch.float32,torch.bfloat16]:
            tick=time.perf_counter();a=torch.ones((64,64),device=device,dtype=dtype);b=a@a
            torch.cuda.synchronize(device);assert torch.all(b==64).item()
            checks.append({'dtype':str(dtype),'shape':[64,64],'knownExactResult':64,'seconds':time.perf_counter()-tick});del a,b
        state.update(state='NATIVE_RX6800XT_FP32_BF16_TINY_GPU_OPERATORS_PASSED_MODEL_UNTESTED',checks=checks,limitsAfterGpu=limits.query(),gpuPeakAllocatedBytes=torch.cuda.max_memory_allocated(device),gpuPeakReservedBytes=torch.cuda.max_memory_reserved(device))
    except BaseException as error:state.update(state='NATIVE_AMD_PROBE_FAILURE_RETAINED',error=repr(error));raise
    finally:state.update(finishedAt=now(),wallSeconds=time.perf_counter()-begin);save();print(json.dumps(state),flush=True)
else:
    import psutil
    receipt=root/'native-amd-probe-supervisor-r3.json';assert not receipt.exists()
    pressure=SystemRamPressure();state={'at':now(),'state':'PRECHECK','modelLoaded':False,'peakPrivateBytes':0,'peakRssBytes':0,'systemMemoryMinimum':psutil.virtual_memory().available}
    def save():receipt.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    save();begin=time.perf_counter();child=None
    try:
        if pressure.low():state['state']='DEFERRED_ACTUAL_WINDOWS_LOW_MEMORY_NOTIFICATION'
        else:
            python=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe')
            env={k:v for k,v in os.environ.items() if not k.startswith(('COMPANION_','LISTENER_','OPENAI_','HF_TOKEN','HUGGING_FACE_HUB_TOKEN','PYTHONPATH'))}
            env.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONUNBUFFERED='1')
            with (root/'native-amd-probe-r3.log').open('xb') as out:
                child=subprocess.Popen([str(python),str(Path(__file__).resolve()),'--worker'],env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                process=psutil.Process(child.pid);process.cpu_affinity(process.cpu_affinity()[-2:]);state.update(state='RUNNING_OWN_LIMITED_GPU_PROBE',ownedPid=child.pid);save()
                while child.poll() is None:
                    low=pressure.low();stop=(root/'stop.request').exists();expired=time.perf_counter()-begin>180
                    if low or stop or expired:
                        owned=process.children(recursive=True)+[process]
                        for member in reversed(owned):
                            try:member.terminate()
                            except psutil.NoSuchProcess:pass
                        psutil.wait_procs(owned,timeout=3);child.wait(timeout=5)
                        state['state']='STOPPED_LOW_RAM' if low else ('STOPPED_REQUEST' if stop else 'STOPPED_PROBE_TIMEOUT');break
                    try:
                        info=process.memory_info();state['peakRssBytes']=max(state['peakRssBytes'],info.rss);state['peakPrivateBytes']=max(state['peakPrivateBytes'],getattr(info,'private',0));state['systemMemoryMinimum']=min(state['systemMemoryMinimum'],psutil.virtual_memory().available)
                    except psutil.NoSuchProcess:pass
                    time.sleep(.5)
                state['exitCode']=child.returncode
                if state['state']=='RUNNING_OWN_LIMITED_GPU_PROBE':state['state']='PROBE_COMPLETED_READ_WORKER_SCOPE' if child.returncode==0 else 'PROBE_FAILED_READ_RETAINED_LOG'
    finally:pressure.close();state.update(finishedAt=now(),wallSeconds=time.perf_counter()-begin);save();print(json.dumps(state),flush=True)
