"""One-model CPU guard for the official native speaker candidate; no retries."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json,stop_owned_family
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--score',action='store_true');p.add_argument('--short-compatibility',action='store_true');p.add_argument('--native-control-proof');a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now().astimezone().isoformat(timespec='seconds');target=C/'native-run.json';assert not target.exists();cases=read(C/'audio-only.json')
worker=Path(__file__).with_name('practical_nemotron_worker_20261107.py')
if any(r['audioSeconds']>61 for r in cases):
    assert a.native_control_proof;proof=read(a.native_control_proof);assert proof['state']=='PASS_NATIVE61_FULL_STREAM_AND_CLI_BOUNDARY'
    assert proof['workerSourceSha256']==sha(worker) and proof['protocolNeuralBinding']=={k:v for k,v in read(C/'protocol.json').items() if k!='probabilityCacheRoot'}
state={'state':'PREPARING_NATIVE8','pid':os.getpid(),'startedAt':now(),'results':[],'automaticRetries':0,'referencePassedToWorker':False,'protocolSha256':sha(C/'protocol.json'),'workerSourceSha256':sha(worker)};save=lambda:atomic_json(target,state);save();pressure=SystemRamPressure();child=None;root=None
try:
    names=['moss_night_gpu_worker_20261104.py','practical_cpu_worker_20261107.py','practical_transcript_worker_20261107.py','bounded_speaker_20261107.py','practical_nemotron_worker_20261107.py','practical_nemotron_cli_control_20261107.py','nemo-speech.exe']
    for process in psutil.process_iter(['cmdline']):
        try:assert not any(Path(x).name in names for x in process.info['cmdline'] or []),'One neural model at a time'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    for index,case in enumerate(cases):
        for phase,module in [('activity','practical_nemotron_worker_20261107.py')]+([('cli-control','practical_nemotron_cli_control_20261107.py')] if a.short_compatibility else []):
            if pressure.low():state['state']='DEFERRED_NATIVE8_ACTUAL_LOW_RAM';break
            state.update(state='RUNNING_NATIVE8_'+phase.upper(),activeMeeting=case['meeting']);save();tick=time.perf_counter();peak=0
            with (C/(case['meeting']+'-'+phase+'.log')).open('xb') as log:
                child=subprocess.Popen([sys.executable,str(Path(__file__).with_name(module)),'--control',str(C),'--index',str(index)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS);root=psutil.Process(child.pid);root.cpu_affinity([12,13]);state['activePid']=child.pid;save()
                while child.poll() is None:
                    if pressure.low() or (C/'stop.request').exists():
                        stop_owned_family(child,root);state['state']='STOPPED_NATIVE8_LOW_RAM_OR_EXPLICIT_RETAINED';break
                    try:
                        family=[root]+root.children(recursive=True);private=sum(getattr(p.memory_info(),'private',0) for p in family);peak=max(peak,private)
                        with (C/'resources.jsonl').open('a',encoding='utf8') as file:file.write(json.dumps({'at':now(),'meeting':case['meeting'],'phase':phase,'privateBytes':private,'availableBytes':psutil.virtual_memory().available})+'\n')
                    except psutil.Error:pass
                    time.sleep(1)
            out=C/'results'/case['meeting'];receipt=read(out/('completed-state.json' if phase=='activity' else 'native-cli-control.json')) if (out/('completed-state.json' if phase=='activity' else 'native-cli-control.json')).exists() else {}
            row={'meeting':case['meeting'],'phase':phase,'exitCode':child.returncode,'workerState':receipt.get('state'),'wholeProcessFamilySeconds':time.perf_counter()-tick,'privatePeakBytes':peak};state['results'].append(row);state.pop('activePid',None);save()
            expected='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' if phase=='activity' else 'PASS_NATIVE61_C_ABI_AND_OFFICIAL_CLI_SEGMENTS'
            if child.returncode or receipt.get('state')!=expected:
                if not state['state'].startswith('STOPPED_'):state['state']='NATIVE8_INCOMPLETE_RETAINED_NO_AUTOMATIC_RETRY'
                break
        else:
            if a.score:
                case_score=next(x for x in read(C/'scoring-only.json') if x['meeting']==case['meeting']);atomic_json(out/'scoring-case.json',case_score)
                state.update(state='SCORING_EXITED_NATIVE8_FULL_JOURNAL');save()
                with (out/'scoring.log').open('xb') as log:code=subprocess.run(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),'--case',str(out/'scoring-case.json'),'--rttm',str(out/'predicted.rttm'),'--out',str(out/'review.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
                row['scoringExitCode']=code
                if code:state['state']='NATIVE8_SCORING_FAILED_OUTPUT_RETAINED';break
                row['qualityReview']=read(out/'review.json');save()
            continue
        break
    else:
        state['state']='COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED'
        if a.short_compatibility:
            receipt=read(C/'results'/cases[0]['meeting']/'completed-state.json');assert receipt['allOriginalAudioSamplesSubmitted'] and receipt['oneContinuousSpeakerState'] and receipt['newNeuralPushes']>=3
            atomic_json(C/'native-control-proof.json',{'state':'PASS_NATIVE61_FULL_STREAM_AND_CLI_BOUNDARY','workerSourceSha256':sha(worker),'protocolNeuralBinding':{k:v for k,v in read(C/'protocol.json').items() if k!='probabilityCacheRoot'},'officialCliAgreement':True,'continuous61Seconds':True,'speakerQualityQualified':False,'referenceInput':False})
except BaseException as error:state.update(state='NATIVE8_CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,root)
    pressure.close();state.pop('activePid',None);state.pop('activeMeeting',None);state['finishedAt']=now();save();print(json.dumps(state,ensure_ascii=False),flush=True)
