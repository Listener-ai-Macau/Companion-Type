"""Independent interval/ID contract audit against frozen RTTM, not identity QA."""
from pathlib import Path
from datetime import datetime
import json,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
T=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/supervised-blind-separation-r1'
C=T/'contextual-speaker-binding-r1';OLD=T/'continuous-overlap-composition-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
run=Path(read(C/'association-execution.json')['run']);state=read(run/'state.json')
assert state['state']=='COMPLETE_CONTEXTUAL_AUDIO_SPEAKER_ASSOCIATION_UNQUALIFIED'
cases={r['id']:r for r in read(C/'cases-audio-only.json')}
result=read(run/'associations.json');assert len(result['cases'])==32
detectors=read(OLD/'routed-composition-protocol.json')['detectors'];intervals={}
for meeting,source in detectors.items():
    assert sha(source['predictionRttm'])==source['predictionRttmSha256']
    rows=[]
    for line in Path(source['predictionRttm']).read_text().splitlines():
        f=line.split();rows.append((round(float(f[3])*16000),round((float(f[3])+float(f[4]))*16000),int(f[7].removeprefix('group'))))
    intervals[meeting]=rows
def coverage(meeting,person,low,high):
    points=sorted((max(low,a),min(high,b)) for a,b,p in intervals[meeting] if p==person and b>low and a<high)
    total=0;end=low
    for a,b in points:
        if b>max(end,a):total+=b-max(end,a)
        end=max(end,b)
    return total
resolved=unconfirmed=0;known_segments=0
for record in result['cases']:
    case=cases[record['id']];rows=record['segments'];n=case['sourceEndFrame']-case['sourceStartFrame']
    assert rows[0]['startFrame']==0 and rows[-1]['endFrame']==n
    assert all(a['endFrame']==b['startFrame'] for a,b in zip(rows,rows[1:]))
    assert sum(s['endFrame']-s['startFrame'] for s in rows)==n
    assert not record['sourceAudioAndWordsChanged'] and not record['speakerIdentityVerified']
    for segment in rows:
        lo=case['sourceStartFrame']+segment['startFrame'];hi=case['sourceStartFrame']+segment['endFrame']
        ids=segment['predictedModelSlots']
        if segment['associationReason']=='contextual-distinct-single-source-agreement':
            assert ids[0] is not None and ids[1] is not None and ids[0]!=ids[1]
            for person in ids:assert coverage(case['meeting'],person,lo,hi)==hi-lo
            for person in range(8):
                if person not in ids:assert coverage(case['meeting'],person,lo,hi)==0
            resolved+=hi-lo;known_segments+=1
        elif segment['overlapRoute']:
            assert ids==[None,None];unconfirmed+=hi-lo
        elif ids[0] is not None:assert coverage(case['meeting'],ids[0],lo,hi)==hi-lo
    for stream in case['streams']:assert sha(stream['file'])==stream['sha256']
oldRun=Path(read(OLD/'protocol.json')['asrRun']);oldState=read(oldRun/'state.json')
assert len(oldState['results'])==64
for item in oldState['results']:assert sha(item['file'])==item['sha256']
assert resolved/16000==state['overlapResolvedSeconds'] and unconfirmed/16000==state['overlapUnconfirmedSeconds']
proof=dict(state='PASS_AUDIO_INTERVAL_COVERAGE_AND_ORIGINAL_MODEL_ID_CONTRACT_ONLY',
    at=datetime.now().astimezone().isoformat(),associationRun=str(run),cases=32,
    completeTimeCoverage=True,sourceWaveformsUnchanged=True,original64AsrResultsUnchanged=True,
    independentOriginalRttmMembershipConfirmed=True,predictedPairedAssociationSegments=known_segments,
    predictedPairedAssociationSeconds=resolved/16000,unconfirmedOverlapSeconds=unconfirmed/16000,
    predictedAssociationCoverage=resolved/(resolved+unconfirmed),
    physicalSpeakerIdentityAccuracyMeasured=False,wordSpeakerAlignmentImplemented=False,
    unknownIntervalsDropped=False,newNeuralCalls=0,qualityQualified=False,d2Complete=False,
    boundary='Original model-ID/time consistency and retention only. These6.95seconds are predictions, not verified human identities or a speaker accuracy rate. Existing whole-meeting DER/CER and independent identity tests still required.')
(C/'association-validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
