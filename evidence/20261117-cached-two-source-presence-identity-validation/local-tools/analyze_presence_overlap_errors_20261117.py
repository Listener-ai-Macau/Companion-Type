"""Partition unchanged full-source DER for diagnosis; never alter acceptance."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict,Counter
import json,os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
from meeting_acoustic_contract_20261116 import read,sha,require
from score_joint_whole_meetings_20261115 import rttm,activity_score
from durable_model_state_20261117 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
control=J/'context-activity-r1/quantized30-presence-r1'
P=read(control/'protocol.json');C=read(control/'scoring-control.json')
for item in C['files']:require(sha(item['file'])==item['sha256'],'Frozen original scorer/reference changed')
cases=read(C['wholeReferences'])['cases']
def partition(reference,hypothesis,duration,identity):
    events=defaultdict(list)
    for side,rows in [('r',reference),('h',hypothesis)]:
        for row in rows:
            low,high=max(0.,row['start']),min(duration,row['end'])
            if high<=low:continue
            person=row['speaker'] if side=='r' else identity.get(row['speaker'],'UNMAPPED-'+row['speaker'])
            events[low].append((side,person,1));events[high].append((side,person,-1))
    events[0.];events[duration];active={'r':Counter(),'h':Counter()};times=sorted(events)
    buckets={name:dict(timelineSeconds=0.,referenceSpeakerSeconds=0.,missSeconds=0.,falseAlarmSeconds=0.,confusionSeconds=0.)
        for name in ['referenceSilence','oneReferenceSpeaker','overlappingReferenceSpeakers']}
    for start,end in zip(times,times[1:]):
        for side,person,delta in events[start]:active[side][person]+=delta
        ref={s for s,n in active['r'].items() if n>0};hyp={s for s,n in active['h'].items() if n>0};dt=end-start
        group=buckets['referenceSilence' if not ref else 'oneReferenceSpeaker' if len(ref)==1 else 'overlappingReferenceSpeakers']
        group['timelineSeconds']+=dt;group['referenceSpeakerSeconds']+=len(ref)*dt
        group['missSeconds']+=max(0,len(ref)-len(hyp))*dt;group['falseAlarmSeconds']+=max(0,len(hyp)-len(ref))*dt
        group['confusionSeconds']+=(min(len(ref),len(hyp))-len(ref&hyp))*dt
    for value in buckets.values():
        value['errorSeconds']=sum(value[k] for k in ['missSeconds','falseAlarmSeconds','confusionSeconds'])
        value['DER']=value['errorSeconds']/value['referenceSpeakerSeconds'] if value['referenceSpeakerSeconds'] else None
    full=activity_score(reference,hypothesis,duration,identity=identity)
    for key in ['referenceSpeakerSeconds','missSeconds','falseAlarmSeconds','confusionSeconds','errorSeconds']:
        require(abs(sum(v[key] for v in buckets.values())-full[key])<1e-7,'Diagnostic partition lost original '+key)
    require(abs(sum(v['timelineSeconds'] for v in buckets.values())-duration)<1e-7,'Original timeline not partitioned exactly')
    return {'fullOriginalScore':full,'diagnosticBuckets':buckets}
meetings=[]
for meeting in P['admittedEnglishSources']:
    case=next(r for r in cases if r['meeting']==meeting)
    require(sha(case['activityReference'])==case['activityReferenceSha256'],'Original activity reference changed')
    reference=read(case['activityReference']) if case['activityKind']=='json' else rttm(case['activityReference'])
    prediction=read(E/'context-activity-r1/quantized30-presence-r1'/meeting/'prediction.json')
    score=read(control/('score-'+meeting+'.json'));identity=score['originalRawMultiVoice']['identityForScoringOnly']
    base=partition(reference,rttm(prediction['sourceRttm']),case['audioSeconds'],identity)
    combined=partition(reference,rttm(prediction['combined']['file']),case['audioSeconds'],identity)
    require(abs(combined['fullOriginalScore']['DER']-score['combinedWithOriginalFixedIdentity']['DER'])<1e-12,'Original full score changed')
    comparisons={'originalNative8':base,'q8PresencePlusNative8':combined}
    if meeting=='ES2003b':
        native=read(P['retainedNative180Prediction'])
        require(sha(native['combined']['file'])==native['combined']['sha256'],'Retained native180 journal changed')
        comparisons['native180PresencePlusNative8']=partition(reference,rttm(native['combined']['file']),case['audioSeconds'],identity)
    meetings.append({'meeting':meeting,'audioSeconds':case['audioSeconds'],'comparisons':comparisons,
        'q8InvalidTimeSegments':prediction['invalidNativeTimeSegments']})
report={'state':'DIAGNOSTIC_REFERENCE_OVERLAP_PARTITION_SUMS_TO_UNCHANGED_FULL_DER',
    'at':datetime.now().astimezone().isoformat(),'meetings':meetings,'oneOriginalMappingAcrossAllBuckets':True,
    'referenceUsedForDiagnosticScoringOnly':True,'modelInputsOrPredictionsChanged':False,
    'originalFullSourceAcceptanceChanged':False,'subsetAccuracyClaimed':False,
    'scorerSourceSha256':sha(S/'score_joint_whole_meetings_20261115.py'),
    'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
atomic_json(control/'overlap-error-diagnosis.json',report)
print(json.dumps({'state':report['state'],'meetings':[{ 'meeting':m['meeting'],
    'comparisons':{name:row['diagnosticBuckets'] for name,row in m['comparisons'].items()}} for m in meetings]},ensure_ascii=False))
