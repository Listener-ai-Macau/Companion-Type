"""One bounded, model-free preprocessing attempt; never auto-retry or launch ASR."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,subprocess,time,psutil,sys
from moss_windows_resource_limits_20261104 import SystemRamPressure

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');Q=R/'model-research'
parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='r19');args=parser.parse_args()
assert args.run_id and all(c.isalnum() or c in '._-' for c in args.run_id)
control=R/('docs/handoffs/20261105-model-resume/full-L-prepared-inputs-20261106-'+args.run_id);control.mkdir(exist_ok=False)
prior=R/'docs/handoffs/20261105-model-resume/full-L-gpu-reconnected-20261106-r18'
protocol=json.loads((prior/'frozen-protocol.json').read_text(encoding='utf8'))
protocol['scope']='Exact original full-meeting author preprocessing in a separate process before model weights; same batch shape/math/device/runtime, no ASR, transcript, reference, tuning or audio truncation.'
(control/'frozen-protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
(control/'audio-only.json').write_bytes((prior/'audio-only.json').read_bytes())
cache=Path('E:/CodexData/Companion/.model-cache')/('moss-prepared-full-L-20261106-'+args.run_id);cache.mkdir(exist_ok=False)
env={k:v for k,v in os.environ.items() if not k.startswith(('COMPANION_','LISTENER_','OPENAI_','DEEPSEEK_','VOLC_','HF_TOKEN','HUGGING_FACE_HUB_TOKEN','PYTHONPATH'))}
env.update(HF_HOME=str(cache/'hf-cache'),HF_MODULES_CACHE=str(cache/'hf-modules'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HUB_DISABLE_PROGRESS_BARS='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMBA_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTHONUNBUFFERED='1',HIP_CACHE_DIR=str(cache/'hip-cache'),TRITON_CACHE_DIR=str(cache/'triton-cache'))
state={'state':'PREPARING_INPUTS_ONLY_NO_MODEL','startedAt':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'referencePassedToWorker':False,'automaticRetries':0,'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=Q,text=True).strip(),'peakPrivateBytes':0,'peakRssBytes':0,'output':str(cache/'packet')}
def save():(control/'supervisor-state.json').write_text(json.dumps(state,indent=2),encoding='utf8')
pressure=SystemRamPressure();start=time.perf_counter();save()
try:
    if pressure.low():state['state']='DEFERRED_WINDOWS_LOW_MEMORY_BEFORE_PREPROCESSING';save();raise SystemExit(0)
    with (control/'input-preparation.log').open('xb') as log:
        child=subprocess.Popen([protocol['runtime']['python'],str(Q/'src/prepare_moss_inputs_worker_20261106.py'),'--protocol',str(control/'frozen-protocol.json'),'--inputs',str(control/'audio-only.json'),'--output',str(cache/'packet')],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        process=psutil.Process(child.pid);process.cpu_affinity(protocol['runtime']['affinity']);state.update(pid=child.pid,processCreatedAt=process.create_time());save()
        while child.poll() is None:
            if pressure.low() or (control/'stop.request').exists():
                state['state']='STOPPED_PREPROCESSING_RESOURCE_OR_EXPLICIT_REQUEST'
                for member in reversed([process]+process.children(recursive=True)):
                    try:member.terminate()
                    except psutil.NoSuchProcess:pass
                child.wait(timeout=10);break
            try:
                family=[process]+process.children(recursive=True);rss=private=0
                for member in family:
                    info=member.memory_info();rss+=info.rss;private+=getattr(info,'private',0)
                state['peakPrivateBytes']=max(state['peakPrivateBytes'],private);state['peakRssBytes']=max(state['peakRssBytes'],rss)
                with (control/'resources.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps({'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'privateBytes':private,'rssBytes':rss,'availableMemoryBytes':psutil.virtual_memory().available})+'\n')
            except psutil.Error:pass
            time.sleep(1)
        state['exitCode']=child.wait()
    worker_path=control/'input-preparation-state.json';worker=json.loads(worker_path.read_text(encoding='utf8')) if worker_path.exists() else {}
    state['workerState']=worker.get('state')
    if state['exitCode']==0 and worker.get('state')=='COMPLETE_AUTHOR_INPUT_PREPARATION_NO_MODEL_LOADED':
        state.update(state='COMPLETE_EXACT_FULL_AUDIO_INPUT_PREPARATION_ONLY',manifest=worker['manifest'],manifestSha256=worker['manifestSha256'])
    elif state['state']=='PREPARING_INPUTS_ONLY_NO_MODEL':state['state']='PREPROCESSING_FAILURE_RETAINED_NO_RETRY'
finally:
    pressure.close();state.update(finishedAt=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),wallSeconds=time.perf_counter()-start);save()
print(json.dumps(state),flush=True)
