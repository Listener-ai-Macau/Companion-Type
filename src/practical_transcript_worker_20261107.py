"""Recoverable whole-audio baseline with native token timing and honest attribution."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_transcript_20261107 import align_window,normalized_journal
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--resume',action='store_true');p.add_argument('--text-only',action='store_true');p.add_argument('--cached-only',action='store_true');a=p.parse_args()
C=Path(a.control);read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));case=read(C/'audio-only.json')[a.index];protocol=read(C/'asr-protocol.json')
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);out=C/'transcripts'/case['meeting'];out.mkdir(parents=True,exist_ok=a.resume)
chunks=out/'windows';chunks.mkdir(exist_ok=a.resume)
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(path,value):
    if not atomic_json(path,value,progress=path.name=='state.json'):state['progressWriteDeferrals']=state.get('progressWriteDeferrals',0)+1
tick=time.perf_counter();state={'state':'LOADING_EXISTING_CPU_ASR','pid':os.getpid(),'startedAt':now(),'meeting':case['meeting'],'audioSha256':case['audioSha256'],'referencePassedToWorker':False,'gpuUsed':False,'completedWindows':0,'newNeuralWindows':0,'modelLoaded':False,'priorAttemptSeconds':0.,'limits':limits.query()}
if a.resume:
    old=read(out/'state.json');assert old['meeting']==case['meeting'] and old['audioSha256']==case['audioSha256']
    # A completed recognition may only be re-derived, never silently sent
    # through the neural recognizer after cleanup removes a committed file.
    if old.get('state')=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' or old.get('cachedOnly'):a.cached_only=True
    snapshot=out/('prior-state-'+sha(out/'state.json')[:12]+'.json')
    if not snapshot.exists():snapshot.write_bytes((out/'state.json').read_bytes())
    state['priorAttemptSeconds']=old.get('priorAttemptSeconds',0)+old.get('wholeWorkerSeconds',old.get('newAttemptSeconds',0))
    state['priorAttemptTimeIncomplete']=old.get('priorAttemptTimeIncomplete',False) or 'wholeWorkerSeconds' not in old
state['cachedOnly']=a.cached_only
write(out/'state.json',state)
try:
    assert sha(case['audio'])==case['audioSha256']
    journal_file=C/'results'/case['meeting']/'speaker-journal.json'
    journal={'segments':[]};journal_sha=None;speaker_display_map={}
    if not a.text_only:
        journal=read(journal_file);producer=read(journal_file.parent/'completed-state.json')
        assert producer['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' and producer['finishedAt']
        assert journal['audioSha256']==case['audioSha256'] and journal['audioSeconds']==case['audioSeconds']
        journal_sha=sha(journal_file);assert journal_sha==protocol['speakerJournals'][case['meeting']]
        journal,speaker_display_map=normalized_journal(journal)
    binding={'audioSha256':case['audioSha256'],'protocolSha256':sha(C/'asr-protocol.json'),'journalSha256':journal_sha,'workerSha256':sha(__file__),'attributionSha256':sha(Path(__file__).with_name('practical_transcript_20261107.py'))}
    use_itn=protocol.get('useItn',True)
    assert type(use_itn) is bool,'useItn must be an explicit boolean when present'
    raw_binding={'audioSha256':case['audioSha256'],'modelFiles':protocol['modelFiles'],'runtimeVersion':protocol['runtimeVersion'],'nativeExtensionSha256':protocol['nativeExtensionSha256'],'windowSamples':protocol['maximumWindowSamples'],'language':'zh','useItn':use_itn,'provider':'cpu','numThreads':1}
    canonical=lambda obj:json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')
    for record in protocol['modelFiles'].values():assert sha(record['file'])==record['sha256']
    rec=None
    raw_windows=[];utterances=[];estimated_tokens=[];reused=0
    with wave.open(case['audio'],'rb') as audio:
        assert audio.getnchannels()==1 and audio.getsampwidth()==2 and audio.getframerate()==16000
        count=audio.getnframes();assert abs(count/16000-case['audioSeconds'])<1/16000
        size=protocol['maximumWindowSamples'];assert size==30*16000
        state.update(state='TRANSCRIBING_FULL_AUDIO',audioSeconds=count/16000,totalWindows=(count+size-1)//size)
        for index,start in enumerate(range(0,count,size)):
            if (C/'stop.request').exists():raise InterruptedError('Explicit stop requested')
            end=min(count,start+size);file=chunks/('%06d.json'%index);raw_file=chunks/('%06d.raw.json'%index)
            if raw_file.exists():
                assert a.resume;packet=read(raw_file);assert packet['binding']==raw_binding
                raw=packet['raw'];assert hashlib.sha256(canonical(raw)).hexdigest()==packet['rawSha256'],'Durable raw ASR changed'
                assert raw['index']==index and raw['startSample']==start and raw['endSample']==end;reused+=1
            else:
                assert not a.cached_only,'Completed raw ASR cache is missing; no new model was loaded. Original audio/results retained.'
                if rec is None:
                    import numpy as np,sherpa_onnx
                    import sherpa_onnx.lib._sherpa_onnx as native
                    assert sherpa_onnx.__version__==protocol['runtimeVersion'] and sha(native.__file__)==protocol['nativeExtensionSha256']
                    before_load=time.perf_counter()
                    rec=sherpa_onnx.OfflineRecognizer.from_sense_voice(model=protocol['modelFiles']['model.int8.onnx']['file'],tokens=protocol['modelFiles']['tokens.txt']['file'],num_threads=1,provider='cpu',language='zh',use_itn=use_itn)
                    state['modelLoaded']=True
                    state['modelLoadSeconds']=time.perf_counter()-before_load
                audio.setpos(start);samples=np.frombuffer(audio.readframes(end-start),dtype='<i2').astype(np.float32)/32768
                assert len(samples)==end-start
                stream=rec.create_stream();stream.accept_waveform(16000,samples);before=time.perf_counter();rec.decode_stream(stream)
                result=stream.result
                raw={'index':index,'startSample':start,'endSample':end,'text':result.text,'tokens':list(result.tokens),'timestamps':list(result.timestamps),'durations':list(getattr(result,'durations',[])),'nativeResult':str(result),'inferenceSeconds':time.perf_counter()-before}
                write(raw_file,{'binding':raw_binding,'originalNeuralWorkerSha256':sha(__file__),'raw':raw,'rawSha256':hashlib.sha256(canonical(raw)).hexdigest()});state['newNeuralWindows']+=1
            try:aligned=align_window(raw,journal['segments'],audio_seconds=count/16000)
            except ValueError as error:
                aligned={'alignmentAvailable':False,'nativeTimingFailure':str(error),'rawText':raw['text'],'tokenEstimates':[],'utterances':([{'text':raw['text'],'startMs':round(start/16),'endMs':round(end/16),'speaker':None,'approximateTiming':True,'attribution':'native_timing_invalid_preserve_full_window'}] if raw['text'] else [])}
                state['invalidNativeTimingWindows']=state.get('invalidNativeTimingWindows',0)+1
            packet={'binding':binding,'raw':raw,'aligned':aligned}
            if file.exists():
                previous=read(file)
                if previous!=packet:
                    archive=file.with_name(file.stem+'-p-'+sha(file)[:12]+'.json')
                    if not archive.exists():archive.write_bytes(file.read_bytes())
                    else:assert sha(archive)==sha(file),'Archive prefix collision; original results retained'
            write(file,packet)
            raw_windows.append(raw);utterances.extend(aligned['utterances']);estimated_tokens.extend(aligned['tokenEstimates'])
            state.update(completedWindows=index+1,reusedDurableWindows=reused,completedSample=end,newAttemptSeconds=time.perf_counter()-tick,limits=limits.query());write(out/'state.json',state)
    assert raw_windows and raw_windows[0]['startSample']==0 and raw_windows[-1]['endSample']==count
    assert all(x['endSample']==y['startSample'] for x,y in zip(raw_windows,raw_windows[1:]))
    assert ''.join(r['text'] for r in raw_windows)==''.join(r['text'] for r in utterances)
    document={'isFinal':True,'text':'\n'.join(r['text'] for r in raw_windows),'utterances':[{k:r[k] for k in ['text','startMs','endMs','speaker','approximateTiming']} for r in utterances]}
    write(out/'model-output.json',document)
    review={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'binding':binding,'allOriginalAudioSamplesCoveredOnce':True,'rawWindowCount':len(raw_windows),'rawWindowText':'\n'.join(r['text'] for r in raw_windows),'allTextPreservedThroughAttribution':True,'tokenEstimates':estimated_tokens,'utterancesWithAttribution':utterances,'unconfirmedTokens':sum(r['speaker'] is None for r in estimated_tokens),'overlapTokensRequiringRecovery':sum(r['overlapDetectedNearOnset'] for r in estimated_tokens),'scope':'Completed baseline, not quality qualified. Full original audio retained. Native token onsets only; unknown boundaries/overlaps must be reviewed, both overlapping voices are not recovered. No real names/roles or verified word duration.'}
    review['nativeToConsecutiveDisplaySpeakerIds']=speaker_display_map
    write(out/'attribution-review.json',review)
    state.update(state='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED',speakerJournalPending=a.text_only,modelLoaded=rec is not None,allAudioSamplesCoveredOnce=True,allAsrTextPreserved=True,unconfirmedTokens=review['unconfirmedTokens'],overlapTokensRequiringRecovery=review['overlapTokensRequiringRecovery'],modelOutputSha256=sha(out/'model-output.json'),attributionReviewSha256=sha(out/'attribution-review.json'))
except BaseException as error:
    state.update(state='FAILED_RETAINED_RESUMABLE',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());write(out/'state.json',state);write(out/'completed-state.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)
