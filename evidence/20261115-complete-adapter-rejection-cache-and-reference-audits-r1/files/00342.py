"""Exited-output diagnosis; no new model, policy, or acceptance metric."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from reference_textgrid_20261104 import read_reference_intervals
import numpy as np,re
R=S.parent.parent;C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
D=C/'d1d2-execution/nemotron-cache-trace-r1'
run=Path('E:/CodexData/Companion/product-d1d2-20261114/nemotron-cache-trace-r1/whole-new-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(D/'protocol.json');review=read(run/'cache-review.json')
assert review['exactFullProbabilityBytesUnchanged']
prob_file=run/'result/probabilities.npy'
assert hashlib.sha256(prob_file.read_bytes()).hexdigest()==P['originalFullProbabilitySha256']
value=np.load(prob_file,allow_pickle=False)
case=next(c for c in read(D/'scoring-only.json') if c['meeting']=='20200623_S_R001S07C01')
assert hashlib.sha256(Path(case['reference']).read_bytes()).hexdigest()==case['referenceSha256']
diagnosis=read(C/'combination-study-r1/convergence-review-r1.json')
time=np.arange(len(value),dtype=np.float64)*.01
reference={name:np.zeros(len(value),dtype=np.bool_) for name in ['001-M','003-M','004-M','006-M']}
for row in read_reference_intervals(case['reference']):
 if re.sub(r'<[^>]*>','',row['text']).strip():
  reference[row['speaker']]|=(time>=row['start'])&(time<row['end'])
other=np.stack([mask for name,mask in reference.items() if name!='003-M']).any(axis=0)
target=reference['003-M'];channel=diagnosis['nativeSpeakerForScoringOnly'];assert channel==2
periods={'beforeGap':time<diagnosis['lastReferenceBeforeGapSeconds'],
         'afterReturn':time>=diagnosis['referenceReturnSeconds']}
results={}
def summary(mask):
 selected=value[mask];assert len(selected)
 active=selected>.5;maximum=selected.argmax(axis=1)
 others=np.delete(selected,channel,axis=1).max(axis=1)
 return {'diagnosticReferenceFrameSeconds':len(selected)*.01,
  'frames':len(selected),'targetChannelActiveSeconds':float(active[:,channel].sum()*.01),
  'noChannelAboveOriginalThresholdSeconds':float((~active.any(axis=1)).sum()*.01),
  'otherChannelAboveOriginalThresholdSeconds':float(np.delete(active,channel,axis=1).any(axis=1).sum()*.01),
  'highestProbabilityChannelSeconds':{str(i):float((maximum==i).sum()*.01) for i in range(8)},
  'targetProbabilityQuantiles':np.quantile(selected[:,channel],[.05,.5,.95,.99,1.]).tolist(),
  'maximumOtherProbabilityQuantiles':np.quantile(others,[.05,.5,.95,.99,1.]).tolist(),
  'quantileLevels':[.05,.5,.95,.99,1.]}
for phase,period in periods.items():
 results[phase]={'allTargetReferenceFrames':summary(target&period),
                 'targetOnlyReferenceFramesForDiagnosis':summary(target&period&~other)}
report={'state':'COMPLETE_RETURNING_VOICE_POSTERIOR_DIAGNOSIS_NO_NEW_INFERENCE',
 'at':datetime.now().astimezone().isoformat(),'results':results,
 'referenceSpeakerAndMappingForPostInferenceDiagnosisOnly':{'003-M':2,'004-M':1,'001-M':3,'006-M':0},
 'sourceProbabilitySha256':P['originalFullProbabilitySha256'],
 'referenceSha256':case['referenceSha256'],'cachedHistoricalFramesRemain':review['exactSameHistoricalActiveFrameFingerprintsRetainedAcrossGap'],
 'newNeuralCalls':0,'thresholdOrMappingRetuned':False,'modelOutputChanged':False,'qualityQualified':False,
 'scope':'10ms-frame descriptive diagnostic, not continuous-time DER or a replacement gate. Original coarse reference intervals may include silence; all-target and target-only frames are both reported. No region is removed from original scoring. Reference voice identity has not been independently re-audited by listening here.',
 'limits':limits.query()}
out=run/'posterior-review.json';assert not out.exists()
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
