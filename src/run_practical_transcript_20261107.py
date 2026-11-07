"""Consume exited journals, run existing ASR sequentially, then score and retain."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json,stop_owned_family
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--wait-for-diarization',action='store_true');a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
target=C/'transcript-run.json';assert not target.exists()
state={'state':'WAITING_FOR_EXITED_DIARIZATION','startedAt':now(),'pid':os.getpid(),'automaticRetries':0,'referencePassedToInference':False,'results':[]}
def save():
    atomic_json(target,state)
save();pressure=SystemRamPressure();psutil.cpu_percent(interval=None);child=None;root=None
try:
    if a.wait_for_diarization:
        # Poll only this concrete model job; no scheduler or unrelated process.
        while True:
            prior=read(C/'run.json')
            if prior.get('finishedAt'):break
            process=psutil.Process(prior['pid'])
            assert any(Path(arg).name=='run_practical_cpu_20261107.py' for arg in process.cmdline()),'Original producer no longer exists'
            if (C/'stop.request').exists():raise InterruptedError('Explicit stop while awaiting producer')
            time.sleep(2)
    prior=read(C/'run.json');assert prior['state']=='TWO_COMPLETE_CPU_MEETINGS_SCORED_REVIEW_REQUIRED' and prior['finishedAt'],'No transcript launch after an incomplete producer'
    cases=read(C/'audio-only.json');probe=read(C/'asr-smoke.json');assert probe['state']=='EXISTING_ASR_CONTROL_COMPLETE'
    protocol={'runtimeVersion':probe['runtime'],'nativeExtensionSha256':read(C/'protocol.json')['runtime']['nativeExtensionSha256'],'modelFiles':probe['modelFiles'],'maximumWindowSamples':30*16000,'provider':'cpu','language':'zh','useItn':True,'modelOrHotwordsChanged':False,'speakerJournals':{case['meeting']:sha(C/'results'/case['meeting']/'speaker-journal.json') for case in cases},'onsetUncertaintyMarginSeconds':.06,'scope':'Existing SenseVoice baseline on complete disjoint30s windows, preserving every input sample. Per-token estimated-onset attribution; unknown/overlap is unconfirmed. No forced participant count or real names. No reference read by worker.'}
    assert not (C/'asr-protocol.json').exists();(C/'asr-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    state['sourceSha256']={p.name:sha(p) for p in Path(__file__).parent.glob('*practical_transcript*20261107.py')};state['sourceSha256']['practical_io_20261107.py']=sha(Path(__file__).with_name('practical_io_20261107.py'));state['protocolSha256']=sha(C/'asr-protocol.json');save()
    for index,case in enumerate(cases):
        if pressure.low():state['state']='DEFERRED_ACTUAL_WINDOWS_LOW_RAM';break
        if (C/'stop.request').exists():state['state']='STOPPED_EXPLICITLY';break
        state.update(state='RUNNING_COMPLETE_CPU_TRANSCRIPT',activeMeeting=case['meeting']);save();started=time.perf_counter();private_peak=0;rss_peak=0
        with (C/(case['meeting']+'-transcript.log')).open('xb') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('practical_transcript_worker_20261107.py')),'--control',str(C),'--index',str(index)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            root=psutil.Process(child.pid);root.cpu_affinity([12,13]);state['activePid']=child.pid;save()
            while child.poll() is None:
                low=pressure.low();stop=(C/'stop.request').exists()
                if low or stop:
                    try:owned=root.children(recursive=True)+[root]
                    except psutil.NoSuchProcess:owned=[]
                    for process in reversed(owned):
                        try:process.terminate()
                        except psutil.NoSuchProcess:pass
                    psutil.wait_procs(owned,timeout=2);child.wait(timeout=3);state['state']='STOPPED_ACTUAL_WINDOWS_LOW_RAM' if low else 'STOPPED_EXPLICITLY';save();break
                try:
                    family=[root]+root.children(recursive=True);private=0;rss=0;cpu=0
                    for process in family:
                        info=process.memory_info();private+=getattr(info,'private',0);rss+=info.rss;ts=process.cpu_times();cpu+=ts.user+ts.system
                    private_peak=max(private_peak,private);rss_peak=max(rss_peak,rss)
                    with (C/'transcript-resources.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps({'at':now(),'meeting':case['meeting'],'privateBytes':private,'rssBytes':rss,'familyCpuSeconds':cpu,'systemCpuPercent':psutil.cpu_percent(interval=None),'availableBytes':psutil.virtual_memory().available})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        out=C/'transcripts'/case['meeting'];worker=read(out/'completed-state.json') if (out/'completed-state.json').exists() else {}
        row={'meeting':case['meeting'],'exitCode':child.returncode,'wholeProcessFamilySeconds':time.perf_counter()-started,'privatePeakBytes':private_peak,'rssPeakBytes':rss_peak,'workerState':worker.get('state'),'output':str(out)}
        state['results'].append(row);state.pop('activePid',None);state.pop('activeMeeting',None);save()
        if child.returncode or worker.get('state')!='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED':
            if not state['state'].startswith('STOPPED_'):state['state']='STOPPED_INCOMPLETE_NO_AUTOMATIC_RETRY'
            break
        state['state']='SCORING_EXITED_COMPLETE_TRANSCRIPT';save()
        with (out/'scoring.log').open('xb') as log:
            code=subprocess.run(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(Path(__file__).with_name('score_practical_transcript_20261107.py')),'--control',str(C),'--meeting',case['meeting']],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS).returncode
        row['scoringExitCode']=code
        if code:state['state']='SCORING_FAILED_RETAINED';break
        review=read(out/'quality-review.json');row.update(chronologicalDiagnosticCer=review['chronologicalTextDiagnostic']['cer'],cpCerDiagnostic=review['anonymousStreamCpCerDiagnostic']['characterErrorRate'],unconfirmedTextFraction=review['unconfirmedSpeakerText']['fractionOfRecognizedCharacters']);save()
    else:state['state']='TWO_COMPLETE_CPU_TRANSCRIPTS_SCORED_REVIEW_REQUIRED'
except BaseException as error:
    state.update(state='CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:state['ownWorkerReleasedOnControllerFailure']=stop_owned_family(child,root)
    pressure.close();state.update(finishedAt=now());state.pop('activePid',None);state.pop('activeMeeting',None);save();print(json.dumps(state,ensure_ascii=False),flush=True)
