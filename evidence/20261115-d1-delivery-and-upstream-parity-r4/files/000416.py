"""Real complete-utterance text-supervised TSE pairs, not four-second frame labels.

Official TRAIN material only, separate train/validation sessions, paired physical
mic0/1 retained. This is a training-input pilot, not a trained or accepted model.
"""
from pathlib import Path
from datetime import datetime
from collections import Counter
import concurrent.futures,hashlib,json,math,os,random,sys,time,urllib.request,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');OLD=R/'docs/handoffs/20261108-target-activity-adaptation';C=R/'docs/handoffs/20261108-joint-neural-spatial';E=Path('E:/CodexData/Companion/.model-cache/joint-neural-spatial-20261108/training-pairs')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def fetch(source):
    meeting=source['meeting'];size=source['fileSize'];digest=source['expectedWholeFileLfsSha256'];dest=E/'sources'/(meeting+'.flac');dest.parent.mkdir(exist_ok=True)
    if dest.exists():assert dest.stat().st_size==size and sha(dest)==digest;return dest
    width=(size+3)//4;folder=E/'ranges'/meeting;folder.mkdir(parents=True,exist_ok=True)
    def part(index):
        a=index*width;b=min(size,a+width)-1;path=folder/(str(index)+'.part');expected=b-a+1
        for attempt in range(4):
            offset=path.stat().st_size if path.exists() else 0
            if offset==expected:return path
            assert 0<=offset<expected
            req=urllib.request.Request(source['url']+f'?download=true&pair_range={a+offset}-{b}',headers={'Range':f'bytes={a+offset}-{b}','Accept-Encoding':'identity','User-Agent':'Companion-real-train-complete-utterance'})
            try:
                with urllib.request.urlopen(req,timeout=45) as response:
                    assert response.status==206 and response.headers.get('Content-Range')==f'bytes {a+offset}-{b}/{size}'
                    with path.open('ab') as out:
                        remaining=expected-offset
                        while remaining:
                            data=response.read(min(1024**2,remaining));assert data;out.write(data);remaining-=len(data)
                        out.flush();os.fsync(out.fileno())
                assert path.stat().st_size==expected;return path
            except Exception:
                if attempt==3:raise
                time.sleep(min(2**attempt,4))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:parts=list(pool.map(part,range(4)))
    assembled=dest.with_suffix('.assembled.part')
    with assembled.open('wb') as out:
        for p in parts:
            with p.open('rb') as f:
                while data:=f.read(1024**2):out.write(data)
        out.flush();os.fsync(out.fileno())
    assert assembled.stat().st_size==size and sha(assembled)==digest;os.replace(assembled,dest)
    # Only redundant transfer fragments in this exact owned source folder.
    for p in parts:assert p.resolve().parent==folder.resolve() and p.name in ['0.part','1.part','2.part','3.part'];p.unlink()
    return dest
def overlap(a,b,c,d):return max(0,min(b,d)-max(a,c))
def main():
    limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2);E.mkdir(exist_ok=True);target=C/'training-pair-preparation.json';assert not target.exists();tick=time.perf_counter()
    sources=read(OLD/'selected-training-sources.json');old_audio=read(OLD/'prepared-audio.json');profile_map={(x['meeting'],x['person']):x for x in old_audio if x['kind']=='profile'}
    forbidden={'L_R003S01C02','S_R004S03C01','M_R003S02C01','S_R003S01C01','L_R003S03C02'};assert all(s['meeting'] not in forbidden and s['sourceSubset'].startswith('train_') for s in sources)
    state={'state':'PREPARING_REAL_TRAIN_COMPLETE_UTTERANCE_PAIRS','startedAt':datetime.now().astimezone().isoformat(),'sourceSelection':'Reuse three previously verified official train sources:two train_L training sessions and one separate train_S validation session. No benchmark/final holdout enters training. This is still a limited pilot, not a general training corpus.','selectionSeed':20261108,'maximumPairsPerPersonPerCategory':4,'targetSecondsMinimum':0.2,'querySecondsMaximum':15,'newModelCalls':0,'newTrainingRuns':0,'sources':[],'pairs':[],'missingCategoryCoverage':[]};atomic_json(target,state)
    sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools');import soundfile as sf
    for source in sources:
        assert sha(source['reference'])==source['referenceSha256'];truth=[x for x in read_reference_intervals(source['reference']) if normalize(x['text'])];people=sorted({x['speaker'] for x in truth});file=fetch(source);meeting=source['meeting'];meeting_pairs=[]
        with sf.SoundFile(str(file)) as audio:
            assert audio.samplerate==16000 and audio.channels==8 and audio.subtype=='PCM_16';seconds=audio.frames/16000
            for person in people:
                profile=profile_map[(meeting,person)];assert sha(profile['audio'])==profile['audioSha256'];profile_lo,profile_hi=profile['startSample']/16000,profile['endSample']/16000
                candidates={'present_solo':[],'present_overlap':[],'absent_other_speech':[]};seen=set()
                for utterance in truth:
                    a=max(0.,utterance['start']-.25);b=min(seconds,utterance['end']+.25)
                    if b-a<2:a=max(0,a-(2-(b-a))/2);b=min(seconds,max(b,a+2))
                    # Expand to contain every target utterance touching the
                    # query. Never attach a full sentence outside its audio.
                    for _ in range(12):
                        touching=[x for x in truth if x['speaker']==person and x['end']>a and x['start']<b]
                        aa=max(0.,min([a]+[x['start']-.05 for x in touching]));bb=min(seconds,max([b]+[x['end']+.05 for x in touching]))
                        if abs(aa-a)+abs(bb-b)<1e-8:break
                        a,b=aa,bb
                    if b-a>15 or overlap(a,b,profile_lo,profile_hi)>0:continue
                    lo,hi=math.floor(a*16000),math.ceil(b*16000);key=(lo,hi)
                    if key in seen:continue
                    seen.add(key);targets=[x for x in truth if x['speaker']==person and overlap(a,b,x['start'],x['end'])>0]
                    if any(x['start']<lo/16000-1e-6 or x['end']>hi/16000+1e-6 for x in targets):continue
                    other=[x for x in truth if x['speaker']!=person and overlap(a,b,x['start'],x['end'])>0]
                    if not targets:
                        if sum(overlap(a,b,x['start'],x['end']) for x in other)<1:continue
                        category='absent_other_speech'
                    else:
                        if sum(overlap(a,b,x['start'],x['end']) for x in targets)<.2:continue
                        is_overlap=any(overlap(x['start'],x['end'],y['start'],y['end'])>0 for x in targets for y in other);category='present_overlap' if is_overlap else 'present_solo'
                    candidates[category].append({'startSample':lo,'endSample':hi,'targets':targets,'otherSpeechPresent':bool(other),'nonTargetSpeechElsewhereInQuery':bool(other)})
                for category,pool in candidates.items():
                    random.Random(int(hashlib.sha256(f'20261108/{meeting}/{person}/{category}'.encode()).hexdigest()[:16],16)).shuffle(pool);selected=pool[:4]
                    if len(selected)<4:state['missingCategoryCoverage'].append({'meeting':meeting,'person':person,'category':category,'available':len(pool),'selected':len(selected),'notSynthesizedOrDuplicated':True})
                    for index,row in enumerate(selected):
                        identity=f'{meeting}-{person}-{category}-{index}';dest=E/(identity+'-mic01.wav');audio.seek(row['startSample']);pcm=audio.read(row['endSample']-row['startSample'],dtype='int16',always_2d=True);assert len(pcm)==row['endSample']-row['startSample']
                        with wave.open(str(dest),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm[:,:2].astype('<i2',copy=False).tobytes())
                        transcript=''.join(x['text'] for x in sorted(row['targets'],key=lambda x:(x['start'],x['end'])));assert bool(normalize(transcript))==(category!='absent_other_speech')
                        packet={'id':identity,'role':source['role'],'meeting':meeting,'targetPersonForSupervisedTrainingOnly':person,'category':category,'audio':str(dest),'audioSha256':sha(dest),'audioSeconds':len(pcm)/16000,'sourceStartSample':row['startSample'],'sourceEndSample':row['endSample'],'sourceWholeFlacSha256':source['expectedWholeFileLfsSha256'],'sourceWholeFlacHashVerified':True,'sourcePhysicalChannels':[0,1],'sampleRate':16000,'profileAudio':profile['audio'],'profileAudioSha256':profile['audioSha256'],'profileSourceStartSample':profile['startSample'],'profileSourceEndSample':profile['endSample'],'queryAndProfileDisjoint':True,'referenceTranscriptForTrainingOnly':transcript,'targetUtterancesForTrainingOnly':row['targets'],'targetTranscriptEntirelyInsideAudio':True,'targetWaveformAvailable':category=='absent_other_speech' or (category=='present_solo' and not row['nonTargetSpeechElsewhereInQuery']),'targetWaveformMeaning':'Exact zero is valid only for annotated lexical target absence; originalmic0 is an unprocessed noisy target only when no other annotated speech occurs anywhere in this query. Real-overlap examples have text supervision only, not fabricated clean target waveforms.','sourceReferenceSha256':source['referenceSha256'],'notDeploymentReferenceInput':True}
                        meeting_pairs.append(packet)
        state['pairs']+=meeting_pairs;state['sources'].append({'meeting':meeting,'role':source['role'],'file':str(file),'wholeSha256':source['expectedWholeFileLfsSha256'],'originalSeconds':seconds,'pairs':len(meeting_pairs)});atomic_json(target,state);print(json.dumps({'meeting':meeting,'pairs':len(meeting_pairs),'wholeSourceHashVerified':True}),flush=True)
    training={x['meeting'] for x in state['pairs'] if x['role']=='train'};validation={x['meeting'] for x in state['pairs'] if x['role']=='validation'};assert training.isdisjoint(validation)
    summary={'state':'COMPLETE_TEXT_ALIGNED_REAL_TRAINING_INPUT_PILOT_NOT_TRAINED_MODEL','pairs':len(state['pairs']),'counts':dict(Counter(x['role']+'/'+x['category'] for x in state['pairs'])),'audioSecondsIncludingRepeatedQueryPairs':sum(x['audioSeconds'] for x in state['pairs']),'distinctSourceAudioWindows':len({(x['meeting'],x['sourceStartSample'],x['sourceEndSample']) for x in state['pairs']}),'trainingMeetings':sorted(training),'validationMeetings':sorted(validation),'originalBenchmarkAndFinalHoldoutUsedForTraining':False,'physicalSpeakerIndependenceEstablished':False,'completeTargetSentencesInsideQuery':True,'cleanTargetWaveformsForRealOverlap':False,'newTrainingRuns':0,'modelAccuracyImprovementDemonstrated':False,'readiness':'Ready as bounded text-supervised TSE training/gradient input pilot. Not enough for a general production model; expand real training sessions/rooms and define actual waveform or differentiable ASR-proxy supervision before a substantive training run. Do not repeat the old4s-frame-head microtraining or treat a train-loss drop as acceptance.'}
    atomic_json(C/'training-pair-manifest.json',state['pairs']);atomic_json(C/'training-readiness.json',summary);state.update(state=summary['state'],finishedAt=datetime.now().astimezone().isoformat(),wholePreparationSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
