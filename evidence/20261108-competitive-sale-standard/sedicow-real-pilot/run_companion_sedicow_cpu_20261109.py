"""Freeze one target before launch; monitor only our child, no nested CPU job."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,subprocess,sys,time
import psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'docs/handoffs/20261109-sedicow-r1';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=argparse.ArgumentParser();p.add_argument('--target',default='native-1',choices=['native-1','native-2','native-3']);p.add_argument('--control',default=str(R/'docs/handoffs/20261109-sedicow-cpu-r1'));p.add_argument('--inputs-json',default=str(S/'audio-only-inputs.json'));a=p.parse_args();C=Path(a.control);C.mkdir(exist_ok=False);worker=M/'src/companion_sedicow_cpu_worker_20261109.py';job=next(j for j in read(a.inputs_json) if j['id']==a.target);write(C/'audio-only.json',job)
assert read(S/'cpu-stream-probe.json')['state']=='PASS_TINY_STREAMED_EAGER_EXACT_SDPA_TOLERANCE'
support=[M/'src'/name for name in ['companion_sedicow_cpu_stream_20261109.py','companion_sedicow_checkpoint_20261109.py','companion_sedicow_decode_trace_20261109.py','moss_windows_resource_limits_20261104.py','practical_io_20261107.py','practical_qwen_bounded_decode_20261107.py']]
protocol={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'workerSha256':sha(worker),'controllerSha256':sha(__file__),'supportSources':[{'file':str(p),'sha256':sha(p)} for p in support],'sourceManifest':str(S/'source.json'),'sourceManifestSha256':sha(S/'source.json'),'weightFile':read(S/'weight-download.json')['weightFile'],'isolatedRuntime':'E:/CodexData/Companion/.model-cache/sedicow-runtime-20261109','inputManifestSha256':sha(C/'audio-only.json'),'inputListManifest':str(Path(a.inputs_json)),'inputListManifestSha256':sha(a.inputs_json),'policy':'One fixedreal30s target chosen frompredeclared1/2/3 before newoutput. Read originalF32checkpoint byencoderblock+keepdecoderresident, everytensorhashchecked; no quantization/training/audioalteration, no referencewords/peoplecount. SDPAattention isexecutionbackend change (tinymax5.96e-8vs eager), notbitexactfullpretrainedclaim. AuthorCTCgenerationweight0 modulesnotallocated, guarded against accidentaluse. Worker5percentCPU/2GiBprivate; actualLOWRAM controllerstops ownchild. No GPUoperations, no fullmeeting orproductionlatencyclaim.','targetSelectionReason':'Alltargets are originalpredeclaredpilot1/2/3. Native2 alsochosen foroneauthorbinarymaskcounterfactual aftersoftconditioned outputwronglanguage; no words/oracleactivity used in any modelinputs.','maximumRunSeconds':300,'referencePassedToInference':False,'saleQualified':False};write(C/'protocol.json',protocol)
pressure=SystemRamPressure();child=None;root=None;start=time.perf_counter();state={'state':'PREFLIGHT','newNeuralCalls':0,'privatePeakBytes':0,'controllerHasCpuRateJob':False,'target':a.target,'saleQualified':False}
def save():state['wallSeconds']=time.perf_counter()-start;write(C/'controller.json',state)
try:
 if pressure.low():state['state']='DEFERRED_ACTUAL_WINDOWS_LOWRAM';save();raise SystemExit(0)
 with (C/'worker.log').open('xb') as log:
  child=subprocess.Popen([sys.executable,str(worker),'--control',str(C)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);root=psutil.Process(child.pid);state.update(state='RUNNING',pid=child.pid);save()
  while child.poll() is None:
   low=pressure.low()
   if low or time.perf_counter()-start>protocol['maximumRunSeconds']:stop_owned_family(child,root);state['state']='STOPPED_ACTUAL_WINDOWS_LOWRAM' if low else 'STOPPED_BOUNDED_TIME';break
   try:
    private=root.memory_info().private;state['privatePeakBytes']=max(state['privatePeakBytes'],private)
    if private>2*1024**3:stop_owned_family(child,root);state['state']='STOPPED_PRIVATE_MEMORY_BUDGET';break
   except psutil.Error:pass
   save();time.sleep(1)
 state['exitCode']=child.returncode;worker_state=read(C/'state.json') if (C/'state.json').exists() else {};state.update(workerState=worker_state.get('state'),newNeuralCalls=worker_state.get('newNeuralCalls',0))
 if state['state']=='RUNNING':state['state']='COMPLETE' if child.returncode==0 and worker_state.get('state')=='COMPLETE_REAL_CPU_TARGET_ASR_NOT_QUALIFIED' else 'FAILED'
finally:
 if child is not None and child.poll() is None:stop_owned_family(child,root)
 save();print(json.dumps(state,ensure_ascii=False),flush=True)
