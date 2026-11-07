"""One owned model stage at a time, actual RAM guard, no neural-error retries."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
parser=argparse.ArgumentParser();parser.add_argument('--resume-after-low-ram',action='store_true');args=parser.parse_args()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
for member in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(a).name in ['practical_ps4_frontend_worker_20261107.py','practical_alignment_worker_20261107.py','practical_qwen_checkpoint_worker_20261107.py','practical_qwen_boundaries_worker_20261107.py','moss_night_gpu_worker_20261104.py'] for a in member.info['cmdline'] or []),'Another owned model stage runs'
    except (psutil.AccessDenied,psutil.NoSuchProcess):pass
pressure=SystemRamPressure();target=C/'run-r2.json';prior=[]
if target.exists():
    old=read(target);assert args.resume_after_low_ram and old['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM' and old.get('finishedAt')
    last=json.loads((C/'resources-r2.json').read_text().splitlines()[-1]) if old['results'] else {'availableBytes':old['deferredAvailableBytes']}
    peak=old['results'][-1]['privatePeakBytes'] if old['results'] else 0
    assert not pressure.low() and psutil.virtual_memory().available>last['availableBytes']+peak,'Wait for actual external memory recovery'
    archive=C/('r2-attempt-%04d.json'%(len(old['priorAttemptReceipts'])+1));assert not archive.exists();archive.write_bytes(target.read_bytes());prior=old['priorAttemptReceipts']+[str(archive)]
else:assert not args.resume_after_low_ram
state={'state':'PREPARING_SEQUENTIAL_TARGET_SEPARATION_ASR','pid':os.getpid(),'startedAt':now(),'priorAttemptReceipts':prior,'results':[],'automaticModelFailureRetries':0,'qualityQualified':False}
atomic_json(target,state);child=None;owned=None
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
stages=[('inventory','practical_qwen_native_worker_20261107.py',['--control',str(C),'--inventory-only'],C/'hip-inventory.json','PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'),
    ('separation','practical_ps4_frontend_worker_20261107.py',['--stage','separation'],C/'separation-state-r2.json','COMPLETE_PS4_SEPARATION_UNQUALIFIED'),
    ('asr','practical_ps4_frontend_worker_20261107.py',['--stage','asr'],C/'asr-state-r2.json','COMPLETE_PS4_ASR_UNQUALIFIED')]
try:
    for stage,module,extra,receipt,passed in stages:
        if receipt.exists() and read(receipt)['state']==passed:continue
        if pressure.low():state.update(state='STOPPED_ACTUAL_WINDOWS_LOW_RAM',deferredAvailableBytes=psutil.virtual_memory().available);break
        if stage!='inventory':env['HIP_VISIBLE_DEVICES']=str(read(C/'hip-inventory.json')['selected']['ordinal'])
        command=[PY,str(Path(__file__).with_name(module)),*extra]
        if receipt.exists():
            assert stage!='inventory','Retain failed GPU inventory; no automatic retry'
            command+=['--resume']
        peak=0;start=time.perf_counter();lastpoint=None;progress_at=start
        with (C/(stage+'-r2-attempt-%04d.log'%(len(prior)+1))).open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);owned.cpu_affinity([14,15]);state.update(state='RUNNING_PS4_'+stage.upper(),stage=stage,activePid=child.pid);atomic_json(target,state)
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists()
                if low or stop or time.perf_counter()-progress_at>600:
                    state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY' if stop else 'STOPPED_MODEL_PROGRESS_DEADLINE';stop_owned_family(child,owned);break
                try:
                    private=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,private)
                    progress=read(receipt) if receipt.exists() else {};point=(progress.get('state'),progress.get('completedInputs'),progress.get('newNeuralCalls'))
                    if point!=lastpoint:lastpoint=point;progress_at=time.perf_counter()
                    with (C/'resources-r2.json').open('a',encoding='utf8') as output:output.write(json.dumps({'at':now(),'stage':stage,'availableBytes':psutil.virtual_memory().available,'privateBytes':private,'completedInputs':progress.get('completedInputs'),'newNeuralCalls':progress.get('newNeuralCalls')})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        state.pop('activePid',None);state['results'].append({'stage':stage,'exitCode':child.returncode,'wholeProcessFamilySeconds':time.perf_counter()-start,'privatePeakBytes':peak});atomic_json(target,state)
        if child.returncode:
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_PS4_COMPONENT_RETAINED_NO_AUTOMATIC_RETRY'
            break
        assert read(receipt)['state']==passed
    else:state['state']='COMPLETE_TARGET_SEPARATION_AND_ASR_REVIEW_REQUIRED'
except BaseException as error:
    state.update(state='PS4_CONTROLLER_ERROR_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,owned)
    pressure.close();state.pop('activePid',None);state.update(finishedAt=now());atomic_json(target,state);print(json.dumps(state),flush=True)
