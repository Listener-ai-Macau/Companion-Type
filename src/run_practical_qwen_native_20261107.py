"""One owned short control; no long run, retries, global env, or driver changes."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,wave
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['inventory','short']);a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1';C.mkdir(exist_ok=True)
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
worker=Path(__file__).with_name('practical_qwen_native_worker_20261107.py');target=C/(a.phase+'-run.json');assert not target.exists()
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for proc in psutil.process_iter(['cmdline']):
    try:assert not any(Path(arg).name in ['practical_qwen_native_worker_20261107.py','practical_transcript_worker_20261107.py','practical_nemotron_worker_20261107.py','moss_night_gpu_worker_20261104.py'] for arg in proc.info['cmdline'] or []),'An existing owned model stage must finish first'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
if a.phase=='short':
    inventory=read(C/'hip-inventory.json');assert inventory['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL' and inventory['sourceSha256']==sha(worker)
    assert read(C/'prepared.json')['state']=='PINNED_OFFICIAL_NATIVE_HF_MODEL_READY_NO_INFERENCE'
    env['HIP_VISIBLE_DEVICES']=str(inventory['selected']['ordinal'])
    assert read(C/'protocol.json')['backend']=='official_native_transformers'
    assets=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/controls');assets.mkdir(exist_ok=False)
    cases=[]
    paths=[('public-compat30s',Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/engine-smoke30s-restored.wav'))]
    original=next(x for x in read(C.parent/'practical-text-first-r1/audio-only.json') if x['meeting']=='S_R004S03C01')
    first=assets/'S-original-first30s.wav'
    with wave.open(original['audio'],'rb') as f:
        assert sha(original['audio'])==original['audioSha256'];params=f.getparams();raw=f.readframes(480000)
    with wave.open(str(first),'wb') as f:f.setparams(params);f.writeframes(raw)
    silent=assets/'synthetic-silence3s.wav'
    with wave.open(str(silent),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0'*(3*16000*2))
    paths.extend([('S-original-first30s',first),('synthetic-silence3s',silent)])
    for ident,path in paths:
        with wave.open(str(path),'rb') as f:seconds=f.getnframes()/f.getframerate()
        cases.append({'id':ident,'audio':str(path),'audioSha256':sha(path),'audioSeconds':seconds})
    atomic_json(C/'short-audio-only.json',cases)
state={'state':'PREPARING_OFFICIAL_NATIVE_'+a.phase.upper(),'at':now(),'pid':os.getpid(),'workerSourceSha256':sha(worker),'automaticRetries':0,'referencePassedToWorker':False,'qualityQualified':False}
atomic_json(target,state);pressure=SystemRamPressure();child=None;process=None
try:
    assert not pressure.low(),'Actual Windows low-memory signal before native control'
    start=time.perf_counter();peak=0;rss_peak=0
    with (C/(a.phase+'-worker.log')).open('xb') as log:
        cmd=[PY,str(worker),'--control',str(C)]+(['--inventory-only'] if a.phase=='inventory' else [])
        child=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        process=psutil.Process(child.pid);process.cpu_affinity([14,15]);state.update(state='RUNNING_'+a.phase.upper(),activePid=child.pid);atomic_json(target,state)
        while child.poll() is None:
            low=pressure.low();stop=(C/'stop.request').exists();deadline=time.perf_counter()-start>(90 if a.phase=='inventory' else 600)
            if low or stop or deadline:
                state.update(state='STOPPED_OWN_NATIVE_CONTROL',reason='actual_low_ram' if low else 'explicit_stop' if stop else 'bounded_short_control_deadline');stop_owned_family(child,process);break
            try:
                family=[process]+process.children(recursive=True);private=sum(p.memory_info().private for p in family);rss=sum(p.memory_info().rss for p in family);peak=max(peak,private);rss_peak=max(rss_peak,rss)
                with (C/(a.phase+'-resources.jsonl')).open('a',encoding='utf8') as stream:stream.write(json.dumps({'at':now(),'privateBytes':private,'rssBytes':rss,'systemAvailableBytes':psutil.virtual_memory().available})+'\n')
            except psutil.Error:pass
            time.sleep(.5)
    state.update(exitCode=child.returncode,wholeProcessFamilySeconds=time.perf_counter()-start,sampledPrivatePeakBytes=peak,sampledRssPeakBytes=rss_peak)
    if state['state'].startswith('RUNNING_'):state['state']='COMPLETE_'+a.phase.upper()+'_CONTROL_REVIEW_REQUIRED' if child.returncode==0 else 'FAILED_NATIVE_CONTROL_RETAINED_NO_AUTOMATIC_RETRY'
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,process)
    pressure.close();state.pop('activePid',None);state.update(finishedAt=now());atomic_json(target,state);print(json.dumps(state),flush=True)
