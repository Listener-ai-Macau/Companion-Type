"""Freeze trained-checkpoint recovery against the longest fixed validation query."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-tse-supervised-adaptation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
P=read(C/'training-protocol-r4.json');review=read(C/'training-review.json');assert review['completedWeightUpdates']==166 and review['protocolSha256']==sha(C/'training-protocol-r4.json')
checkpoint=read(C/'latest-training-checkpoint.json');assert checkpoint['completedSteps']==166 and checkpoint['protocolSha256']==review['protocolSha256']
outputs=read(C/'adapted-validation.json')['examples'];assert len(outputs)==48;selected=max(outputs,key=lambda x:x['audioSeconds']);example=next(x for x in read(P['dataManifest']) if x['id']==selected['id']);assert example['role']=='validation'
# Inference receives audio/profile only; strip all scoring and supervision text.
example={k:v for k,v in example.items() if k in ['id','audio','audioSha256','profileAudio','profileAudioSha256','audioSeconds']}
worker=S/'tse_supervised_reload_worker_20261108.py';extra=[worker,C/'training-review.json',C/'latest-training-checkpoint.json',C/'adapted-validation.json']
target=C/'reload-protocol-r1.json';assert not target.exists();atomic_json(target,{**P,'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_INDEPENDENT_TRAINED_WEIGHT_RECOVERY','workerSha256':sha(worker),'sourceFiles':[*P['sourceFiles'],*[{'file':str(p),'sha256':sha(p)} for p in extra]],'checkpoint':checkpoint,'example':example,'expectedValidationOutput':{k:selected[k] for k in ['audio','audioSha256','pcmExportDivisor']},'pcmMaximumLsbDifference':1,'newWeightUpdates':0,'qualityQualified':False})
print(json.dumps({'state':'FROZEN_INDEPENDENT_TRAINED_WEIGHT_RECOVERY','protocol':str(target)}),flush=True)
