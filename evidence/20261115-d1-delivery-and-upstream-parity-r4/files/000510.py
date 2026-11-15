"""Sequential inventory/pilot/short, own-family actual RAM guard, no model retries."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,psutil,subprocess,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
parser=argparse.ArgumentParser();parser.add_argument('--resume-after-low-ram',action='store_true');parser.add_argument('--resume-preparation',action='store_true');args=parser.parse_args()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
for p in psutil.process_iter(['cmdline']):
    try:assert not any(Path(a).name.startswith('practical_') and '_worker_20261107.py' in Path(a).name for a in p.info['cmdline'] or []),'Another neural stage runs'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
pressure=SystemRamPressure();target=C/'run.json';prior=[]
if target.exists():
    old=read(target);assert old.get('finishedAt')
    if args.resume_preparation:
        assert old['state']=='FAILED_ACTIVITY_CANDIDATE_NO_MODEL_RETRY' and (C/'preparation-instrumentation-change.json').exists()
        assert not (C/'outputs').exists() and not (C/'native-enrollment-vectors.json').exists()
        assert read(C/'pilot-state-preparation-failure-01.json')['newNeuralCalls']==0
        assert read(C/'gpu-feature-numeric-proof.json')['state']=='PASS_NATIVE_GPU_KALDI_FEATURES_INDEPENDENT_NUMPY_REFERENCE'
        assert read(C/'preparation-instrumentation-change.json')['cpuFeatureFailureReproducedWithoutModels']
    else:
        assert args.resume_after_low_ram and old['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM'
        assert not pressure.low() and psutil.virtual_memory().available>old['lastAvailableBytes']+(old['results'][-1]['privatePeakBytes'] if old['results'] else 0),'Wait for actual external RAM recovery'
    archive=C/('attempt-%04d.json'%(len(old['priorAttemptReceipts'])+1));assert not archive.exists();archive.write_bytes(target.read_bytes());prior=old['priorAttemptReceipts']+[str(archive)]
else:assert not args.resume_after_low_ram and not args.resume_preparation
state={'state':'PREPARING_ONE_ACTIVITY_CANDIDATE','pid':os.getpid(),'startedAt':now(),'priorAttemptReceipts':prior,'results':[],'automaticModelFailureRetries':0,'qualityQualified':False};atomic_json(target,state);child=None;owned=None
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']};env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
stages=[('inventory','practical_qwen_native_worker_20261107.py',['--control',str(C),'--inventory-only'],C/'hip-inventory.json','PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'),
    ('pilot','practical_target_activity_worker_20261107.py',['--stage','pilot'],C/'pilot-state.json','COMPLETE_TARGET_ACTIVITY_PILOT_UNQUALIFIED'),
    ('short','practical_target_activity_worker_20261107.py',['--stage','short'],C/'short-state.json','COMPLETE_TARGET_ACTIVITY_SHORT_UNQUALIFIED')]
try:
    for stage,module,extra,receipt,passed in stages:
        if receipt.exists() and read(receipt)['state']==passed:continue
        state['lastAvailableBytes']=psutil.virtual_memory().available
        if pressure.low():state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM';break
        if stage!='inventory':env['HIP_VISIBLE_DEVICES']=str(read(C/'hip-inventory.json')['selected']['ordinal'])
        command=[PY,str(Path(__file__).with_name(module)),*extra]
        if receipt.exists():assert stage!='inventory';command+=['--resume']
        peak=0;tick=time.perf_counter();point=None;progress_at=tick
        with (C/(stage+'-attempt-%04d.log'%(len(prior)+1))).open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);owned.cpu_affinity([14,15]);state.update(state='RUNNING_TARGET_ACTIVITY_'+stage.upper(),activePid=child.pid);atomic_json(target,state)
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists();state['lastAvailableBytes']=psutil.virtual_memory().available
                if low or stop or time.perf_counter()-progress_at>600:
                    state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY' if stop else 'STOPPED_PROGRESS_DEADLINE';stop_owned_family(child,owned);break
                try:
                    private=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,private);progress=read(receipt) if receipt.exists() else {};newpoint=(progress.get('state'),progress.get('completedInputs'),progress.get('newNeuralCalls'))
                    if newpoint!=point:point=newpoint;progress_at=time.perf_counter()
                    with (C/'resources.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps({'at':now(),'stage':stage,'privateBytes':private,'availableBytes':state['lastAvailableBytes'],'completedInputs':progress.get('completedInputs'),'newNeuralCalls':progress.get('newNeuralCalls')})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        state.pop('activePid',None);state['results'].append({'stage':stage,'exitCode':child.returncode,'wholeProcessFamilySeconds':time.perf_counter()-tick,'privatePeakBytes':peak});atomic_json(target,state)
        if child.returncode:
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_ACTIVITY_CANDIDATE_NO_MODEL_RETRY'
            break
        assert read(receipt)['state']==passed
    else:state['state']='COMPLETE_SHORT_ACTIVITY_CANDIDATE_REVIEW_REQUIRED'
except BaseException as error:state.update(state='ACTIVITY_CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,owned)
    pressure.close();state.pop('activePid',None);state.update(finishedAt=now());atomic_json(target,state);print(json.dumps(state),flush=True)
