"""One frozen public full-meeting experiment, exited scoring and preservation; no retries."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess,sys,time,traceback
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';base=R/'docs/handoffs/20261107-model-generation-recovery';C=base/'native8-f16-full-r1';T=base/'practical-text-first-r1'
sys.path.insert(0,str(M/'src'))
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
target=C/'chain-state.json';assert not target.exists()
state={'state':'RUNNING_NATIVE8_FULL_MEETING_CHAIN','startedAt':now(),'pid':os.getpid(),'automaticRetries':0,'textSource':str(T),'results':[],'qualityQualified':False};save=lambda:atomic_json(target,state)
def command(args,log):
    with Path(log).open('xb') as stream:
        return subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS).returncode
save()
try:
    code=command([sys.executable,str(M/'src/run_practical_nemotron_20261107.py'),'--control',str(C),'--score','--native-control-proof',str(base/'native8-f16-smoke-r1/native-control-proof.json')],C/'speaker-controller.log')
    state['speakerControllerExitCode']=code;batch=read(C/'native-run.json');state['speakerBatchState']=batch['state'];save()
    if code or batch['state']!='COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED':
        state['state']='INCOMPLETE_SPEAKER_BATCH_CACHES_RETAINED';raise RuntimeError('Full speaker batch incomplete; no automatic retry')
    cases=read(C/'audio-only.json');protocol=read(T/'asr-protocol.json');protocol['speakerJournals']={r['meeting']:sha(C/'results'/r['meeting']/'speaker-journal.json') for r in cases}
    protocol['scope']='Full public audio raw ASR reused without neural inference; anonymous stable speaker activity only, uncertain/overlap text remains unknown.'
    atomic_json(C/'asr-protocol.json',protocol)
    prior={r['meeting']:r for r in read(T/'transcript-run.json')['results']}
    validator=Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe')
    for index,case in enumerate(cases):
        source=T/'transcripts'/case['meeting'];out=C/'transcripts'/case['meeting'];assert not out.exists()
        shutil.copytree(source,out,ignore=shutil.ignore_patterns('quality-review.json','scoring.log'))
        raw_files=list((out/'windows').glob('*.raw.json'));raw_hashes={f.name:sha(f) for f in raw_files};assert len(raw_files)==read(source/'completed-state.json')['totalWindows']
        state.update(state='ATTRIBUTING_SAVED_RAW_TEXT_NO_NEW_NEURAL_INFERENCE',activeMeeting=case['meeting']);save();tick=time.perf_counter()
        code=command([sys.executable,str(M/'src/practical_transcript_worker_20261107.py'),'--control',str(C),'--index',str(index),'--resume'],out/'retag.log')
        receipt=read(out/'completed-state.json');assert code==0 and receipt['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
        assert receipt['newNeuralWindows']==0 and receipt['modelLoaded'] is False and not receipt['speakerJournalPending']
        assert all(sha(out/'windows'/name)==digest for name,digest in raw_hashes.items()),'Original neural output must stay unchanged'
        assert read(out/'attribution-review.json')['rawWindowText']==read(source/'attribution-review.json')['rawWindowText']
        retag_seconds=time.perf_counter()-tick
        check=subprocess.run([str(validator),str(out/'model-output.json'),str(round(case['audioSeconds']*1000))],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        atomic_json(out/'product-contract-proof.json',{'exitCode':check.returncode,'stdout':check.stdout,'stderr':check.stderr,'validatorSha256':sha(validator),'modelOutputSha256':sha(out/'model-output.json')});assert check.returncode==0
        score=command(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(M/'src/score_practical_transcript_20261107.py'),'--control',str(C),'--meeting',case['meeting']],out/'scoring.log');assert score==0
        review=read(out/'quality-review.json');speaker_seconds=sum(r['wholeProcessFamilySeconds'] for r in batch['results'] if r['meeting']==case['meeting'])
        row={'meeting':case['meeting'],'originalAsrProcessFamilySeconds':prior[case['meeting']]['accumulatedProcessFamilySeconds'],'speakerProcessFamilySeconds':speaker_seconds,'cacheAttributionProcessSeconds':retag_seconds,'accumulatedOwnedProcessSeconds':prior[case['meeting']]['accumulatedProcessFamilySeconds']+speaker_seconds+retag_seconds,'elapsedWaitingAndMinutesNotIncluded':True,'newAsrNeuralWindows':0,'originalRawFilesUnchanged':True,'allOriginalWordsPreserved':True,'productContractPassed':True,'chronologicalDiagnosticCer':review['chronologicalTextDiagnostic']['cer'],'cpCerDiagnostic':review['anonymousStreamCpCerDiagnostic'],'unconfirmedSpeakerText':review['unconfirmedSpeakerText'],'speakerActivity':review['speakerActivityReview'],'qualityQualified':False}
        state['results'].append(row);save()
    state['state']='COMPLETE_TWO_MEETING_CANDIDATE_QUALITY_REVIEW_REQUIRED'
except BaseException as error:
    if state['state']!='INCOMPLETE_SPEAKER_BATCH_CACHES_RETAINED':state['state']='FAILED_CHAIN_RESULTS_RETAINED'
    state.update(error=repr(error),traceback=traceback.format_exc())
finally:
    state.pop('activeMeeting',None);state['finishedAt']=now();save()
    phase='finished' if state['state']=='COMPLETE_TWO_MEETING_CANDIDATE_QUALITY_REVIEW_REQUIRED' else 'failed'
    state['preservationExitCode']=command([sys.executable,str(Path(__file__).with_name('preserve_practical_progress_20261107.py')),'--phase',phase],C/'preservation.log');save()
    print(json.dumps(state,ensure_ascii=False),flush=True)
