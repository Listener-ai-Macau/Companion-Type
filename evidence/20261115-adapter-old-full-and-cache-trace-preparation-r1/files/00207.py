"""Review a neutral cache trace only after exact complete-output control."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,sys
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
control=C/'d1d2-execution/nemotron-cache-trace-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(control/'protocol.json');result=a.run/'result';trace=result/'cache-trace'
assert read(a.run/'run.json')['state']=='COMPLETE_SAME_CHECKPOINT_REFERENCE_COMPARISON_PENDING'
state=read(result/'state.json');assert state['state']=='COMPLETE_UPSTREAM_REFERENCE_COMPARISON_PENDING'
assert read(result/'observational-control.json')['exactOriginalFullProbabilityBytes']
assert hashlib.sha256((result/'probabilities.npy').read_bytes()).hexdigest()==P['originalFullProbabilitySha256']
source=C/'combination-study-r1/convergence-review-r1.json';diagnosis=read(source)
assert diagnosis['meeting']==state['case']['meeting']=='20200623_S_R001S07C01'
channel=diagnosis['nativeSpeakerForScoringOnly'];assert channel==2
start,end=diagnosis['lastPredictedActivitySeconds'],diagnosis['referenceReturnSeconds']
rows=[];active_hashes={}
for file in sorted(trace.glob('update-*.json')):
 row=read(file);index=row['update'];value=np.load(trace/('cache-%04d.npy'%index),allow_pickle=False)
 assert value.shape==(1,row['after']['frames'],8)
 assert (value>.5).sum(axis=1)[0].tolist()==row['after']['activeFramesByChannel']
 fingerprints=row['after']['embeddingSha256ByFrame'];assert len(fingerprints)==value.shape[1]
 active_hashes[index]={fingerprints[i] for i in np.nonzero(value[0,:,channel]>.5)[0]}
 rows.append(row)
assert len(rows)==read(trace/'summary.json')['updates']==state['mainNeuralChunkCalls']
gap=[row for row in rows if start<row['sourceEndSeconds']<end]
assert len(gap)>=2 and all(x['sourceEndSeconds']<y['sourceEndSeconds'] for x,y in zip(rows,rows[1:]))
first,last=gap[0],gap[-1]
retained=active_hashes[first['update']]&active_hashes[last['update']]
minimum=min(row['after']['activeFramesByChannel'][channel] for row in gap)
prior=max(row['after']['activeFramesByChannel'][channel] for row in rows if row['sourceEndSeconds']<=start)
if minimum>0 and retained:
 conclusion='HISTORICAL_CACHE_EVIDENCE_RETAINED_SIMPLE_TOTAL_EVICTION_NOT_SUPPORTED'
 next_action='Do not add reserve-slot policy: the hypothesized total loss did not occur. Preserve this negative result; distinguish prototype/acoustic mismatch from absent memory.'
elif prior>0 and minimum==0:
 conclusion='OBSERVED_LOSS_OF_ACTIVE_CACHE_EVIDENCE_REQUIRES_CAUSAL_REVIEW'
 next_action='Cache evidence disappears before return; inspect the first loss update before proposing one capacity-preserving intervention. No automatic threshold/size variants.'
else:
 conclusion='INCONCLUSIVE_CACHE_TRACE_DO_NOT_CHANGE_POLICY'
 next_action='Preserve trace and inspect original inputs; no automatic model/policy variant.'
report={'state':conclusion,'at':datetime.now().astimezone().isoformat(),
 'exactFullProbabilityBytesUnchanged':True,'audioSha256':state['case']['audioSha256'],
 'probabilitySha256':P['originalFullProbabilitySha256'],
 'diagnosisSourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'anonymousChannelForPostInferenceDiagnosisOnly':channel,
 'previousLastPredictedActivitySeconds':start,'referenceReturnSecondsForDiagnosisOnly':end,
 'absenceObservedCacheUpdates':len(gap),'priorMaximumActiveCacheFrames':prior,
 'minimumActiveCacheFramesDuringAbsence':minimum,
 'firstAfterActivityUpdate':first['update'],'lastBeforeReturnUpdate':last['update'],
 'firstAfterActivityCacheSupportFrames':first['after']['activeFramesByChannel'][channel],
 'lastBeforeReturnCacheSupportFrames':last['after']['activeFramesByChannel'][channel],
 'exactSameHistoricalActiveFrameFingerprintsRetainedAcrossGap':len(retained),
 'gapCurve':[{'update':row['update'],'sourceEndSeconds':row['sourceEndSeconds'],
  'activeCacheFrames':row['after']['activeFramesByChannel'][channel],
  'positiveScoreCacheFrames':row['after']['positiveScoreFramesByChannel'][channel],
  'maximumCachedProbability':row['after']['maximumProbabilityByChannel'][channel]} for row in gap],
 'newSelectionPolicyOrWeights':False,'qualityQualified':False,'d2Complete':False,
 'nextAction':next_action,'limits':limits.query(),
 'scope':'Prior reference return time enters only this exited-output audit. Cache support is model-predicted activity, not human-verified voice identity. Preserved embeddings rule out full eviction, not all forms of representation or contextual confusion.'}
target=a.run/'cache-review.json';assert not target.exists()
target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['state','minimumActiveCacheFramesDuringAbsence','exactSameHistoricalActiveFrameFingerprintsRetainedAcrossGap','nextAction']}))
