"""One fixed, bounded previously prepared ASR adaptation; no automatic retry."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,subprocess,sys,time
import psutil
from companion_local_pcm_session_20261114 import atomic_json,exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
    p.add_argument('--phase',choices=['trial'],default='trial');p.add_argument('--index',type=int,default=0)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    assert a.control.is_absolute() and a.run.is_absolute() and not a.run.exists()
    a.run.mkdir(parents=True);src=Path(__file__).resolve().parent
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    protocol=read(a.control/'protocol.json');worker=src/'nemotron_cache_trace_worker_20261115.py'
    assert sha(worker)==protocol['workerSha256']
    now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
    state={'state':'PREPARING_SAME_CHECKPOINT_REFERENCE','startedAt':now(),'phase':a.phase,'index':a.index,
        'workerSha256':sha(worker),'newTraining':False,'automaticRetries':0,'qualityQualified':False,'privatePeakBytes':0}
    save=lambda:atomic_json(a.run/'run.json',state);save()
    pressure=SystemRamPressure();child=owned=None;began=time.monotonic()
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
        try:
            assert not pressure.low(),'Actual Windows low-memory signal'
            inventory=a.run/'inventory'
            with (a.run/'inventory.log').open('xb') as log:
                code=subprocess.call([sys.executable,str(src/'run_practical_qwen_native_20261107.py'),
                    '--phase','inventory','--control',str(inventory)],stdout=log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            value=read(inventory/'hip-inventory.json')
            assert code==0 and value['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
            gpu=value['selected'];assert gpu['name']=='AMD Radeon RX 6800 XT' and gpu['architecture']=='gfx1030'
            assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(value['finishedAt'])).total_seconds()<1800
            env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
            env.update(HIP_VISIBLE_DEVICES=str(gpu['ordinal']),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
            command=['E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',
                str(worker),'--control',str(a.control),'--index',str(a.index),'--run',str(a.run)]
            with (a.run/'worker.log').open('xb') as log:
                child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                owned=psutil.Process(child.pid);state.update(state='RUNNING_SAME_CHECKPOINT_REFERENCE',pid=child.pid,pidCreatedAt=owned.create_time(),gpu=gpu);save()
                while child.poll() is None:
                    if pressure.low() or (a.run/'stop.request').exists() or time.monotonic()-began>3600:
                        stop_owned_family(child,owned);raise InterruptedError('Owned bounded model phase stopped; all source/nodes retained')
                    try:
                        memory=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True))
                        state['privatePeakBytes']=max(state['privatePeakBytes'],memory)
                        if memory>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Owned model family reached2GiB')
                    except psutil.Error:pass
                    time.sleep(.5)
            assert child.returncode==0,'Fixed ASR phase failed; no automatic variant or retry'
            state.update(state='COMPLETE_SAME_CHECKPOINT_REFERENCE_COMPARISON_PENDING',exitCode=0)
        except BaseException as error:state.update(state='INCOMPLETE_FIXED_ASR_PHASE_RETAINED_NO_AUTO_RETRY',error=repr(error));raise
        finally:
            if child is not None and child.poll() is None:stop_owned_family(child,owned)
            pressure.close();state.update(finishedAt=now(),seconds=time.monotonic()-began);save()
    print(json.dumps(state,ensure_ascii=False))

if __name__=='__main__':main()
