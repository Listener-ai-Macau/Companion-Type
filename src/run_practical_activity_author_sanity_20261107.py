"""One bounded fixture-only compatibility process after the real test fails."""
from pathlib import Path
from datetime import datetime
import json,os,psutil,subprocess,time
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1/author-sanity');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));assert not (C/'run.json').exists()
pressure=SystemRamPressure();assert not pressure.low();env={k:v for k,v in os.environ.items() if k not in ['HIP_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','CUDA_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']};env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HIP_VISIBLE_DEVICES=str(read(C.parent/'hip-inventory.json')['selected']['ordinal']))
state={'state':'RUNNING_AUTHOR_FIXTURE_COMPATIBILITY_ONLY','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'automaticRetries':0,'privatePeakBytes':0,'qualityQualified':False};atomic_json(C/'run.json',state);started=time.perf_counter()
with (C/'run.log').open('xb') as log:
    child=subprocess.Popen(['E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',str(Path(__file__).with_name('practical_activity_author_sanity_worker_20261107.py')),'--stage','short'],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);owned=psutil.Process(child.pid);owned.cpu_affinity([14,15])
    while child.poll() is None:
        if pressure.low() or time.perf_counter()-started>300:state['state']='STOPPED_FIXTURE_RESOURCE_OR_DEADLINE';stop_owned_family(child,owned);break
        try:state['privatePeakBytes']=max(state['privatePeakBytes'],sum(p.memory_info().private for p in [owned]+owned.children(recursive=True)))
        except psutil.Error:pass
        time.sleep(1)
state.update(exitCode=child.returncode,wholeProcessFamilySeconds=time.perf_counter()-started,finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'))
if child.returncode==0:state['state']='COMPLETE_AUTHOR_FIXTURE_COMPATIBILITY_REVIEW_REQUIRED'
elif state['state'].startswith('RUNNING_'):state['state']='FAILED_AUTHOR_FIXTURE_RETAINED_NO_RETRY'
pressure.close();atomic_json(C/'run.json',state);print(json.dumps(state),flush=True)
