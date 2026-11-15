from pathlib import Path
from datetime import datetime
import hashlib,json,sys
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
import numpy as np
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(C/'combination-study-r1/native8/protocol.json')
case=read(C/'combination-study-r1/native8/audio-only.json')[0]
N=Path(P['probabilityCacheRoot'])/case['meeting']
manifest=read(N/'probabilities.json')
native=np.load(N/'probabilities.npy',mmap_mode='r',allow_pickle=False)[:manifest['committedFrames']]
assert hashlib.sha256(memoryview(native).cast('B')).hexdigest()==manifest['committedPrefixSha256']
result=E/'new-ordinary-run-r2/result'
state=read(result/'state.json');strict=read(result/'strict-score.json')
assert state['state']=='COMPLETE_UPSTREAM_REFERENCE_COMPARISON_PENDING'
assert case['audioSha256']==state['case']['audioSha256']==manifest['audioSha256']
candidate=np.load(result/'probabilities.npy',allow_pickle=False)
assert abs(len(candidate)-len(native))<=1 and candidate.shape[1]==8
count=min(len(native),len(candidate));difference=np.abs(candidate[:count]-native[:count])
a,b=native[:count]>.5,candidate[:count]>.5;union=a|b
def last_time(values,channel):
 indices=np.nonzero(values[:,channel]>.5)[0]
 return None if not len(indices) else float(indices[-1]*.01)
report={'state':'REFERENCE_FULL_MEETING_CONFIRMS_NO_MATERIAL_IMPLEMENTATION_QUALITY_GAIN',
 'at':datetime.now().astimezone().isoformat(),'audioSha256':case['audioSha256'],
 'originalNemoSha256':read(result/'model-binding.json')['originalSha256'],
 'fullMeetingSeconds':case['audioSeconds'],'sameRawAnonymousChannelOrder':True,
 'comparedFrames':count,'nativeFrames':len(native),'referenceFrames':len(candidate),
 'meanAbsoluteProbabilityDifference':float(difference.mean()),
 'maximumAbsoluteProbabilityDifference':float(difference.max()),
 'activityDisagreementFramesByChannel':(a!=b).sum(axis=0).tolist(),
 'activityDisagreementFractionOfActiveUnion':int((a!=b).sum())/int(union.sum()),
 'nativeOriginalDer':0.1584147,'upstreamDer':strict['components']['diarization error rate'],
 'upstreamStrictScore':str(result/'strict-score.json'),
 'previouslyMissingReturningChannel2LastActivity':{'native':last_time(native,2),'upstream':last_time(candidate,2)},
 'derGate':0.10,'derPassed':strict['components']['diarization error rate']<=.10,
 'neuralCallsInComparison':0,'weightsChangedOrTrained':False,'qualityQualified':False,
 'decision':'Retain existing backend. No benefit supports swapping in this reference. Do not run old38min reference solely to retest an unhelpful alternative, or sweep frontend/geometry/threshold. Return to the already frozen ASR adapter full-meeting evaluation and model activity/identity limitations.',
 'boundedFrontendControl':'CPU-only61s and3nonaligned edge/impulse cases bit-exact to upstream full frontend; full same original source and geometry under2GiB. No labels, shifts, or channel matching used in probability comparison.',
 'limits':limits.query()}
out=E/'full-comparison.json';assert not out.exists()
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
