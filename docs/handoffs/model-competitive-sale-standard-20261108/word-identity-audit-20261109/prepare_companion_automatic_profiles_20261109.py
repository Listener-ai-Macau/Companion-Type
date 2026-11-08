"""Check automatic profile readiness without training or reference-guided selection."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,math,sys,wave,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';PARENT=R/'docs/handoffs/20261108-competitive-sale-standard';C=PARENT/'word-identity-audit-20261109';N=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results/L_R003S01C02'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if (C/'automatic-profiles-review.json').exists():
    previous=read(C/'automatic-profiles-review.json');assert previous['selectedProfiles']==17
    shutil.copyfile(C/'automatic-profiles-review.json',C/'automatic-profiles-review-initial-count-check.json')
P=read(PARENT/'async-speaker-contract-r2/prefix-protocol.json');journal=read(N/'speaker-journal.json');assert journal['audioSha256']==sha(P['sourceAudio'])
protocol={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'purpose':'Before another voice-extraction experiment, check whether the existing automatic diarization can supply stable solo profiles, without reference labels or text selecting them.','journalSha256':sha(N/'speaker-journal.json'),'audioSha256':journal['audioSha256'],'policy':'Outside the exposed5m window; exactly one predicted person active; shrink each continuous solo span200ms per side; at least2s; choose earliest up to8s, maximum3clips per predicted identity, start separation>=30s. All selected clips retained, including bad ones.','readinessDiagnostic':'After preparation only, check dominant actual reference identity consistency and>=95% exclusive reference speech coverage of each selected clip; this is a profile-purity diagnostic, not a model acceptance threshold or a selection filter.','newModelInference':False,'newNetworkCalls':0,'finalHoldoutOpened':False,'saleQualified':False}
write(C/'automatic-profiles-protocol.json',protocol)
segments=journal['segments'];edges=sorted({0,journal['audioSeconds'],P['sourceStartSeconds'],P['sourceEndSeconds'],*[v for x in segments for v in [x['start'],x['end']]]});solo=[]
for a,b in zip(edges,edges[1:]):
    if a<P['sourceEndSeconds'] and b>P['sourceStartSeconds']:continue
    people={str(x['speaker']) for x in segments if x['start']<b and x['end']>a}
    if len(people)!=1:continue
    person=next(iter(people))
    if solo and solo[-1]['person']==person and abs(solo[-1]['end']-a)<1e-9:solo[-1]['end']=b
    else:solo.append({'person':person,'start':a,'end':b})
selected=[];by_person={str(x['speaker']):[] for x in segments}
for span in solo:
    start=span['start']+.2;end=min(span['end']-.2,start+8)
    if end-start<2:continue
    current=by_person[span['person']]
    if len(current)>=3 or any(abs(start-x['start'])<30 for x in current):continue
    row={'id':'native-'+span['person']+'-'+str(len(current)),'nativePerson':span['person'],'start':start,'end':end};current.append(row);selected.append(row)
cache=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/automatic-profiles-20261109');cache.mkdir(parents=True,exist_ok=True)
with wave.open(P['sourceAudio'],'rb') as src:
    assert (src.getnchannels(),src.getframerate(),src.getsampwidth())==(1,16000,2)
    for row in selected:
        first=math.ceil(row['start']*16000);last=math.floor(row['end']*16000);src.setpos(first);pcm=src.readframes(last-first);path=cache/(row['id']+'.wav')
        with wave.open(str(path),'wb') as dst:dst.setnchannels(1);dst.setsampwidth(2);dst.setframerate(16000);dst.writeframes(pcm)
        row.update(start=first/16000,end=last/16000,audio=str(path),audioSha256=sha(path))
write(C/'automatic-profiles-inputs.json',{'audioSource':P['sourceAudio'],'audioSha256':journal['audioSha256'],'profiles':selected,'referencePassedToSelection':False,'predictedPeople':sorted(by_person),'noModelRun':True})
# All processing inputs are frozen before any scoring reference is opened.
from reference_textgrid_20261104 import read_reference_intervals
Q=read(PARENT/'async-speaker-contract-r2/prefix-scoring-only.json');assert sha(Q['reference'])==Q['referenceSha256'];references=[x for x in read_reference_intervals(Q['reference']) if x['text'].strip() and not x['text'].strip().startswith('<sil>')]
audit=[]
for row in selected:
    intervals=[x for x in references if x['start']<row['end'] and x['end']>row['start']];people=sorted({x['speaker'] for x in intervals})
    points=sorted({row['start'],row['end'],*[max(row['start'],min(row['end'],v)) for x in intervals for v in [x['start'],x['end']]]});speech={x:0.0 for x in people};exclusive={x:0.0 for x in people}
    for a,b in zip(points,points[1:]):
        active={x['speaker'] for x in intervals if x['start']<b and x['end']>a}
        for person in active:speech[person]+=b-a
        if len(active)==1:exclusive[next(iter(active))]+=b-a
    dominant=max(people,key=lambda x:speech[x]) if people else None;coverage=exclusive.get(dominant,0)/(row['end']-row['start']);audit.append({'id':row['id'],'nativePerson':row['nativePerson'],'dominantReferenceForEvaluationOnly':dominant,'exclusiveReferenceCoverage':coverage,'referenceSpeechSeconds':speech,'exclusiveReferenceSeconds':exclusive,'meetsFrozenPurityDiagnostic':coverage>=.95})
persons={}
for person,rows in by_person.items():
    checks=[x for x in audit if x['nativePerson']==person];identities={x['dominantReferenceForEvaluationOnly'] for x in checks}
    persons[person]={'clips':len(rows),'consistentDominantReference':len(identities)==1 and None not in identities,'allClipsPureEnough':bool(checks) and all(x['meetsFrozenPurityDiagnostic'] for x in checks),'referenceIdentitiesForScoringOnly':sorted(x for x in identities if x is not None)}
distinct={x['referenceIdentitiesForScoringOnly'][0] for x in persons.values() if x['consistentDominantReference']}
ready=bool(persons) and len(distinct)==len(persons) and all(x['clips']>=1 and x['consistentDominantReference'] and x['allClipsPureEnough'] for x in persons.values())
result={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'AUTOMATIC_PROFILE_POOL_READY_FOR_FURTHER_UNSEEN_CHECK_ONLY' if ready else 'AUTOMATIC_PROFILE_POOL_NOT_READY_NO_EXTRACTION_STARTED','selectedProfiles':len(selected),'predictedPeople':len(persons),'allPredictedPeopleReady':ready,'distinctDominantReferenceIdentities':len(distinct),'perPerson':persons,'profiles':audit,'readinessCountCorrection':'The existing reference-bank API accepts1..3 clips. Maximum3 is not a minimum; the first readiness check accidentally demanded3. Corrected to>=1 without changing any of17 selected clips or95% purity criterion; initial result retained. Two valid clips for one short speaker are not discarded or padded.','referenceGuidedSelection':False,'profilesPrunedAfterScoring':False,'sourceCaseIsExposedDevelopment':True,'actualPhysicalIdentityIndependenceKnown':False,'newModelOrNetworkCalls':0,'qualityQualified':False,'saleQualified':False,'finalHoldoutOpened':False}
write(C/'automatic-profiles-review.json',result);print(json.dumps({k:result[k] for k in ['state','selectedProfiles','predictedPeople','allPredictedPeopleReady','perPerson']},ensure_ascii=False),flush=True)
