"""One guarded bounded-recovery pilot, then the same two complete meetings."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['pilot','full'],required=True);p.add_argument('--resume-after-low-ram',action='store_true');a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
P=read(C/'protocol.json');worker=Path(__file__).with_name('practical_qwen_checkpoint_worker_20261107.py');assert sha(worker)==P['workerSourceSha256']
PY='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
SC='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
folder=C/'full' if a.phase=='full' else C
target=folder/'run.json' if a.phase=='full' else C/'pilot-run.json';resources=folder/('resources.jsonl' if a.phase=='full' else 'pilot-resources.jsonl')
prior=[]
if target.exists():
    assert a.resume_after_low_ram;old=read(target)
    assert old['state'] in ['STOPPED_ACTUAL_WINDOWS_LOW_RAM','DEFERRED_ACTUAL_WINDOWS_LOW_RAM'] and old.get('finishedAt') and not old.get('activePid')
    last=json.loads(resources.read_text().splitlines()[-1]) if old['results'] else {'availableBytes':0};peak=old['results'][-1]['sampledPrivatePeakBytes'] if old['results'] else 0;available=psutil.virtual_memory().available
    pressure=SystemRamPressure();low=pressure.low();pressure.close()
    if low or available<=last['availableBytes']+peak:
        receipt=folder/('recovery-deferred-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
        atomic_json(receipt,{'state':'DEFERRED_ACTUAL_EXTERNAL_RAM_RECOVERY','noModelLaunched':True,'actualWindowsLowRam':low,'availableBytes':available,'lastAvailableBytes':last['availableBytes'],'previousOwnPrivatePeakBytes':peak});print(receipt);raise SystemExit(0)
    prior=old['priorAttemptReceipts'];archive=folder/((a.phase+'-attempt-%04d.json')%(len(prior)+1));assert not archive.exists();archive.write_bytes(target.read_bytes());prior=prior+[str(archive)]
else:assert not a.resume_after_low_ram
if a.phase=='full':
    pilot=read(C/'pilot/state.json');assert pilot['state']=='PASS_BOUNDED_NATIVE_PILOT_FULL_QUALITY_UNMEASURED' and pilot['binding']['protocolSha256']==sha(C/'protocol.json')
for process in psutil.process_iter(['cmdline']):
    try:assert not any(Path(arg).name in ['practical_qwen_checkpoint_worker_20261107.py','practical_qwen_bounded_worker_20261107.py','practical_qwen_full_worker_20261107.py','practical_qwen_native_worker_20261107.py','practical_transcript_worker_20261107.py','practical_nemotron_worker_20261107.py','moss_night_gpu_worker_20261104.py','companion_local_meeting_20261107.py'] for arg in process.info['cmdline'] or []),'Another model stage is still running'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
env.update(HIP_VISIBLE_DEVICES=str(read(Path(P['baseControl'])/'hip-inventory.json')['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
state={'state':'PREPARING_BOUNDED_NATIVE_'+a.phase.upper(),'pid':os.getpid(),'startedAt':now(),'priorAttemptReceipts':prior,'results':[],'referencePassedToWorker':False,'qualityQualified':False,'automaticModelFailureRetries':0}
atomic_json(target,state);pressure=SystemRamPressure();child=None;owned=None
try:
    cases=read(C/'audio-only.json') if a.phase=='full' else [{'meeting':'pilot'}]
    for index,case in enumerate(cases):
        if pressure.low():state['state']='DEFERRED_ACTUAL_WINDOWS_LOW_RAM';break
        name=case['meeting'];out=C/'full/transcripts'/name if a.phase=='full' else C/'pilot'
        command=[PY,str(worker),'--control',str(C),'--phase',a.phase,'--index',str(index)]+(['--resume'] if (out/'state.json').exists() else [])
        start=time.perf_counter();peak=0;last_progress=None;progress_at=start
        with (folder/(name+'-attempt%02d.log'%len(prior))).open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);owned.cpu_affinity([14,15]);state.update(state='RUNNING_BOUNDED_NATIVE_'+a.phase.upper(),activePid=child.pid,activeMeeting=name);atomic_json(target,state)
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists();progress=read(out/'state.json') if (out/'state.json').exists() else {}
                point=(progress.get('completedWindows'),progress.get('newNeuralCalls'))
                if point!=last_progress:last_progress=point;progress_at=time.perf_counter()
                if low or stop or time.perf_counter()-progress_at>600:
                    state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY' if stop else 'STOPPED_BOUNDED_CONTROL_DEADLINE';stop_owned_family(child,owned);break
                try:
                    private=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,private)
                    with resources.open('a',encoding='utf8') as stream:stream.write(json.dumps({'at':now(),'meeting':name,'availableBytes':psutil.virtual_memory().available,'privateBytes':private,'completedWindows':progress.get('completedWindows'),'newNeuralCalls':progress.get('newNeuralCalls')})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        elapsed=time.perf_counter()-start
        old_seconds=sum(row['wholeProcessFamilySeconds'] for p in prior for row in read(p)['results'] if row['meeting']==name)
        row={'meeting':name,'exitCode':child.returncode,'wholeProcessFamilySeconds':elapsed,'accumulatedProcessFamilySeconds':old_seconds+elapsed,'sampledPrivatePeakBytes':peak}
        state['results'].append(row);state.pop('activePid',None);state.pop('activeMeeting',None);atomic_json(target,state)
        if child.returncode:
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_BOUNDED_NATIVE_RETAINED_NO_AUTOMATIC_RETRY'
            break
        completed=read(out/'completed-state.json')
        if a.phase=='pilot':assert completed['state']=='PASS_BOUNDED_NATIVE_PILOT_FULL_QUALITY_UNMEASURED'
        else:
            assert completed['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
            if not (out/'quality-review.json').exists():
                with (out/'scoring.log').open('xb') as log:row['scoringExitCode']=subprocess.run([SC,str(Path(__file__).with_name('score_practical_transcript_20261107.py')),'--control',str(C/'full'),'--meeting',name],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW).returncode
                assert row['scoringExitCode']==0
            assert sha(R/'companion-device-closure055/packages/meeting-transcript/src/lib.rs')=='f8f5b87017ebf10616b93d36520bab388f7e63033187bc289dfa1034b3af1684'
            checker='E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe'
            check=subprocess.run([checker,str(out/'model-output.json'),str(round(case['audioSeconds']*1000))],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);assert check.returncode==0,check.stderr
            atomic_json(out/'product-contract.json',{'exitCode':check.returncode,'stdout':check.stdout,'installedAppOrPhonePassed':False})
            row.update(qualityReview=read(out/'quality-review.json'),actualProductDocumentContractPassed=True)
        atomic_json(target,state)
        if a.phase=='full' and name=='S_R004S03C01':
            rule=read(C/'comparison-rule.json');cer=row['qualityReview']['chronologicalTextDiagnostic']['cer']
            if cer>=rule['baselineStrictCer']:
                state.update(state='REJECTED_NATIVE17_NO_ORDINARY_ACCURACY_GAIN_COMPLEX_NOT_RUN',ordinaryCer=cer,predeclaredBaselineCer=rule['baselineStrictCer']);break
    else:state['state']='COMPLETE_BOUNDED_NATIVE_PILOT_REVIEW_REQUIRED' if a.phase=='pilot' else 'COMPLETE_TWO_BOUNDED_NATIVE_FULL_MEETINGS_REVIEW_REQUIRED'
except BaseException as error:
    state.update(state='BOUNDED_CONTROLLER_ERROR_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,owned)
    pressure.close();state.pop('activePid',None);state.pop('activeMeeting',None);state.update(finishedAt=now());atomic_json(target,state);print(json.dumps(state),flush=True)
