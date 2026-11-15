"""Sequential tiny-loader, real pilot and full alignment with owned-only guards."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,psutil,subprocess,sys,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
parser=argparse.ArgumentParser();parser.add_argument('--resume-after-low-ram',action='store_true');args=parser.parse_args()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-alignment-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
for member in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(a).name in ['practical_alignment_worker_20261107.py','check_practical_alignment_loader_20261107.py','practical_qwen_boundaries_worker_20261107.py','run_practical_qwen_boundaries_20261107.py','practical_qwen_checkpoint_worker_20261107.py'] for a in member.info['cmdline'] or []),'Another neural stage still runs'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
pressure=SystemRamPressure();target=C/'run.json';prior=[]
if target.exists():
    old=read(target);assert args.resume_after_low_ram and old['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM' and old.get('finishedAt')
    last=json.loads((C/'resources.jsonl').read_text().splitlines()[-1]) if old['results'] else {'availableBytes':old['deferredAvailableBytes']}
    peak=old['results'][-1]['privatePeakBytes'] if old['results'] else 0
    assert not pressure.low() and psutil.virtual_memory().available>last['availableBytes']+peak,'Wait for actual external RAM recovery'
    archive=C/('attempt-%04d.json'%(len(old['priorAttemptReceipts'])+1));assert not archive.exists();archive.write_bytes(target.read_bytes())
    prior=old['priorAttemptReceipts']+[str(archive)]
else:assert not args.resume_after_low_ram
state={'state':'PREPARING_SEQUENTIAL_NATIVE_ALIGNMENT','startedAt':now(),'pid':os.getpid(),'priorAttemptReceipts':prior,'results':[],'automaticModelFailureRetries':0,'qualityQualified':False}
atomic_json(target,state);child=None;owned=None
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
env.update(HIP_VISIBLE_DEVICES=str(read(C.parent/'practical-qwen-author-boundaries-r6/hip-inventory.json')['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
stages=[('tiny-loader','check_practical_alignment_loader_20261107.py',[],C/'tiny-loader-proof.json','PASS_STANDARD_AND_STREAMED_TINY_ALIGNER_EXACT_LOGITS'),
    ('pilot','practical_alignment_worker_20261107.py',['--phase','pilot'],C/'pilot-state.json','COMPLETE_NATIVE_ALIGNMENT_PILOT_NOT_TIME_QUALIFIED'),
    ('full','practical_alignment_worker_20261107.py',['--phase','full'],C/'full-state.json','COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED')]
try:
    for label,module,extra,receipt,passed in stages:
        if receipt.exists() and read(receipt).get('state')==passed:continue
        if pressure.low():state.update(state='STOPPED_ACTUAL_WINDOWS_LOW_RAM',deferredAvailableBytes=psutil.virtual_memory().available);break
        command=[PY,str(Path(__file__).with_name(module)),*extra]
        if receipt.exists() and module=='practical_alignment_worker_20261107.py':command+=['--resume']
        elif receipt.exists():raise AssertionError('Retain failed tiny-loader proof, no automatic retry')
        start=time.perf_counter();peak=0;lastpoint=None;progress_at=start
        log=C/(label+'-attempt-%04d.log'%(len(prior)+1))
        with log.open('xb') as stream:
            child=subprocess.Popen(command,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);owned.cpu_affinity([14,15]);state.update(state='RUNNING_NATIVE_ALIGNMENT_'+label.upper(),activePid=child.pid,stage=label);atomic_json(target,state)
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists()
                if low or stop or time.perf_counter()-progress_at>600:
                    state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY' if stop else 'STOPPED_ALIGNMENT_PROGRESS_DEADLINE';stop_owned_family(child,owned);break
                try:
                    private=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,private)
                    progress=read(receipt) if receipt.exists() else {}
                    point=(progress.get('state'),progress.get('completedLeaves'),progress.get('newNeuralCalls'))
                    if point!=lastpoint:lastpoint=point;progress_at=time.perf_counter()
                    with (C/'resources.jsonl').open('a',encoding='utf8') as output:output.write(json.dumps({'at':now(),'stage':label,'availableBytes':psutil.virtual_memory().available,'privateBytes':private,'completedLeaves':progress.get('completedLeaves')})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        state.pop('activePid',None)
        state['results'].append({'stage':label,'exitCode':child.returncode,'wholeProcessFamilySeconds':time.perf_counter()-start,'privatePeakBytes':peak})
        atomic_json(target,state)
        if child.returncode:
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_NATIVE_ALIGNMENT_RETAINED_NO_AUTOMATIC_RETRY'
            break
        assert read(receipt)['state']==passed
    else:state['state']='COMPLETE_SEQUENTIAL_NATIVE_ALIGNMENT_REVIEW_REQUIRED'
except BaseException as error:
    state.update(state='ALIGNMENT_CONTROLLER_ERROR_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,owned)
    pressure.close();state.pop('activePid',None);state.update(finishedAt=now());atomic_json(target,state);print(json.dumps(state),flush=True)
