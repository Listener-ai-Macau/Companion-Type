"""Verify converted train annotations against all published original TextGrids."""
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,re,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from reference_textgrid_20261104 import read_reference_intervals
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';A=E/'alimeeting-intake-audit-r1';out=O/'original-pairing-r2';out.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
download=read(O/'annotation-download-r1/completed.json')
assert download['state']=='COMPLETE_ALL209_ORIGINAL_PUBLIC_TRAIN_ANNOTATIONS_PENDING_PAIRING'
state={'at':datetime.now().astimezone().isoformat(),'state':'PAIRING_ORIGINAL209_TRAIN_ANNOTATIONS',
    'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'parserSourceSha256':hashlib.sha256((S/'reference_textgrid_20261104.py').read_bytes()).hexdigest(),
    'completed':[],'convertedUnaugmentedRows':0,'neuralCalls':0,'parameterUpdates':0,
    'evalOrTestReferenceRead':False,'rawSourceOrTargetChanged':False,'qualityQualified':False}
def save():
    state.update(observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
pressure=SystemRamPressure();began=time.monotonic();save()
try:
    converted=defaultdict(Counter)
    with gzip.open(A/'alimeeting-far_cuts_train.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            cut=json.loads(line);rec=cut['recording']
            if rec.get('transforms'):continue
            assert len(cut['supervisions'])==1;s=cut['supervisions'][0];state['convertedUnaugmentedRows']+=1
            key=(s['speaker'],round((cut['start']+s['start'])*16000),round((cut['start']+s['start']+s['duration'])*16000),s['text'])
            converted[rec['id']][key]+=1
    published=list(csv.DictReader((O/'Train_Ali_far.csv').open(encoding='utf-8-sig')))
    near=list(csv.DictReader((O/'Train_Ali_near.csv').open(encoding='utf-8-sig')))
    near_people=defaultdict(set)
    for r in near:
        name=Path(r['Audio:FILE']).stem;meeting='_'.join(name.split('_')[:2]);near_people[meeting].add(re.search(r'SPK(\d+)',name).group(1))
    assert set(converted)=={Path(r['Text:FILE']).stem for r in published}==set(near_people)
    source_people=set();total_missing=total_extra=total_zero=total_speaker_mismatch=total_same_person_overlap=0
    for item in download['entries']:
        assert not pressure.low(),'Original Windows low-RAM protection'
        assert time.monotonic()-began<300,'Bounded annotation pairing deadline'
        path=Path(item['local']);assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
        meeting=path.stem;state['currentMeeting']=meeting;save();raw=read_reference_intervals(path);original=Counter();zero=[];by_speaker=defaultdict(list);empty=0;short_names=0
        for r in raw:
            match=re.fullmatch('(?:'+re.escape(meeting)+'_)?'+r'[MF]_SPK(\d+)',r['speaker']);assert match,'Unexpected original speaker tier'
            short_names+=int(not r['speaker'].startswith(meeting+'_'))
            sid=match.group(1);source_people.add(sid)
            if not r['text']:empty+=1;continue
            first=round(r['start']*16000);last=round(r['end']*16000)
            if first>=last:zero.append((sid,first,last));continue
            original[(sid,first,last,r['text'])]+=1;by_speaker[sid].append((first,last))
        same_overlap=0
        for intervals in by_speaker.values():
            intervals.sort();end=-1
            for first,last in intervals:
                if first<end:same_overlap+=1
                end=max(end,last)
        missing=sum((original-converted[meeting]).values());extra=sum((converted[meeting]-original).values())
        speaker_mismatch=set(by_speaker)!=near_people[meeting]
        total_missing+=missing;total_extra+=extra;total_zero+=len(zero);total_same_person_overlap+=same_overlap;total_speaker_mismatch+=int(speaker_mismatch)
        state['completed'].append({'meeting':meeting,'originalFileSha256':item['sha256'],
            'nonemptyPositiveOriginalIntervals':sum(original.values()),'emptyOriginalIntervals':empty,
            'convertedUnaugmentedIntervals':sum(converted[meeting].values()),'originalSpeakerIds':sorted(by_speaker),'originalIntervalsWithShortGenderSpkTierName':short_names,
            'officialNearFileSpeakerIdsMatch':not speaker_mismatch,'rawTextSpeakerAndSampleTimesMissing':missing,
            'rawTextSpeakerAndSampleTimesExtra':extra,'zeroOrNegativeSampleLengthOriginalIntervals':zero,
            'samePersonOverlappingIntervals':same_overlap})
        save();del converted[meeting]
    assert not converted and len(state['completed'])==209
    passed=total_missing==total_extra==total_zero==total_speaker_mismatch==total_same_person_overlap==0
    state.update(state='PASS_ALL209_ORIGINAL_TRAIN_TEXT_AND_TIMES_EXACT' if passed else 'ORIGINAL_TRAIN_ANNOTATION_DIFFERENCES_REQUIRE_DIAGNOSIS',
        rawTextSpeakerAndSampleTimesMissing=total_missing,rawTextSpeakerAndSampleTimesExtra=total_extra,
        zeroOrNegativeSampleLengthOriginalIntervals=total_zero,samePersonOverlappingIntervals=total_same_person_overlap,
        officialNearSpeakerMismatchedMeetings=total_speaker_mismatch,sourceGlobalTrainingIds=len(source_people),
        publishedActualTrainSessions=209,publishedActualNearSpeakerIds=len({s for v in near_people.values() for s in v}),
        paperReportedCountsAreNotThePublishedFileIndex=True,
        priorIncompleteMirrorConclusionCorrected='Both official releasedCSV and raw conversion have the same209meeting/452ID inventory; paper212/456 counts alone did not establish missing mirror files.',
        allRawTextPreserved=True,textNormalizationUsedForPass=False,sourceFramesQuantizedAt16000HzWithoutAudioRewrite=True,
        trainingAudioFullyVerified=False,originalAishellCrossCorpusPersonIsolationProven=False,
        chineseTrainingAdmitted=False,elapsedSeconds=time.monotonic()-began)
    save();atomic_json(out/'completed.json',state)
except BaseException as error:state.update(state='FAILED_ORIGINAL_TRAIN_PAIRING_RETAINED',error=repr(error));save();raise
finally:pressure.close()
print(json.dumps({k:v for k,v in state.items() if k!='completed'},ensure_ascii=False))
