from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,wave,zipfile
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from prepare_sequential_meetings_20261115 import plans,ami_rows
from score_sequential_speakers_20261115 import intervals,mapping,der
from meeting_activity_threshold_20261115 import active_frames
import numpy as np
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r2/activity-cal-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2/activity-cal-r1/model-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 payload=json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item())+'\n'
 with p.open('x',encoding='utf-8') as f:f.write(payload);f.flush();os.fsync(f.fileno())
rule=read(C/'selection-before-download.json');state=read(E/'speaker-state.json')
assert state['state']=='COMPLETE_STAGE_A_ORIGINAL_WHOLE_SPEAKER_UNQUALIFIED'
scores=[];sources=read(C/'sources.json');inputs=[]
for source in sources:
 result=next(r for r in state['completed'] if r['meeting']==source['meeting'])
 assert sha(result['probabilities'])==result['probabilitiesSha256'] and result['audioSha256']==source['audioSha256']
 data=np.load(result['probabilities'],allow_pickle=False)
 with zipfile.ZipFile(source['annotationArchive']) as z:rows=ami_rows(z,source['meeting'])
 reference=[r for r in rows if r['text']];windows,audit=plans(rows);assert len(windows)>=3
 for w in windows:assert not [r for r in rows if r not in w['rows'] and r['start']<w['end']-1e-9 and r['end']>w['start']+1e-9]
 with wave.open(source['audio'],'rb') as wav:seconds=wav.getnframes()/16000
 original=intervals(active_frames(data,.5),seconds);identity,matrix=mapping(reference,original)
 inputs.append({'meeting':source['meeting'],'windows':len(windows),'eligibleAudit':audit,'sourcePosteriorSha256':result['probabilitiesSha256'],
  'fixedWholeMeetingIdentityMapping':identity,'trainingWindows':[{'start':w['start'],'end':w['end']} for w in windows]})
 for threshold in rule['thresholds']:
  hypothesis=intervals(active_frames(data,threshold),seconds)
  totals={k:0. for k in ['referenceSpeakerSeconds','missSeconds','falseAlarmSeconds','confusionSeconds','errorSeconds']}
  for w in windows:
   m=der(reference,hypothesis,w['start'],w['end'],identity)
   for k in totals:totals[k]+=m[k]
  scores.append({'meeting':source['meeting'],'threshold':threshold,'DER':totals['errorSeconds']/totals['referenceSpeakerSeconds'],**totals})
groups=[]
for threshold in rule['thresholds']:
 values=[r for r in scores if r['threshold']==threshold];assert len(values)==2
 groups.append({'threshold':threshold,'maxTrainingDER':max(r['DER'] for r in values),
  'meanTrainingDER':sum(r['DER'] for r in values)/2,'trainingDERs':[r['DER'] for r in values]})
best=min(groups,key=lambda r:(r['maxTrainingDER'],abs(r['threshold']-.5),-r['threshold']))
baseline=next(r for r in groups if r['threshold']==.5)
supported=best['maxTrainingDER']<=.1 and baseline['meanTrainingDER']-best['meanTrainingDER']>=.01
decision={'state':'CALIBRATED_ONE_ENGLISH_CANDIDATE_FOR_FROZEN_VALIDATION' if supported else 'REJECT_ACTIVITY_THRESHOLD_HYPOTHESIS_ON_TRAINING',
 'at':datetime.now().astimezone().isoformat(),'selectionRuleSha256':sha(C/'selection-before-download.json'),'inputs':inputs,
 'selected':best,'baseline':baseline,'thresholdSweepTrainingOnly':groups,'detail':scores,
 'selectedEnglishThreshold':best['threshold'] if supported else None,'ChineseThresholdUnchanged':.5,
 'validationReadDuringCalibration':False,'speakerWeightsChanged':False,'speakerCountHintProvided':False,
 'newNeuralCalls':0,'qualityQualified':False,'productDefaultChanged':False,'scriptSha256':sha(__file__),
 'activityHelperSha256':sha(S/'meeting_activity_threshold_20261115.py')}
write(C/'decision.json',decision);print(json.dumps({k:v for k,v in decision.items() if k not in ['inputs','thresholdSweepTrainingOnly','detail']},ensure_ascii=False))
