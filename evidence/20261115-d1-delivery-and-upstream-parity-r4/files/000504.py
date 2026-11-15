"""One bounded audio-only local-identity audit; resource-only resumptions."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,psutil,subprocess,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
parser=argparse.ArgumentParser();parser.add_argument('--resume-after-low-ram',action='store_true');args=parser.parse_args()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-ps4-local-presence-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
for p in psutil.process_iter(['cmdline']):
    try:
        names=[Path(a).name for a in p.info['cmdline'] or []]
        assert not any(n.endswith('_worker_20261107.py') and n.startswith(('practical_','moss_')) for n in names),'Another neural stage runs'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
pressure=SystemRamPressure();target=C/'run.json';prior=[]
if target.exists():
    old=read(target);assert args.resume_after_low_ram and old['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM' and old.get('finishedAt')
    assert not pressure.low() and psutil.virtual_memory().available>old['lastAvailableBytes']+old['privatePeakBytes'],'Wait for actual external RAM recovery'
    archive=C/('attempt-%04d.json'%(len(old['priorAttemptReceipts'])+1));assert not archive.exists();archive.write_bytes(target.read_bytes());prior=old['priorAttemptReceipts']+[str(archive)]
else:assert not args.resume_after_low_ram
state={'state':'PREPARING_TIME_LOCAL_IDENTITY_AUDIT','pid':os.getpid(),'startedAt':now(),'priorAttemptReceipts':prior,'automaticModelFailureRetries':0,'privatePeakBytes':0,'qualityQualified':False};atomic_json(target,state)
child=None;owned=None;started=time.perf_counter()
try:
    state['lastAvailableBytes']=psutil.virtual_memory().available
    if pressure.low():state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM'
    else:
        env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
        inv=read(C.parent/'practical-conditioned-ps4-full-r1/hip-inventory.json')
        assert inv['selected']['name']=='AMD Radeon RX 6800 XT'
        env.update(HIP_VISIBLE_DEVICES=str(inv['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        command=['E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',str(Path(__file__).with_name('practical_ps4_local_presence_worker_20261107.py'))]
        if (C/'state.json').exists():command+=['--resume']
        point=None;progress_at=time.perf_counter()
        with (C/('run-attempt-%04d.log'%(len(prior)+1))).open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);owned.cpu_affinity([14,15]);state.update(state='RUNNING_TIME_LOCAL_IDENTITY_AUDIT',activePid=child.pid);atomic_json(target,state)
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists();state['lastAvailableBytes']=psutil.virtual_memory().available
                if low or stop or time.perf_counter()-progress_at>600:
                    state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY' if stop else 'STOPPED_PROGRESS_DEADLINE';stop_owned_family(child,owned);break
                try:
                    private=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));state['privatePeakBytes']=max(state['privatePeakBytes'],private)
                    progress=read(C/'state.json') if (C/'state.json').exists() else {};newpoint=(progress.get('state'),progress.get('completedWindows'))
                    if newpoint!=point:point=newpoint;progress_at=time.perf_counter()
                    with (C/'resources.jsonl').open('a',encoding='utf8') as output:output.write(json.dumps({'at':now(),'privateBytes':private,'availableBytes':state['lastAvailableBytes'],'completedWindows':progress.get('completedWindows')})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        state['exitCode']=child.returncode
        if child.returncode==0:
            assert read(C/'state.json')['state']=='COMPLETE_LOCAL_IDENTITY_HYPOTHESIS_UNQUALIFIED';state['state']='COMPLETE_LOCAL_AUDIT_REVIEW_REQUIRED'
        elif not state['state'].startswith('STOPPED_'):state['state']='FAILED_LOCAL_AUDIT_NO_MODEL_RETRY'
except BaseException as error:
    state.update(state='FAILED_LOCAL_AUDIT_CONTROLLER_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,owned)
    pressure.close();state.pop('activePid',None);state.update(finishedAt=now(),wholeProcessFamilySeconds=time.perf_counter()-started);atomic_json(target,state);print(json.dumps(state),flush=True)
