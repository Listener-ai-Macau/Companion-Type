"""Sequential bounded adaptation, resource-only resume, quality-gated evaluation."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,psutil,subprocess,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
parser=argparse.ArgumentParser();parser.add_argument('--resume-after-low-ram',action='store_true');args=parser.parse_args();C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-target-activity-adaptation');S=Path(__file__).parent;read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
for p in psutil.process_iter(['cmdline']):
    try:
        for argument in p.info['cmdline'] or []:
            a=argument.replace('\\','/').strip('"')
            assert not (a.lower().startswith(str(S).replace('\\','/').lower()+'/') and a.endswith('.py') and ('_worker_' in a or Path(a).name=='target_activity_adaptation_worker_20261108.py')),'Another owned neural stage runs'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
pressure=SystemRamPressure();target=C/'run.json';prior=[]
if target.exists():
    old=read(target);assert args.resume_after_low_ram and old['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM' and old.get('finishedAt');assert not pressure.low() and psutil.virtual_memory().available>old['lastAvailableBytes']+(old['results'][-1]['privatePeakBytes'] if old['results'] else 0),'Wait for actual external RAM recovery'
    archive=C/('attempt-%04d.json'%(len(old['priorAttemptReceipts'])+1));assert not archive.exists();archive.write_bytes(target.read_bytes());prior=old['priorAttemptReceipts']+[str(archive)]
else:assert not args.resume_after_low_ram
state={'state':'PREPARING_FIXED_SMALL_ADAPTATION','pid':os.getpid(),'startedAt':now(),'priorAttemptReceipts':prior,'results':[],'automaticModelFailureRetries':0,'qualityQualified':False};atomic_json(target,state);child=None;owned=None
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']};env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe';stages=[('inventory','practical_qwen_native_worker_20261107.py',['--control',str(C),'--inventory-only'],C/'hip-inventory.json','PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL')]
for stage,passed in [('features','COMPLETE_FROZEN_FEATURES_AND_BASE_PARITY'),('probe','COMPLETE_REAL_GRADIENT_AND_RESOURCE_PROBE'),('train','COMPLETE_SMALL_HEAD_TRAINING_HELDOUT_ROOM_SELECTED'),('evaluate','COMPLETE_ADAPTER_SHORT_EVALUATION_REVIEW_REQUIRED')]:stages.append((stage,'target_activity_adaptation_worker_20261108.py',['--stage',stage],C/(stage+'-state.json'),passed))
try:
    for stage,module,extra,receipt,passed in stages:
        if stage=='evaluate' and (C/'training-selection-review.json').exists() and not read(C/'training-selection-review.json')['adaptedCheckpointImprovesSeparateRoomLoss']:
            state['state']='COMPLETE_ADAPTATION_REJECTED_NO_SEPARATE_ROOM_GAIN';break
        if receipt.exists() and read(receipt)['state']==passed:continue
        state['lastAvailableBytes']=psutil.virtual_memory().available
        if pressure.low():state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM';break
        if stage!='inventory':env['HIP_VISIBLE_DEVICES']=str(read(C/'hip-inventory.json')['selected']['ordinal'])
        command=[PY,str(S/module),*extra]
        if receipt.exists():assert stage!='inventory';command+=['--resume']
        peak=0;tick=time.perf_counter();point=None;progress_at=tick
        with (C/(stage+'-attempt-%04d.log'%(len(prior)+1))).open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);owned=psutil.Process(child.pid);owned.cpu_affinity([14,15]);state.update(state='RUNNING_SMALL_ADAPTATION_'+stage.upper(),activePid=child.pid);atomic_json(target,state)
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists();state['lastAvailableBytes']=psutil.virtual_memory().available
                if low or stop or time.perf_counter()-progress_at>600:state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY' if stop else 'STOPPED_PROGRESS_DEADLINE';stop_owned_family(child,owned);break
                try:
                    private=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,private);progress=read(receipt) if receipt.exists() else {};newpoint=(progress.get('state'),progress.get('completedInputs'),progress.get('newNeuralCalls'))
                    if newpoint!=point:point=newpoint;progress_at=time.perf_counter()
                    with (C/'resources.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps({'at':now(),'stage':stage,'privateBytes':private,'availableBytes':state['lastAvailableBytes'],'completedInputs':progress.get('completedInputs'),'newNeuralCalls':progress.get('newNeuralCalls')})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        state.pop('activePid',None);state['results'].append({'stage':stage,'exitCode':child.returncode,'wholeProcessFamilySeconds':time.perf_counter()-tick,'privatePeakBytes':peak});atomic_json(target,state)
        if child.returncode:
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_ADAPTATION_STAGE_RETAINED_NO_RETRY'
            break
        actual=read(receipt)['state']
        if stage=='train' and actual=='COMPLETE_SMALL_HEAD_NO_SEPARATE_ROOM_VALIDATION_GAIN':state['state']='COMPLETE_ADAPTATION_REJECTED_NO_SEPARATE_ROOM_GAIN';break
        assert actual==passed
    else:state['state']='COMPLETE_ADAPTATION_EVALUATION_REVIEW_REQUIRED'
except BaseException as error:state.update(state='ADAPTATION_CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,owned)
    pressure.close();state.pop('activePid',None);state.update(finishedAt=now());atomic_json(target,state);print(json.dumps(state,ensure_ascii=False),flush=True)
    if state['state']=='COMPLETE_ADAPTATION_EVALUATION_REVIEW_REQUIRED':atomic_json(C/'evaluation/run.json',{**state,'state':'COMPLETE_SHORT_ACTIVITY_CANDIDATE_REVIEW_REQUIRED','adapterReceiptBridgeOnly':True,'nativeRunState':state['state']})
