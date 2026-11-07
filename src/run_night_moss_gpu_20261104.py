"""Run one declared reference-free audio manifest, one native GPU model at a time."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,psutil,subprocess,time
from moss_windows_resource_limits_20261104 import SystemRamPressure

parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--run-name',required=True);parser.add_argument('--protocol')
parser.add_argument('--control-root',help='Isolated experiment control directory; defaults to the original night batch')
parser.add_argument('--continue-timing-invalid-screening',action='store_true',help='Research screening only: preserve timing failures but continue other cases when EOS/text parsing completed')
parser.add_argument('--output-suffix',default='',help='New output namespace; never overwrite a failed earlier attempt')
args=parser.parse_args()
root=Path(args.control_root) if args.control_root else Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
if (root/'stop.request').exists():
 raise SystemExit('GPU experiment is paused: stop.request exists; no worker started')
inputs=Path(args.inputs);cases=json.loads(inputs.read_text(encoding='utf8'))
protocol=Path(args.protocol) if args.protocol else root/'frozen-protocol-gpu.json';settings=json.loads(protocol.read_text(encoding='utf8'))
target=root/(args.run_name+'.json');assert not target.exists(),'Preserve prior run receipts'
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
state={'state':'RUNNING_NATIVE_GPU_MODEL','startedAt':now(),'protocolSha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
 'inputManifestSha256':hashlib.sha256(inputs.read_bytes()).hexdigest(),'results':[],'referencePassedToWorker':False}
def save():
 p=target.with_suffix('.tmp');p.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');p.replace(target)
env={k:v for k,v in os.environ.items() if not k.startswith(('COMPANION_','LISTENER_','OPENAI_','DEEPSEEK_','VOLC_','HF_TOKEN','HUGGING_FACE_HUB_TOKEN','PYTHONPATH'))}
cache=Path(settings['runtime'].get('rebuildableCacheRoot',str(root)))
env.update(HF_HOME=str(cache/'hf-cache'),HF_MODULES_CACHE=str(cache/'hf-modules'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
 HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HUB_DISABLE_PROGRESS_BARS='1',OMP_NUM_THREADS='2',
 MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMBA_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',
 PYTHONUNBUFFERED='1',HIP_CACHE_DIR=str(cache/'hip-cache'),TRITON_CACHE_DIR=str(cache/'triton-cache'))
if 'hipVisibleDeviceOrdinal' in settings['runtime']:
 ordinal=settings['runtime']['hipVisibleDeviceOrdinal']
 assert type(ordinal) is int and 0<=ordinal<16,'Declared physical GPU ordinal only'
 for key in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','HIP_VISIBLE_DEVICES']:env.pop(key,None)
 env['HIP_VISIBLE_DEVICES']=str(ordinal)
save();psutil.cpu_percent(interval=None);ram_pressure=SystemRamPressure()
try:
 for index,case in enumerate(cases):
  if ram_pressure.low():
   state['state']='DEFERRED_WINDOWS_LOW_SYSTEM_RAM_NO_WORKER_STARTED';break
  if (root/'stop.request').exists():
   state['state']='PAUSED_BEFORE_NEXT_WORKER_EXPLICIT_REQUEST';break
  assert not any('reference' in k.lower() for k in case),'Worker audio manifest must not contain reference fields'
  name=case['meeting'];output_name=name+args.output_suffix
  assert all(c.isalnum() or c in '._-' for c in output_name),'Plain output name required'
  assert not (root/'results'/output_name).exists(),'Never overwrite a prior model output'
  start=time.perf_counter();peak=0;cpu=0.;memory_peak=0
  with (root/(output_name+'.log')).open('xb') as log:
   child=subprocess.Popen([settings['runtime']['python'],str(Path(__file__).with_name('moss_night_gpu_worker_20261104.py')),
    '--index',str(index),'--protocol',str(protocol),'--inputs',str(inputs),'--output-name',output_name],env=env,stdout=log,stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   process=psutil.Process(child.pid);process.cpu_affinity(settings['runtime']['affinity'])
   state.update(activeMeeting=name,activePid=child.pid);save()
   while child.poll() is None:
    explicit_stop=(root/'stop.request').exists();low_ram=ram_pressure.low()
    if explicit_stop or low_ram:
     # Stop only this Popen's verified descendants, never other Python/apps.
     # Worker job handles also close on termination, releasing model children.
     try:owned=process.children(recursive=True)+[process]
     except psutil.NoSuchProcess:owned=[]
     for member in reversed(owned):
      try:member.terminate()
      except psutil.NoSuchProcess:pass
     psutil.wait_procs(owned,timeout=2)
     child.wait(timeout=3)
     state['state']='STOPPED_DURING_WORKER_EXPLICIT_REQUEST' if explicit_stop else 'STOPPED_DURING_WORKER_WINDOWS_LOW_SYSTEM_RAM'
     state['stopReason']='Owner explicit request' if explicit_stop else 'Windows LowMemoryResourceNotification signaled; release only this experiment family'
     save();break
    try:
     family=[process]+process.children(recursive=True);rss=0;private=0;family_cpu=0
     for member in family:
      if not member.is_running():continue
      info=member.memory_info();rss+=info.rss;private+=getattr(info,'private',0)
      times=member.cpu_times();family_cpu+=times.user+times.system
     peak=max(peak,rss);memory_peak=max(memory_peak,private);cpu=max(cpu,family_cpu)
     with (root/(args.run_name+'-resources.jsonl')).open('a',encoding='utf8') as out:
      out.write(json.dumps({'at':now(),'meeting':name,'processFamilyRssBytes':rss,'processFamilyPrivateBytes':private,
       'processFamilyCpuSeconds':family_cpu,'systemCpuPercent':psutil.cpu_percent(interval=None),
       'availableMemoryBytes':psutil.virtual_memory().available})+'\n')
    except psutil.Error:pass
    time.sleep(1)
  receipt=root/'results'/output_name/'completed-state.json'
  actual=json.loads(receipt.read_text(encoding='utf8')) if receipt.exists() else {'state':'FAILED_BEFORE_RECEIPT'}
  result={'meeting':name,'exitCode':child.returncode,'workerState':actual['state'],'wholeProcessFamilySeconds':round(time.perf_counter()-start,6),
   'observedProcessFamilyPeakRssBytes':peak,'observedProcessFamilyPeakPrivateBytes':memory_peak,
   'processFamilyCpuSeconds':cpu,'receipt':str(receipt),'smokeOnly':bool(case.get('smokeOnly'))}
  state['results'].append(result);state.pop('activePid',None);save();print(json.dumps(result),flush=True)
  if state['state'] in ['STOPPED_DURING_WORKER_EXPLICIT_REQUEST','STOPPED_DURING_WORKER_WINDOWS_LOW_SYSTEM_RAM']:break
  timing_diagnostic=bool(args.continue_timing_invalid_screening and case.get('screeningOnly') and child.returncode==0
   and actual['state']=='OUTPUT_RETAINED_INCOMPLETE_OR_INVALID' and actual.get('eosCompleted')
   and actual.get('allGeneratedTextParsed') and actual.get('invalidNativeTimeRows'))
  if timing_diagnostic:
   result['timingInvalidDiagnosticOnly']=True;save()
  if child.returncode!=0 or (actual['state']!='COMPLETE_JOINT_CANDIDATE_UNQUALIFIED' and not timing_diagnostic):
   state['state']='STOPPED_WITH_NATIVE_MODEL_FAILURE_EVIDENCE' if child.returncode else 'STOPPED_WITH_INVALID_OUTPUT_EVIDENCE';break
  if (root/'stop.request').exists():state['state']='STOPPED_AFTER_SAVED_OUTPUT_EXPLICIT_REQUEST';break
 else:state['state']=('DIAGNOSTIC_QUEUE_FINISHED_WITH_INVALID_TIMING_NOT_QUALIFIED'
  if any(x.get('timingInvalidDiagnosticOnly') for x in state['results']) else 'COMPLETE_GPU_INFERENCE_SCORING_REQUIRED')
except BaseException as error:
 state.update(state='GPU_SUPERVISOR_FAILURE_RETAINED',error=repr(error));raise
finally:
 ram_pressure.close()
 state.update(finishedAt=now());state.pop('activePid',None);state.pop('activeMeeting',None);save()
print(json.dumps({'state':state['state'],'receipt':str(target)}),flush=True)
