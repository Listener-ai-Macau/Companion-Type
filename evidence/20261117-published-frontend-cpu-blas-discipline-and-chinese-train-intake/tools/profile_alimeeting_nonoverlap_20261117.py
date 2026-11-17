"""Quantify unchanged train utterances; reject cached augmentation/multichannel features."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict,Counter
import bisect,gzip,hashlib,json,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/alimeeting-intake-audit-r1')
source=E/'alimeeting-far_cuts_train.jsonl.gz';target=E/'nonoverlap-metadata-profile.json';assert not target.exists()
began=time.monotonic();groups=defaultdict(list);speakers=set();transformed=0;unaugmented=0;supervision_ids=set();rec_durations={}
with gzip.open(source,'rt',encoding='utf-8') as stream:
    for line in stream:
        row=json.loads(line);rec=row['recording']
        if rec.get('transforms'):transformed+=1;continue
        unaugmented+=1;assert row['channel']==list(range(8)) and row['features']['num_features']==80
        rec_durations[rec['id']]=rec['duration'];assert len(row['supervisions'])==1
        sup=row['supervisions'][0];assert sup['id'] not in supervision_ids;supervision_ids.add(sup['id'])
        assert sup['recording_id']==rec['id'] and sup['speaker'].isdigit()
        start=round((row['start']+sup['start'])*16000);end=start+round(sup['duration']*16000)
        assert 0<=start<end<=rec['num_samples'];speakers.add(sup['speaker'])
        groups[rec['id']].append((start,end,sup['speaker'],len(sup['text'])))
events_all=0;eligible_all=0;eligible_seconds=0.;per_session=[];eligible_speakers=set();overlap_seconds=0.
for meeting,rows in groups.items():
    events=defaultdict(list)
    for start,end,speaker,chars in rows:events[start].append((speaker,1));events[end].append((speaker,-1))
    active=Counter();last=None;overlaps=[]
    for at,changes in sorted(events.items()):
        if last is not None and last<at and len(active)>=2:
            if overlaps and overlaps[-1][1]==last:overlaps[-1]=(overlaps[-1][0],at)
            else:overlaps.append((last,at))
        for speaker,delta in changes:
            active[speaker]+=delta
            if active[speaker]==0:del active[speaker]
        assert all(n>0 for n in active.values());last=at
    assert not active
    ends=[b for a,b in overlaps];selected=[];length_eligible=0
    for start,end,speaker,chars in rows:
        if not 32000<=end-start<=480000:continue
        length_eligible+=1;i=bisect.bisect_right(ends,start)
        if i<len(overlaps) and overlaps[i][0]<end:continue
        selected.append((start,end,speaker,chars));eligible_speakers.add(speaker)
    seconds=sum((b-a)/16000 for a,b,_,_ in selected);eligible_all+=len(selected);eligible_seconds+=seconds
    overlap=sum((b-a)/16000 for a,b in overlaps);overlap_seconds+=overlap
    per_session.append({'meeting':meeting,'rawUtterances':len(rows),'length2To30SecondUtterances':length_eligible,
        'wholeUtteranceNonoverlapCandidates':len(selected),'candidateSeconds':seconds,
        'originalSpeakerIds':len({r[2] for r in rows}),'overlapUnionSeconds':overlap})
result={'at':datetime.now().astimezone().isoformat(),'state':'TRAIN_METADATA_NONOVERLAP_INVENTORY_ONLY_NOT_TRAINING_ADMISSION',
    'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'manifestSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'unaugmentedUtterances':unaugmented,'speedTransformedCutsExcluded':transformed,'originalRecordingSessions':len(groups),
    'originalRecordingSeconds':sum(rec_durations.values()),'normalizedNumericSpeakerIds':len(speakers),
    'publisherReportedTrainSessions':212,'publisherReportedTrainPeople':456,
    'manifestIsNotACompleteOfficialTrainSplit':len(groups)!=212 or len(speakers)!=456,
    'candidateWholeUtterances2To30SecondsWithoutAnyDifferentSpeakerOverlap':eligible_all,
    'candidateSecondsWithoutSpeedPerturbation':eligible_seconds,'candidateSpeakerIds':len(eligible_speakers),
    'originalOverlapUnionSeconds':overlap_seconds,'selectionUsesCandidateModelOutputs':False,
    'selectionChangesTextOrSplitsInsideUtterance':False,'selectionAddsPaddingOrChangesThresholds':False,
    'sourceChannels':8,'cachedFeatureDimensions':80,'cachedFeaturesApprovedForSingleMicModel':False,
    'singleMicSourcePcmAcquired':False,'sourceTextgridIndependentlyMatched':False,
    'originalAishellCrossCorpusSpeakerIsolationProven':False,'chineseTrainingAdmitted':False,
    'metadataNotUsableAudioHours':True,'noTrainingOrEvaluationAudioOpened':True,
    'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'perSession':per_session,
    'elapsedSeconds':time.monotonic()-began,'limits':limits.query()}
atomic_json(target,result)
print(json.dumps({k:v for k,v in result.items() if k!='perSession'},ensure_ascii=False))
