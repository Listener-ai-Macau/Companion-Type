from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,wave,zipfile
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from prepare_sequential_meetings_20261115 import plans,ami_rows
from score_sequential_speakers_20261115 import intervals,mapping,der
from meeting_activity_threshold_20261115 import active_frames
from meeting_activity_gap_20261115 import fill_same_speaker_gaps
import numpy as np
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r2/activity-gap-r1';C.mkdir()
TRAIN=C.parent/'activity-cal-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2/activity-cal-r1/model-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 payload=json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item())+'\n'
 with p.open('x',encoding='utf-8') as f:f.write(payload);f.flush();os.fsync(f.fileno())
assert read(TRAIN/'decision.json')['state']=='REJECT_ACTIVITY_THRESHOLD_HYPOTHESIS_ON_TRAINING'
rule={'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_TRAINING_ONLY_SAME_ID_GAP_CALIBRATION',
 'hypothesis':'Original0.5 threshold retained. Training-only boundary audit found many misses near same-ID predicted speech. Close internal holes only between the same native identity, if no original speaker is active in the hole; reject competing fill proposals. No outward edge padding or new speaker IDs.',
 'gapSeconds':[0.,.05,.1,.2,.3,.5,.75,1.0],'objective':'Minimize maximum training-meeting zero-collar raw DER. Tie choose the smallest gap.',
 'adoptionRule':'Both independent training meetings DER<=10% and mean DER improvement>=1pp. Then evaluate exactly one selected policy on frozen development; otherwise reject without development search.',
 'referenceSelection':'Exact same all-speaker complete nonoverlap training windows and0.5 whole-meeting fixed identity maps as activity-cal-r1.',
 'trainingSourcesSha256':sha(TRAIN/'sources.json'),'priorThresholdFailureSha256':sha(TRAIN/'decision.json'),
 'boundaryAuditSha256':sha(TRAIN/'boundary-audit.json'),'activityHelperSha256':sha(S/'meeting_activity_threshold_20261115.py'),
 'gapHelperSha256':sha(S/'meeting_activity_gap_20261115.py'),'inspiredByOfficialPostprocessing':'https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/include/nemo_speech/diar.h',
 'validationThresholdOrGapSearch':False,'qualityGatesChanged':False,'noNewWeightsOrNeuralCalls':True}
write(C/'protocol.json',rule)
original_decision=read(TRAIN/'decision.json');state=read(E/'speaker-state.json');scores=[]
for source in read(TRAIN/'sources.json'):
 result=next(r for r in state['completed'] if r['meeting']==source['meeting']);assert sha(result['probabilities'])==result['probabilitiesSha256']
 data=np.load(result['probabilities'],allow_pickle=False);active=active_frames(data,.5)
 with zipfile.ZipFile(source['annotationArchive']) as z:rows=ami_rows(z,source['meeting'])
 reference=[r for r in rows if r['text']];windows,audit=plans(rows)
 bind=next(r for r in original_decision['inputs'] if r['meeting']==source['meeting']);identity={int(k):v for k,v in bind['fixedWholeMeetingIdentityMapping'].items()}
 assert [{'start':w['start'],'end':w['end']} for w in windows]==bind['trainingWindows']
 with wave.open(source['audio'],'rb') as wav:seconds=wav.getnframes()/16000
 for gap in rule['gapSeconds']:
  filled,mask=fill_same_speaker_gaps(active,gap);hypothesis=intervals(filled,seconds)
  total={k:0. for k in ['referenceSpeakerSeconds','missSeconds','falseAlarmSeconds','confusionSeconds','errorSeconds']}
  for w in windows:
   m=der(reference,hypothesis,w['start'],w['end'],identity)
   for k in total:total[k]+=m[k]
  scores.append({'meeting':source['meeting'],'gapSeconds':gap,'DER':total['errorSeconds']/total['referenceSpeakerSeconds'],**total,
   'wholeMeetingFilledSpeakerSeconds':int(mask.sum())/100})
groups=[]
for gap in rule['gapSeconds']:
 values=[r for r in scores if r['gapSeconds']==gap]
 groups.append({'gapSeconds':gap,'maxTrainingDER':max(r['DER'] for r in values),'meanTrainingDER':sum(r['DER'] for r in values)/2,'trainingDERs':[r['DER'] for r in values]})
best=min(groups,key=lambda r:(r['maxTrainingDER'],r['gapSeconds']));baseline=next(r for r in groups if r['gapSeconds']==0)
supported=best['maxTrainingDER']<=.1 and baseline['meanTrainingDER']-best['meanTrainingDER']>=.01
decision={'state':'CALIBRATED_ONE_GAP_CANDIDATE_FOR_FROZEN_VALIDATION' if supported else 'REJECT_SAME_ID_GAP_HYPOTHESIS_ON_TRAINING',
 'selected':best,'baseline':baseline,'selectedGapSeconds':best['gapSeconds'] if supported else None,'thresholdUnchanged':.5,
 'trainingOnlySweep':groups,'detail':scores,'protocolSha256':sha(C/'protocol.json'),'validationReadDuringCalibration':False,
 'speakerWeightsChanged':False,'newNeuralCalls':0,'productDefaultChanged':False,'qualityQualified':False,'scriptSha256':sha(__file__)}
write(C/'decision.json',decision);print(json.dumps({k:v for k,v in decision.items() if k not in ['trainingOnlySweep','detail']},ensure_ascii=False))
