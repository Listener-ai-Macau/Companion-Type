"""Staged whole-meeting speaker comparison with durable neural checkpoints."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json,stop_owned_family
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--score',action='store_true');p.add_argument('--native-control-proof');a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
target=C/'bounded-run.json';assert not target.exists();cases=read(C/'audio-only.json');P=read(C/'protocol.json')
if any(case['audioSeconds']>30 for case in cases):
    assert a.native_control_proof,'Actual affected native short comparison required before full meeting'
    proof=read(a.native_control_proof);assert proof['state']=='PASS_NATIVE_SHORT_DIARIZATION_WITH_BOUNDED_VOTES'
    assert proof['workerSourceSha256']==sha(Path(__file__).with_name('bounded_speaker_20261107.py')) and proof['ioSourceSha256']==sha(Path(__file__).with_name('practical_io_20261107.py'))
state={'state':'PREPARING','startedAt':now(),'pid':os.getpid(),'results':[],'referencePassedToInference':False,'automaticRetries':0,'protocolSha256':sha(C/'protocol.json'),'sourceSha256':{n:sha(Path(__file__).with_name(n)) for n in ['bounded_speaker_20261107.py','run_bounded_speaker_20261107.py','practical_io_20261107.py','moss_windows_resource_limits_20261104.py']}}
save=lambda:atomic_json(target,state)
save();pressure=SystemRamPressure();child=None;root=None
try:
    for process in psutil.process_iter(['cmdline']):
        try:assert not any(Path(arg).name in ['moss_night_gpu_worker_20261104.py','practical_cpu_worker_20261107.py','practical_transcript_worker_20261107.py','bounded_speaker_20261107.py'] for arg in process.info['cmdline'] or []),'One model at a time'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    for index,case in enumerate(cases):
        for stage in ['segment','embed','reconstruct']:
            if pressure.low():state['state']='DEFERRED_ACTUAL_LOW_RAM_NEURAL_CACHE_RETAINED';break
            if (C/'stop.request').exists():state['state']='STOPPED_EXPLICITLY_CACHE_RETAINED';break
            state.update(state='RUNNING_'+stage.upper(),activeMeeting=case['meeting']);save();tick=time.perf_counter();private_peak=0;rss_peak=0
            with (C/(case['meeting']+'-'+stage+'.log')).open('xb') as log:
                child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('bounded_speaker_20261107.py')),'--control',str(C),'--index',str(index),'--stage',stage],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                root=psutil.Process(child.pid);root.cpu_affinity([12,13]);state['activePid']=child.pid;save()
                while child.poll() is None:
                    low=pressure.low();stop=(C/'stop.request').exists()
                    if low or stop:
                        stop_owned_family(child,root);state['state']='STOPPED_ACTUAL_LOW_RAM_NEURAL_CACHE_RETAINED' if low else 'STOPPED_EXPLICITLY_CACHE_RETAINED';save();break
                    try:
                        family=[root]+root.children(recursive=True);private=sum(getattr(p.memory_info(),'private',0) for p in family);rss=sum(p.memory_info().rss for p in family);private_peak=max(private_peak,private);rss_peak=max(rss_peak,rss)
                        with (C/'resources.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps({'at':now(),'stage':stage,'meeting':case['meeting'],'privateBytes':private,'rssBytes':rss,'availableBytes':psutil.virtual_memory().available})+'\n')
                    except psutil.Error:pass
                    time.sleep(1)
            output=C/'results'/case['meeting'];receipt=output/(stage+'-state.json');worker=read(receipt) if receipt.exists() else {}
            row={'meeting':case['meeting'],'stage':stage,'exitCode':child.returncode,'workerState':worker.get('state'),'wholeProcessFamilySeconds':time.perf_counter()-tick,'privatePeakBytes':private_peak,'rssPeakBytes':rss_peak,'receipt':str(receipt),'newNeuralItems':worker.get('newNeuralItems'),'reusedCachedPrefix':worker.get('reusedCachedPrefix')}
            state['results'].append(row);state.pop('activePid',None);save()
            expected={'segment':'COMPLETE_SEGMENTATION_CACHE','embed':'COMPLETE_EMBEDDING_CACHE','reconstruct':'COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED'}[stage]
            if child.returncode or worker.get('state')!=expected:
                if not state['state'].startswith('STOPPED_'):state['state']='STAGE_INCOMPLETE_NEURAL_CACHE_RETAINED'
                break
        else:
            if a.score:
                frozen=next(r for r in read(C/'scoring-only.json') if r['meeting']==case['meeting']);atomic_json(output/'scoring-case.json',frozen)
                state['state']='SCORING_EXITED_COMPLETE_JOURNAL';save()
                with (output/'scoring.log').open('xb') as log:
                    code=subprocess.run(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),'--case',str(output/'scoring-case.json'),'--rttm',str(output/'predicted.rttm'),'--out',str(output/'review.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS).returncode
                row['scoringExitCode']=code
                if code:state['state']='SCORING_FAILED_JOURNAL_RETAINED';break
                row['qualityReview']=read(output/'review.json');save()
            continue
        break
    else:state['state']='COMPLETE_BOUNDED_SPEAKER_BATCH_REVIEW_REQUIRED'
except BaseException as error:
    state.update(state='CONTROLLER_FAILURE_CACHE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,root)
    pressure.close();state.pop('activePid',None);state.pop('activeMeeting',None);state['finishedAt']=now();save();print(json.dumps(state,ensure_ascii=False),flush=True)
