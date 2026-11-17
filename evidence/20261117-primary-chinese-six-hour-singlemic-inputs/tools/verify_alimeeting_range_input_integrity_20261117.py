"""Independent original-label/PCM/split checks for the acquired training dataset."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict,Counter
import csv,hashlib,json,re,sys,time,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from reference_textgrid_20261104 import read_reference_intervals
from durable_model_state_20261117 import atomic_json
from alimeeting_public_oss_20261117 import PublicAliTrainingStore
import psutil
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';C=O/'range-training-cohort-r2';A=C/'acquisition-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(C/'protocol.json');done=read(A/'completed.json')
assert done['state']=='COMPLETE5027_ORIGINAL_SINGLE_MIC_CHINESE_TRAIN_INPUTS_PENDING_INDEPENDENT_INTEGRITY'
assert done['protocolSha256']==sha(C/'protocol.json') and sha(done['manifest'])==done['manifestSha256']
original_selection=[json.loads(l) for l in Path(P['selectedManifest']).read_text(encoding='utf-8').splitlines()]
rows=[json.loads(l) for l in Path(done['manifest']).read_text(encoding='utf-8').splitlines()]
assert len(rows)==len(original_selection)==5027
assert [r['id'] for r in rows]==[r['id'] for r in original_selection]
out=C/'integrity-r1';out.mkdir();pressure=SystemRamPressure();began=time.monotonic()
state={'at':datetime.now().astimezone().isoformat(),'state':'VERIFYING_ORIGINAL_CHINESE_TRAIN_INPUTS',
    'sourceSha256':sha(__file__),'verifiedExamples':0,'verifiedFrames':0,
    'newNeuralCalls':0,'parameterUpdates':0,'evaluationTextOrAudioRead':False,'qualityQualified':False}
def save():
    state.update(observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
def stop():
    assert not pressure.low() and psutil.virtual_memory().available>=3414499000,'Original RAM floor'
    assert time.monotonic()-began<600 and not(out/'stop.request').exists(),'Bounded data integrity cutoff'
save()
try:
    split=read(P['participantProof']);assert not split['intersection']
    train_people=set(split['trainingGlobalSpeakerIds']);eval_people=set(split['evaluationGlobalSpeakerIds'])
    source_files={Path(r['Text:FILE']).stem:r['Audio:FILE'] for r in csv.DictReader((O/'Train_Ali_far.csv').open(encoding='utf-8-sig'))}
    excluded={r['meeting'] for r in P['sourceQualityExclusion']}
    original={};speech={};original_sha={}
    first_source=P['existingVerifiedFirstMono']
    assert sha(first_source['output'])==first_source['outputSha256']
    assert first_source['sourceFullMd5']==P['sourceCatalog']['R0003_M0046']['etag'].lower()
    for meeting in sorted({r['meeting'] for r in rows}):
        path=O/'original-textgrids'/(meeting+'.TextGrid');source_rows=read_reference_intervals(path)
        original[meeting]=source_rows;original_sha[meeting]=sha(path);speech[meeting]=[]
        for r in source_rows:
            if not r['text'] or r['start']>=r['end']:continue
            speaker=r['speaker'].split('SPK')[-1]
            speech[meeting].append((round(r['start']*16000),round(r['end']*16000),speaker))
    selected_intervals=defaultdict(list);source_people=set();chars=0;max_frames=0
    for index,(row,selected) in enumerate(zip(rows,original_selection)):
        stop();assert row['role']=='train-only' and row['language']=='Chinese' and row['meeting'] not in excluded
        for field,value in selected.items():assert row[field]==value,'Selected original data row changed'
        meeting=row['meeting'];ordinal=int(row['id'].split('-original-')[-1]);raw=original[meeting][ordinal]
        assert row['text']==raw['text'] and row['sourceOriginalTier']==raw['speaker'],'Original training text/tier changed'
        assert Path(row['sourceTextgrid']).resolve()==(O/'original-textgrids'/(meeting+'.TextGrid')).resolve()
        assert original_sha[meeting]==row['sourceTextgridSha256']
        a=round(raw['start']*16000);b=round(raw['end']*16000);speaker=raw['speaker'].split('SPK')[-1]
        assert (a,b,speaker)==(row['startFrame'],row['endFrame'],row['sourceSpeakerId'])
        assert speaker in train_people and speaker not in eval_people
        source_people.add(speaker);assert 32000<=b-a==row['frames']<=480000
        source=P['sourceCatalog'][meeting];assert source['file']==source_files[meeting]
        assert 0<=a<b<=source['header']['frames'] and source['singleMicCandidateSourceStructurallyAdmissible']
        # Deliberately independent of the producer's event-sweep selection:
        # compare each selected interval directly with every other speaker.
        assert not any(other!=speaker and max(a,x)<min(b,y) for x,y,other in speech[meeting]),'True cross-speaker overlap entered training'
        selected_intervals[meeting].append((a,b));path=Path(row['audio'])
        assert path.resolve().is_relative_to((A/'clips').resolve()) and sha(path)==row['audioSha256']
        with wave.open(str(path),'rb') as stream:
            assert (stream.getnchannels(),stream.getsampwidth(),stream.getframerate(),stream.getnframes())==(1,2,16000,b-a)
            pcm=stream.readframes(b-a);assert not stream.readframes(1)
        assert len(pcm)==(b-a)*2 and hashlib.sha256(pcm).hexdigest()==row['pcmSha256']
        receipt=read(row['acquisitionReceipt']);assert receipt['id']==row['id'] and receipt['audioSha256']==row['audioSha256']
        assert receipt['sourceFile']==source['file'] and receipt['sourceObjectEtag']==source['etag']
        assert receipt['sourceTextSha256']==hashlib.sha256(raw['text'].encode()).hexdigest()
        assert receipt['sourceOriginalTextgridSha256']==row['sourceTextgridSha256']
        assert receipt['sourceStartFrame']==a and receipt['sourceEndFrame']==b and receipt['selectedChannel']==0
        if receipt['rawBytesFetched']:
            start=source['header']['dataOffset']+a*16;end=source['header']['dataOffset']+b*16-1
            assert receipt['sourceRawByteRange']==[start,end] and receipt['rawBytesFetched']==(b-a)*16
            assert re.fullmatch('[a-f0-9]{64}',receipt['sourceRawRangeSha256'])
        else:
            assert meeting=='R0003_M0046'
            with wave.open(first_source['output'],'rb') as source_stream:
                source_stream.setpos(a);assert source_stream.readframes(b-a)==pcm
        state['verifiedExamples']+=1;state['verifiedFrames']+=b-a;chars+=len(raw['text']);max_frames=max(max_frames,b-a)
        if index%128==0:save()
    for intervals in selected_intervals.values():
        intervals.sort();assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'Duplicate/overlapping source PCM in selected clips'
    controls={}
    for row in rows:
        venue=row['meeting'].split('_')[0]
        key=hashlib.sha256(('independent-original-channel-control/'+row['id']).encode()).hexdigest()
        if venue not in controls or key<controls[venue][0]:controls[venue]=(key,row)
    assert len(controls)==12;store=PublicAliTrainingStore(O/'Train_Ali_far.csv');control_proofs=[]
    for venue,(_,row) in sorted(controls.items()):
        stop();meeting=row['meeting'];source=P['sourceCatalog'][meeting]
        raw_original=original[meeting][int(row['id'].split('-original-')[-1])]
        a=round(raw_original['start']*16000);b=round(raw_original['end']*16000)
        first=source['header']['dataOffset']+a*16;last=source['header']['dataOffset']+b*16-1
        raw=store.range_bytes(source_files[meeting],first,last,source['objectBytes'],source['etag'])
        with wave.open(row['audio'],'rb') as stream:pcm=stream.readframes(b-a)
        assert pcm[0::2]==raw[0::16] and pcm[1::2]==raw[1::16],'Independent original-channel control failed'
        control_proofs.append({'venue':venue,'id':row['id'],'sourceRawRangeSha256':hashlib.sha256(raw).hexdigest(),
            'pcmSha256':hashlib.sha256(pcm).hexdigest(),'allControlBytesMatchFirstSourceChannel':True})
    assert state['verifiedExamples']==P['examples'] and state['verifiedFrames']==P['frames']
    assert not(source_people&eval_people) and 'torch' not in sys.modules
    state.update(state='PASS_5027_ORIGINAL_CHINESE_ASR_INPUTS_SOURCE_TEXT_PCM_TIMING_AND_PERSON_INTEGRITY',
        manifest=done['manifest'],manifestSha256=done['manifestSha256'],protocolSha256=sha(C/'protocol.json'),
        audioSeconds=P['frames']/16000,meetings=len(selected_intervals),venues=12,trainingSpeakerIds=len(source_people),
        officialEvaluationSpeakerIds=len(eval_people),participantIntersection=[],sourceTextCharacters=chars,
        all5027OriginalLabelsAndFrameIntervalsExact=True,all5027WaveHeadersAndPCMHashesChecked=True,
        all5027CaptureReceiptsBindPrimaryOriginalByteRanges=True,everyCaptureOutputByteCheckedAgainstRawChannel=True,
        independentFreshSourceChannelControls=control_proofs,
        trueCrossSpeakerOverlapIntervals=0,duplicateOrOverlappingTrainingSourceFrames=0,
        paddingOrTextNormalizationOrTimeClippingUsed=False,excludedWholeOutOfBoundsSources=len(excluded),
        maximumFrames=max_frames,originalAishellCrossCorpusPersonIsolationProven=False,
        taskScope='Nonoverlap Chinese ASR acoustic-adaptation input only; not a continuous diarization/overlap training set or a quality score.',
        modelTrainingAdmitted=False,modelInstances=0,gpuInitialized=False,elapsedSeconds=time.monotonic()-began)
    save();atomic_json(out/'completed.json',state)
except BaseException as error:state.update(state='FAILED_CHINESE_TRAIN_INPUT_INTEGRITY_RETAINED',error=repr(error));save();raise
finally:pressure.close()
print(json.dumps({k:v for k,v in state.items() if k!='independentFreshSourceChannelControls'},ensure_ascii=False))
