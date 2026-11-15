from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,wave,zipfile
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from prepare_sequential_meetings_20261115 import plans,ami_rows
from score_sequential_speakers_20261115 import intervals,der
from meeting_activity_threshold_20261115 import active_frames
from meeting_activity_head_20261115 import single_head_fallback
import numpy as np
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r2/activity-head-r1';C.mkdir()
TRAIN=C.parent/'activity-cal-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2/activity-cal-r1/model-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 payload=json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item())+'\n'
 with p.open('x',encoding='utf-8') as f:f.write(payload);f.flush();os.fsync(f.fileno())
rule={'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_SINGLE_ACTIVITY_HEAD_ROUTING_BEFORE_TRAINING_SCORE',
 'hypothesis':'Keep original native0.5 activities; only when no slot active, original pretrained3-class activity head predicts single speech with softmax>.5 and top slot has>=.8 of total native probability mass, assign that one original slot. No temporal padding or cache changes.',
 'helperSha256':sha(S/'meeting_activity_head_20261115.py'),'gridOrAlternativeSettings':False,
 'gate':'Both independent training meetings zero-collar DER<=10% and mean>=1pp better; otherwise reject without development. Exactly one fixed setting, no tuning on validation.',
 'reuseSameTrainingWindowsAndGlobalMappings':str(TRAIN/'decision.json'),'newWeightsOrNeuralCalls':False,
 'EnglishOnlyDiagnostic':True,'ChineseDefaultUnchanged':True,'referenceOrSpeakerCountsInInference':False}
write(C/'protocol.json',rule)
original=read(TRAIN/'decision.json');state=read(E/'speaker-state.json');results=[]
for source in read(TRAIN/'sources.json'):
 result=next(r for r in state['completed'] if r['meeting']==source['meeting']);data=np.load(result['probabilities'],allow_pickle=False)
 assert sha(result['probabilities'])==result['probabilitiesSha256']
 aux_file=Path(result['probabilities']).with_name('activity-logits.npy');aux=np.load(aux_file,allow_pickle=False)
 active=active_frames(data,.5);candidate,fill=single_head_fallback(data,aux,active)
 with zipfile.ZipFile(source['annotationArchive']) as z:rows=ami_rows(z,source['meeting'])
 reference=[r for r in rows if r['text']];windows,_=plans(rows);bind=next(r for r in original['inputs'] if r['meeting']==source['meeting'])
 identity={int(k):v for k,v in bind['fixedWholeMeetingIdentityMapping'].items()}
 with wave.open(source['audio'],'rb') as wav:seconds=wav.getnframes()/16000
 for mode,mask in [('original',active),('candidate',candidate)]:
  hypo=intervals(mask,seconds);total={k:0. for k in ['referenceSpeakerSeconds','missSeconds','falseAlarmSeconds','confusionSeconds','errorSeconds']}
  for w in windows:
   m=der(reference,hypo,w['start'],w['end'],identity)
   for k in total:total[k]+=m[k]
  results.append({'meeting':source['meeting'],'mode':mode,'DER':total['errorSeconds']/total['referenceSpeakerSeconds'],**total,
   'addedWholeMeetingSpeakerSeconds':int(fill.sum())/100,'originalAuxiliaryLogitsSha256':sha(aux_file)})
before=[r['DER'] for r in results if r['mode']=='original'];after=[r['DER'] for r in results if r['mode']=='candidate']
supported=max(after)<=.1 and sum(before)/2-sum(after)/2>=.01
decision={'state':'SUPPORTED_FIXED_ACTIVITY_HEAD_FOR_FROZEN_VALIDATION' if supported else 'REJECT_ACTIVITY_HEAD_ROUTING_ON_TRAINING',
 'at':datetime.now().astimezone().isoformat(),'trainingBeforeDER':before,'trainingAfterDER':after,'detail':results,
 'validationRead':False,'protocolSha256':sha(C/'protocol.json'),'helperSha256':rule['helperSha256'],
 'newNeuralCalls':0,'weightsChanged':False,'productDefaultChanged':False,'qualityQualified':False,'scriptSha256':sha(__file__)}
write(C/'decision.json',decision);print(json.dumps({k:v for k,v in decision.items() if k!='detail'},ensure_ascii=False))
