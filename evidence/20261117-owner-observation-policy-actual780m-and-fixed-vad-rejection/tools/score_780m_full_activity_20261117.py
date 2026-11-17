"""Compare one complete 780M speaker journal using the unchanged original mapping."""
from pathlib import Path
from datetime import datetime
import hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from meeting_acoustic_contract_20261116 import read,sha,require
from score_joint_whole_meetings_20261115 import activity_score,rttm
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/igpu-native8-r3')
C=J/'igpu-native8-r3';P=read(C/'protocol.json');state=read(C/'results/ES2003b/completed-state.json')
require(state['state']=='COMPLETE_780M_SPEAKER_JOURNAL_UNQUALIFIED' and state['gpuUsed']
    and state['selectedNativeDevice']['description']=='AMD Radeon 780M Graphics','Actual780M result missing')
require(state['allOriginalAudioSamplesSubmitted'] and state['oneContinuousSpeakerState'],'Partial/reset source')
case=next(r for r in read(J/'cpu-fixed-whole-r2/whole-scoring-only.json')['cases'] if r['meeting']=='ES2003b')
require(case['audioSha256']==state['audioSha256'] and case['frames']==state['submittedSamples'],'Source audio mismatch')
source=read(J/'cpu-fixed-whole-r2/predicted-speaker-bindings.json')['sources']['ES2003b']
for name in ['sourceJournal','producer','probabilityManifest','probabilities']:
    require(sha(source[name])==source[name+'Sha256'],'Retained native baseline changed')
base=Path(source['sourceJournal']).with_name('predicted.rttm');new=C/'results/ES2003b/predicted.rttm'
require(sha(base)==read(source['producer'])['rttmSha256'] and sha(new)==state['rttmSha256'],'RTTM changed')
require(sha(case['activityReference'])==case['activityReferenceSha256'],'Original whole reference changed')
reference=rttm(case['activityReference']);before=activity_score(reference,rttm(base),case['audioSeconds'])
require(abs(before['DER']-case['baselineDER'])<1e-8,'Original native8 score not reproduced')
after=activity_score(reference,rttm(new),case['audioSeconds'],identity=before['identityForScoringOnly'])
result={'at':datetime.now().astimezone().isoformat(),'state':'COMPLETE_780M_WHOLE_SOURCE_ACTIVITY_SCORED_NOT_QUALITY_QUALIFIED',
    'meeting':'ES2003b','audioSeconds':case['audioSeconds'],'allOriginalFrames':case['frames'],
    'originalNative8Baseline':before,'native780mUsingSameWholeSourceIdentity':after,
    'sameFrozenWeights':P['modelSha256']==source['modelSha256'],
    'originalWholeMappingForBothConditions':True,'collarSeconds':0,'overlapIncluded':True,
    'selectedNativeDevice':state['selectedNativeDevice'],
    'nativeCreateAndFullInferenceSeconds':state['nativeCreateAndFullInferenceSeconds'],
    'wholeWorkerSeconds':state['wholeWorkerSeconds'],'jobPeakPrivateCommitBytes':state['limits']['jobPeakPrivateCommitBytes'],
    'protocolSha256':sha(C/'protocol.json'),'workerReceiptSha256':sha(C/'results/ES2003b/completed-state.json'),
    'newTextAsrMeasured':False,'parameterUpdates':0,'qualityQualified':False,'saleQualified':False,
    'scope':'Native8 speaker activity runtime/backend comparison, not a new ASR model or a qualified diarization improvement.',
    'limits':limits.query()}
output=E/'ES2003b-fixed-mapping-activity-score.json';require(not output.exists(),'Keep immutable score')
atomic_json(output,result)
print(json.dumps({k:result[k] for k in ['state','nativeCreateAndFullInferenceSeconds','originalNative8Baseline','native780mUsingSameWholeSourceIdentity']},ensure_ascii=False))
