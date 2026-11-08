"""One owned GPU training stage; observe safely and retain all failed attempts."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from independent_progress_reader_20261108 import read_progress
from moss_windows_resource_limits_20261104 import SystemRamPressure
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--worker',required=True);parser.add_argument('--run-id',required=True);parser.add_argument('--expected',required=True);args=parser.parse_args();C=Path(args.control);S=Path(__file__).parent;P=json.loads(Path(args.protocol).read_text(encoding='utf8'));target=C/(args.run_id+'-controller.json');assert not target.exists();now=lambda:datetime.now().astimezone().isoformat(timespec='seconds');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));pressure=SystemRamPressure();child=root=None
state={'state':'PREPARING_TSE_STAGE','pid':os.getpid(),'startedAt':now(),'worker':args.worker,'runId':args.run_id,'protocolSha256':hashlib.sha256(Path(args.protocol).read_bytes()).hexdigest(),'automaticModelRetries':0,'privatePeakBytes':0,'rssPeakBytes':0,'qualityQualified':False};save=lambda:atomic_json(target,state);save();tick=time.perf_counter()
try:
    for p in psutil.process_iter(['cmdline']):
        try:assert not any(str(a).replace('\\','/').lower().startswith(str(S).replace('\\','/').lower()+'/') and '_worker_' in Path(str(a)).name for a in p.info['cmdline'] or []),'Only one owned neural stage'
        except psutil.Error:pass
    if pressure.low():state.update(state='DEFERRED_ACTUAL_WINDOWS_LOW_RAM',availableAtStopBytes=psutil.virtual_memory().available)
    else:
        env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe';inventory=C/'hip-inventory.json'
        if not inventory.exists():
            with (C/'inventory.log').open('xb') as f:code=subprocess.run([PY,str(S/'practical_qwen_native_worker_20261107.py'),'--control',str(C),'--inventory-only'],env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
            assert code==0
        actual=read(inventory);assert actual['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL';env['HIP_VISIBLE_DEVICES']=str(actual['selected']['ordinal'])
        with (C/(args.run_id+'.log')).open('xb') as f:
            child=subprocess.Popen([PY,str(S/args.worker),'--control',str(C),'--protocol',args.protocol,'--run-id',args.run_id],env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS);root=psutil.Process(child.pid);root.cpu_affinity([12,13,14,15]);state.update(state='RUNNING_TSE_STAGE',activePid=child.pid);save();previous={};lastpoint=None;changed=time.perf_counter();receipt=C/args.run_id/'state.json'
            while child.poll() is None:
                low=pressure.low()
                if low or (C/'stop.request').exists() or time.perf_counter()-changed>600:
                    state.update(state='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_OWNER_OR_PROGRESS_TIMEOUT',availableAtStopBytes=psutil.virtual_memory().available);stop_owned_family(child,root);break
                progress,issue=read_progress(receipt,previous);previous=progress;point=(progress.get('state'),progress.get('newWeightUpdates'),progress.get('gradientCases'),progress.get('completedInputs'),len(progress.get('checks',{})))
                if point!=lastpoint:lastpoint=point;changed=time.perf_counter()
                try:
                    members=[root]+root.children(recursive=True);private=sum(x.memory_info().private for x in members);rss=sum(x.memory_info().rss for x in members);state['privatePeakBytes']=max(state['privatePeakBytes'],private);state['rssPeakBytes']=max(state['rssPeakBytes'],rss)
                    with (C/(args.run_id+'-resources.jsonl')).open('a',encoding='utf8') as output:output.write(json.dumps({'at':now(),'privateBytes':private,'rssBytes':rss,'availableBytes':psutil.virtual_memory().available,'progress':point,'observationIssue':issue})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        state['exitCode']=child.returncode
        if not state['state'].startswith('STOPPED_'):
            outcome=read(receipt) if receipt.exists() else {};state.update(state='COMPLETE_TSE_STAGE_REVIEW_REQUIRED' if child.returncode==0 and outcome.get('state')==args.expected else 'FAILED_TSE_STAGE_RETAINED_NO_AUTOMATIC_RETRY',workerState=outcome.get('state'))
except BaseException as error:state.update(state='TSE_CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,root)
    pressure.close();state.pop('activePid',None);state.update(finishedAt=now(),wholeProcessFamilySeconds=time.perf_counter()-tick);save();print(json.dumps(state),flush=True)
