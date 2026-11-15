"""One bounded native speaker-check job, preserving all previous outputs."""
from pathlib import Path
from datetime import datetime
import json,os,psutil,subprocess,time
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
assert not (C/'identity-run.json').exists()
for p in psutil.process_iter(['cmdline']):
    try:assert not any(Path(a).name in ['practical_ps4_frontend_worker_20261107.py','practical_ps4_identity_worker_20261107.py','practical_qwen_checkpoint_worker_20261107.py','practical_alignment_worker_20261107.py'] for a in p.info['cmdline'] or []),'Another neural stage runs'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
pressure=SystemRamPressure();assert not pressure.low(),'Wait for actual RAM recovery; existing audio and model outputs preserved'
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
env.update(HIP_VISIBLE_DEVICES=str(read(C/'hip-inventory.json')['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
command=['E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',str(Path(__file__).with_name('practical_ps4_identity_worker_20261107.py'))]
result={'state':'RUNNING_MATCHED_SPEAKER_IDENTITY_AUDIT','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'automaticRetries':0};atomic_json(C/'identity-run.json',result)
peak=0;start=time.perf_counter()
with (C/'identity-run.log').open('xb') as log:
    child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    owned=psutil.Process(child.pid);owned.cpu_affinity([14,15])
    while child.poll() is None:
        if pressure.low() or time.perf_counter()-start>300:
            result['state']='STOPPED_OWN_IDENTITY_AUDIT_RAM_OR_DEADLINE';stop_owned_family(child,owned);break
        try:peak=max(peak,sum(p.memory_info().private for p in [owned]+owned.children(recursive=True)))
        except psutil.Error:pass
        time.sleep(1)
result.update(exitCode=child.returncode,wholeProcessFamilySeconds=time.perf_counter()-start,privatePeakBytes=peak,finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'))
if child.returncode==0:result['state']='COMPLETE_MATCHED_SPEAKER_IDENTITY_AUDIT'
elif result['state'].startswith('RUNNING_'):result['state']='FAILED_MATCHED_SPEAKER_IDENTITY_AUDIT_RETAINED'
pressure.close();atomic_json(C/'identity-run.json',result);print(json.dumps(result),flush=True)
