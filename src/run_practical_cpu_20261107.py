"""One whole meeting at a time; actual low RAM stops only our child family."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json,stop_owned_family
p=argparse.ArgumentParser();p.add_argument('--control',required=True);args=p.parse_args();C=Path(args.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
protocol=read(C/'protocol.json');cases=read(C/'audio-only.json');scoring=read(C/'scoring-only.json');target=C/'run.json';assert not target.exists()
state={'state':'PREPARING','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'pid':os.getpid(),'results':[],'protocolSha256':sha(C/'protocol.json'),'sourceSha256':{name:sha(Path(__file__).with_name(name)) for name in ['practical_cpu_worker_20261107.py','run_practical_cpu_20261107.py','moss_windows_resource_limits_20261104.py','score_cross_corpus_diarization_20261103.py','reference_textgrid_20261104.py']},'referencePassedToInference':False,'automaticRetries':0}
def save():
    atomic_json(target,state)
save();pressure=SystemRamPressure();psutil.cpu_percent(interval=None);child=None;family_root=None
try:
    for proc in psutil.process_iter(['cmdline','name']):
        try:
            assert not any(Path(arg).name in ['moss_night_gpu_worker_20261104.py','practical_cpu_worker_20261107.py'] for arg in proc.info['cmdline'] or []),'One model at a time'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    for index,case in enumerate(cases):
        if pressure.low():state['state']='DEFERRED_ACTUAL_WINDOWS_LOW_RAM';break
        if (C/'stop.request').exists():state['state']='STOPPED_EXPLICITLY_BEFORE_NEXT_MEETING';break
        out=C/'results'/case['meeting'];tick=time.perf_counter();peak_private=0;peak_rss=0
        with (C/(case['meeting']+'.log')).open('xb') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('practical_cpu_worker_20261107.py')),'--control',str(C),'--index',str(index)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            family_root=psutil.Process(child.pid);family_root.cpu_affinity(protocol['runtime']['affinity'])
            state.update(state='RUNNING_COMPLETE_MEETING_DIARIZATION',activeMeeting=case['meeting'],activePid=child.pid);save()
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists()
                if low or stop:
                    try:owned=family_root.children(recursive=True)+[family_root]
                    except psutil.NoSuchProcess:owned=[]
                    for member in reversed(owned):
                        try:member.terminate()
                        except psutil.NoSuchProcess:pass
                    psutil.wait_procs(owned,timeout=2);child.wait(timeout=3)
                    state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY';save();break
                try:
                    family=[family_root]+family_root.children(recursive=True);rss=0;private=0;cpu=0.
                    for member in family:
                        info=member.memory_info();rss+=info.rss;private+=getattr(info,'private',0);times=member.cpu_times();cpu+=times.user+times.system
                    peak_private=max(peak_private,private);peak_rss=max(peak_rss,rss)
                    with (C/'resources.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps({'at':datetime.now().astimezone().isoformat(timespec='seconds'),'meeting':case['meeting'],'privateBytes':private,'rssBytes':rss,'familyCpuSeconds':cpu,'systemCpuPercent':psutil.cpu_percent(interval=None),'availableBytes':psutil.virtual_memory().available})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        worker=read(out/'completed-state.json') if (out/'completed-state.json').exists() else read(out/'state.json') if (out/'state.json').exists() else {}
        row={'meeting':case['meeting'],'exitCode':child.returncode,'workerState':worker.get('state'),'wholeProcessFamilySeconds':time.perf_counter()-tick,'privatePeakBytes':peak_private,'rssPeakBytes':peak_rss,'output':str(out)}
        state['results'].append(row);state.pop('activePid',None);state.pop('activeMeeting',None);save()
        if child.returncode or worker.get('state')!='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':
            if not state['state'].startswith('STOPPED_'):state['state']='STOPPED_INCOMPLETE_NO_AUTOMATIC_RETRY'
            save();break
        state.update(state='SCORING_EXITED_SPEAKER_JOURNAL');save()
        frozen=next(r for r in scoring if r['meeting']==case['meeting']);(out/'scoring-case.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        score_python='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
        with (out/'scoring.log').open('xb') as log:
            done=subprocess.run([score_python,str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),'--case',str(out/'scoring-case.json'),'--rttm',str(out/'predicted.rttm'),'--out',str(out/'review.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        row['scoringExitCode']=done.returncode
        if done.returncode:state['state']='SCORING_FAILED_RETAINED';save();break
        review=read(out/'review.json');row.update(der=review['components']['diarization error rate'],predictedSpeakers=review['predictedSpeakers'],referenceSpeakers=review['referenceSpeakers'],uncoveredReferenceSpeakers=review['uncoveredReferenceSpeakers'],macroAttributionRecall=review['macroReferenceAttributionRecall']);save()
    else:state['state']='TWO_COMPLETE_CPU_MEETINGS_SCORED_REVIEW_REQUIRED'
except BaseException as error:
    state.update(state='CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:state['ownWorkerReleasedOnControllerFailure']=stop_owned_family(child,family_root)
    pressure.close();state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'));state.pop('activePid',None);state.pop('activeMeeting',None);save();print(json.dumps(state,ensure_ascii=False),flush=True)
