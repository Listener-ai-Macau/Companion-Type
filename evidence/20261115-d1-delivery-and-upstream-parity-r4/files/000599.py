from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
import numpy as np
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(B/'native8-f16-smoke-r1/protocol.json')
N=Path(P['probabilityCacheRoot'])/'public61-native8-control';manifest=read(N/'probabilities.json')
native=np.load(N/'probabilities.npy',mmap_mode='r',allow_pickle=False)[:manifest['committedFrames']]
assert hashlib.sha256(memoryview(native).cast('B')).hexdigest()==manifest['committedPrefixSha256']
state=read(E/'smoke-run-r5/result/state.json');assert state['state']=='COMPLETE_UPSTREAM_REFERENCE_COMPARISON_PENDING' and state['finishedAt']
assert manifest['audioSha256']==state['case']['audioSha256']
assert P['precisionCheckpointSha256']==read(E/'smoke-run-r5/result/model-binding.json')['originalSha256']
rows={}
for name,file in [('upstream-default','probabilities.npy'),('same-original-bank-control','same-original-bank-probabilities.npy')]:
 candidate=np.load(E/'smoke-run-r5/result'/file,allow_pickle=False)
 assert candidate.shape[1]==8 and abs(len(candidate)-len(native))<=1
 length=min(len(native),len(candidate));difference=np.abs(candidate[:length]-native[:length])
 a,b=native[:length]>.5,candidate[:length]>.5;union=a|b;disagree=a!=b
 rows[name]={'frames':len(candidate),'nativeFrames':len(native),'comparedFrames':length,
  'trailingFrameDifferenceOnly':len(candidate)-len(native),'absoluteMean':float(difference.mean()),
  'absoluteMax':float(difference.max()),'absoluteP99':float(np.quantile(difference,.99)),
  'activityDisagreementFramesByChannel':disagree.sum(axis=0).tolist(),
  'activityDisagreementOfActiveUnion':int(disagree.sum())/int(union.sum()) if union.sum() else 0.,
  'perChannelMean':difference.mean(axis=0).tolist(),'originalChannelOrderCompared':True,'speakerPermutationApplied':False}
report={'state':'COMPLETE_SAME_CHECKPOINT_SHORT_DIFFERENTIAL_PROBABILITY_REVIEW',
 'results':rows,'weightsChangedOrTrained':False,'sourceNemoSha256':P['precisionCheckpointSha256'],
 'newNeuralCallsInThisScoring':0,'qualityQualified':False,'fullMeetingStillRequired':True,
 'scope':'Identical61s audio, fixed geometry/threshold, raw anonymous channels; no annotation, tuning, shifts or best-label remapping. The upstream FP32 frontend is the full-run route; original-bank branch is a fixed implementation diagnostic only.',
 'limits':limits.query()}
out=E/'smoke-comparison.json';assert not out.exists();out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
