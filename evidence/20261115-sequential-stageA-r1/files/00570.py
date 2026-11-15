from pathlib import Path
import hashlib,json,sys,zipfile
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from prepare_sequential_meetings_20261115 import ami_rows,plans
from meeting_activity_threshold_20261115 import active_frames
import numpy as np
from scipy.ndimage import distance_transform_edt
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/sequential-meeting-stageA-r2/activity-cal-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2/activity-cal-r1/model-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
report=[];decision=read(C/'decision.json');state=read(E/'speaker-state.json')
for source in read(C/'sources.json'):
 row=next(r for r in state['completed'] if r['meeting']==source['meeting']);data=np.load(row['probabilities'],allow_pickle=False);active=active_frames(data,.5)
 bind=next(r for r in decision['inputs'] if r['meeting']==source['meeting']);identity={v:int(k) for k,v in bind['fixedWholeMeetingIdentityMapping'].items()}
 with zipfile.ZipFile(source['annotationArchive']) as z:rows=ami_rows(z,source['meeting'])
 windows,_=plans(rows);selected=np.zeros(len(data),dtype=bool)
 for w in windows:selected[int(np.ceil(w['start']*100)):int(np.ceil(w['end']*100))]=True
 distances=[]
 for speaker,slot in identity.items():
  ref=np.zeros(len(data),dtype=bool)
  for r in rows:
   if r['speaker']==speaker and r['text']:ref[int(np.ceil(r['start']*100)):int(np.ceil(r['end']*100))]=True
  missed=selected&ref&~active.any(axis=1)
  distances.extend((distance_transform_edt(~active[:,slot])[missed]/100).tolist())
 bins=[.02,.05,.1,.2,.5,1.,2.];values=np.asarray(distances)
 report.append({'meeting':source['meeting'],'missedSecondsGridDiagnostic':len(values)/100,
  'cumulativeFractionWithinSameSpeakerActivitySeconds':{str(b):float((values<=b).mean()) for b in bins},
  'medianDistance':float(np.median(values)),'p95Distance':float(np.quantile(values,.95))})
target=C/'boundary-audit.json';target.write_text(json.dumps({'state':'TRAINING_ONLY_MISS_BOUNDARY_DISTANCE_AUDIT','sources':report,
 'purpose':'Distinguish short timing holes from completely undetected phrases; not a new metric or qualification score.',
 'validationRead':False,'newNeuralCalls':0},indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
