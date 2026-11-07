"""Run frozen full S/L sequentially only after the official short gate passes."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,shutil,subprocess,sys,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
p=argparse.ArgumentParser();p.add_argument('--resume-after-low-ram',action='store_true');a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=R/'docs/handoffs/20261107-model-generation-recovery';parent=base/'practical-qwen-native-r1';C=parent/'full';C.mkdir(exist_ok=True)
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe';SC='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
proof=read(parent/'short-native-state.json');assert proof['state']=='PASS_OFFICIAL_NATIVE_SHORT_EXECUTION_FULL_QUALITY_UNMEASURED'
assert proof['sourceSha256']==sha(Path(__file__).with_name('practical_qwen_native_worker_20261107.py'))
target=C/'run.json';prior=[]
if target.exists():
    assert a.resume_after_low_ram;old=read(target);assert old['state'] in ['STOPPED_ACTUAL_WINDOWS_LOW_RAM','DEFERRED_ACTUAL_WINDOWS_LOW_RAM'] and old.get('finishedAt') and not old.get('activePid')
    prior=old.get('priorAttemptReceipts',[]);archive=C/('attempt-%04d.json'%(len(prior)+1));assert not archive.exists();archive.write_bytes(target.read_bytes());prior=prior+[str(archive)]
else:
    assert not a.resume_after_low_ram
    cases=sorted(read(base/'practical-text-first-r1/audio-only.json'),key=lambda c:c['meeting'].startswith('L_'))
    atomic_json(C/'audio-only.json',cases);shutil.copyfile(base/'practical-text-first-r1/scoring-only.json',C/'scoring-only.json')
state={'state':'PREPARING_FROZEN_TWO_NATIVE_FULL_MEETINGS','pid':os.getpid(),'startedAt':now(),'priorAttemptReceipts':prior,'automaticRetries':0,'referencePassedToWorker':False,'qualityQualified':False,'results':[]}
atomic_json(target,state);pressure=SystemRamPressure();child=None;process=None
try:
    if prior and (C/'resources.jsonl').exists() and read(prior[-1])['results']:
        last=json.loads((C/'resources.jsonl').read_text().splitlines()[-1]);last_run=read(prior[-1]);peak=last_run['results'][-1]['sampledPrivatePeakBytes'];available=psutil.virtual_memory().available
        assert not pressure.low() and available>last['availableBytes']+2*peak,'Wait for actual external memory recovery; no unchanged reload'
        state['recoveryObservation']={'previousAvailableBytes':last['availableBytes'],'priorPrivatePeakBytes':peak,'currentAvailableBytes':available,'noFixedFreeRamFloor':True}
    for p in psutil.process_iter(['cmdline']):
        try:assert not any(Path(arg).name in ['practical_qwen_native_worker_20261107.py','practical_qwen_full_worker_20261107.py','practical_transcript_worker_20261107.py','practical_nemotron_worker_20261107.py','moss_night_gpu_worker_20261104.py'] for arg in p.info['cmdline'] or []),'Another native stage is still running'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
    env.update(HIP_VISIBLE_DEVICES=str(read(parent/'hip-inventory.json')['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    for index,case in enumerate(read(C/'audio-only.json')):
        name=case['meeting'];out=C/'transcripts'/name;completed=out/'completed-state.json';quality=out/'quality-review.json'
        old_seconds=sum(r['wholeProcessFamilySeconds'] for receipt in prior for r in read(receipt)['results'] if r['meeting']==name)
        if prior and completed.exists() and quality.exists() and read(completed).get('state')=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED':
            state['results'].append({'meeting':name,'exitCode':0,'wholeProcessFamilySeconds':0.,'accumulatedProcessFamilySeconds':old_seconds,'reusedCompleteMeeting':True,'qualityReview':read(quality)});atomic_json(target,state);continue
        if pressure.low():state['state']='DEFERRED_ACTUAL_WINDOWS_LOW_RAM';break
        tick=time.perf_counter();peak=0;last_committed=-1;progress_at=tick
        command=[PY,str(Path(__file__).with_name('practical_qwen_full_worker_20261107.py')),'--control',str(C),'--index',str(index)]+(['--resume'] if out.exists() else [])
        with (C/(name+'-attempt%d.log'%len(prior))).open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            process=psutil.Process(child.pid);process.cpu_affinity([14,15]);state.update(state='RUNNING_COMPLETE_OFFICIAL_NATIVE_ASR',activePid=child.pid,activeMeeting=name);atomic_json(target,state)
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists() or (parent/'stop.request').exists()
                progress=read(out/'state.json') if (out/'state.json').exists() else {}
                committed=progress.get('completedWindows',0)
                if committed>last_committed:last_committed=committed;progress_at=time.perf_counter()
                stalled=time.perf_counter()-progress_at>600
                if low or stop or stalled:
                    state.update(state='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY' if stop else 'STOPPED_NATIVE_WINDOW_CONTROL_DEADLINE');stop_owned_family(child,process);break
                try:
                    private=sum(p.memory_info().private for p in [process]+process.children(recursive=True));peak=max(peak,private)
                    with (C/'resources.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps({'at':now(),'meeting':name,'privateBytes':private,'availableBytes':psutil.virtual_memory().available,'completedWindows':committed})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        elapsed=time.perf_counter()-tick
        row={'meeting':name,'exitCode':child.returncode,'wholeProcessFamilySeconds':elapsed,'accumulatedProcessFamilySeconds':elapsed+old_seconds,'sampledPrivatePeakBytes':peak}
        state['results'].append(row);state.pop('activePid',None);state.pop('activeMeeting',None);atomic_json(target,state)
        if child.returncode or not completed.exists() or read(completed)['state']!='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED':
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_NATIVE_FULL_RETAINED_NO_AUTOMATIC_RETRY'
            break
        with (out/'scoring.log').open('xb') as log:
            row['scoringExitCode']=subprocess.run([SC,str(Path(__file__).with_name('score_practical_transcript_20261107.py')),'--control',str(C),'--meeting',name],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW).returncode
        if row['scoringExitCode']:state['state']='FAILED_EXITED_NATIVE_SCORING';break
        checker=Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe')
        assert sha(R/'companion-device-closure055/packages/meeting-transcript/src/lib.rs')=='f8f5b87017ebf10616b93d36520bab388f7e63033187bc289dfa1034b3af1684'
        check=subprocess.run([str(checker),str(out/'model-output.json'),str(round(case['audioSeconds']*1000))],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);assert check.returncode==0,check.stderr
        atomic_json(out/'product-contract.json',{'exitCode':check.returncode,'stdout':check.stdout,'installedAppOrPhonePassed':False})
        row.update(qualityReview=read(quality),actualProductDocumentContractPassed=True,newNeuralWindows=read(completed)['newNeuralWindows']);atomic_json(target,state)
    else:state['state']='COMPLETE_TWO_OFFICIAL_NATIVE_FULL_MEETINGS_REVIEW_REQUIRED'
except BaseException as error:
    state.update(state='CONTROLLER_ERROR_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,process)
    pressure.close();state.pop('activePid',None);state.pop('activeMeeting',None);state.update(finishedAt=now());atomic_json(target,state);print(json.dumps(state),flush=True)
