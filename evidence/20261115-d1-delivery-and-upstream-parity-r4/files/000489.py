"""Serial model stages, durable receipts and real system RAM-pressure cancellation."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from independent_progress_reader_20261108 import read_progress
from moss_windows_resource_limits_20261104 import SystemRamPressure
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-joint-neural-spatial');S=Path(__file__).parent
def read(p):
    for attempt in range(8):
        try:return json.loads(Path(p).read_text(encoding='utf8'))
        except OSError as e:
            if getattr(e,'winerror',None) not in (5,32,33) or attempt==7:raise
            time.sleep(min(.01*2**attempt,.2))
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
parser=argparse.ArgumentParser();parser.add_argument('--resume-after-low-ram',action='store_true');args=parser.parse_args();pressure=SystemRamPressure();target=C/'run-r2.json';prior=[]
for process in psutil.process_iter(['cmdline']):
    try:assert not any(str(x).replace('\\','/').lower().startswith(str(S).replace('\\','/').lower()+'/') and '_worker_' in Path(str(x)).name for x in process.info['cmdline'] or []),'Another owned neural worker is active'
    except psutil.Error:pass
if target.exists():
    old=read(target);assert args.resume_after_low_ram and old['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM'
    assert not pressure.low() and psutil.virtual_memory().available>old['availableAtStopBytes']+old['stoppedOwnPeakPrivateBytes'],'Wait for external RAM recovery'
    archive=C/('run-attempt-%04d.json'%(len(old['priorAttemptReceipts'])+1));assert not archive.exists();archive.write_bytes(target.read_bytes());prior=old['priorAttemptReceipts']+[str(archive)]
else:assert not args.resume_after_low_ram
state={'state':'PREPARING_SINGLE_JOINT_MASK_CANDIDATE','pid':os.getpid(),'startedAt':now(),'results':[],'priorAttemptReceipts':prior,'automaticModelFailureRetries':0,'referenceInput':False,'controllerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'qualityQualified':False};child=owned=None
save=lambda:atomic_json(target,state)
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe';SC='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']};env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
stages=[('inventory',PY,'practical_qwen_native_worker_20261107.py',['--control',str(C),'--inventory-only'],C/'hip-inventory.json','PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'),('cue',PY,'joint_neural_spatial_cue_worker_20261108.py',[],C/'cue-state.json','COMPLETE_ALL_KNOWN_SPEAKER_CUES_UNQUALIFIED'),('spatial',SC,'joint_neural_spatial_beam_worker_20261108.py',[],C/'separation-state-r2.json','COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT'),('asr',PY,'joint_neural_spatial_asr_worker_20261108.py',['--stage','asr'],C/'asr-state-r2.json','COMPLETE_DUAL_MIC_FIXED_ASR_NOT_PRODUCT')]
save()
try:
    for phase,python,module,extra,receipt,passed in stages:
        if receipt.exists() and read(receipt)['state']==passed:continue
        if pressure.low():state.update(state='STOPPED_ACTUAL_WINDOWS_LOW_RAM',availableAtStopBytes=psutil.virtual_memory().available,stoppedOwnPeakPrivateBytes=0);break
        if phase in ['cue','asr']:env['HIP_VISIBLE_DEVICES']=str(read(C/'hip-inventory.json')['selected']['ordinal'])
        command=[python,str(S/module),*extra]
        if receipt.exists():assert phase!='inventory';command.append('--resume')
        peak=0;rss_peak=0;start=time.perf_counter();progress_at=start;lastpoint=None;observation={};state.update(state='RUNNING_JOINT_'+phase.upper(),stage=phase);save()
        try:
            with (C/(phase+'-attempt-%04d.log'%(len(prior)+1))).open('xb') as log:
                child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS);owned=psutil.Process(child.pid);owned.cpu_affinity([12,13,14,15]);state['activePid']=child.pid;save()
                while child.poll() is None:
                    low=pressure.low()
                    if low or (C/'stop.request').exists() or time.perf_counter()-progress_at>600:
                        state.update(state='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICIT_OR_PROGRESS_DEADLINE',availableAtStopBytes=psutil.virtual_memory().available,stoppedOwnPeakPrivateBytes=peak);stop_owned_family(child,owned);break
                    progress,issue=read_progress(receipt,observation);observation=progress;point=(progress.get('state'),progress.get('completedInputs'),progress.get('newNeuralCalls'),progress.get('newAlgorithmCalls'),progress.get('reusedOutputs'))
                    if point!=lastpoint:lastpoint=point;progress_at=time.perf_counter()
                    try:
                        members=[owned]+owned.children(recursive=True);private=sum(x.memory_info().private for x in members);rss=sum(x.memory_info().rss for x in members);peak=max(peak,private);rss_peak=max(rss_peak,rss)
                        with (C/'resources.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps({'at':now(),'phase':phase,'privateBytes':private,'rssBytes':rss,'availableBytes':psutil.virtual_memory().available,'progress':point,'observationIssue':issue})+'\n')
                    except psutil.Error:pass
                    time.sleep(1)
        finally:
            if child is not None and child.poll() is None:stop_owned_family(child,owned)
            state.pop('activePid',None);state['results'].append({'stage':phase,'exitCode':child.returncode if child else None,'wholeProcessFamilySeconds':time.perf_counter()-start,'privatePeakBytes':peak,'rssPeakBytes':rss_peak});save()
        if child.returncode or not receipt.exists() or read(receipt)['state']!=passed:
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_JOINT_STAGE_RETAINED_NO_MODEL_RETRY'
            break
    else:state['state']='COMPLETE_SINGLE_JOINT_CANDIDATE_REVIEW_REQUIRED'
except BaseException as error:state.update(state='JOINT_CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,owned)
    pressure.close();state.update(finishedAt=now());state.pop('activePid',None);save();print(json.dumps(state),flush=True)
