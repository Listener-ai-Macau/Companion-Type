from pathlib import Path
from datetime import datetime
import hashlib,json,sys,urllib.request
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/public-speaker-adaptation-r1'
(D/'upstream').mkdir(parents=True)
paths=['models/sortformer_diar_models.py','losses/aux_diarization_loss.py','losses/bce_loss.py',
 'parts/utils/asr_multispeaker_utils.py','data/audio_to_diar_label.py']
entries=[]
for path in paths:
 url='https://raw.githubusercontent.com/NVIDIA-NeMo/NeMo/main/nemo/collections/asr/'+path
 with urllib.request.urlopen(url,timeout=30) as response:raw=response.read(2*1024**2)
 assert raw.startswith(b'#') and (b'Apache' in raw[:1500])
 out=D/'upstream'/(path.replace('/','__')+'.source.txt');assert not out.exists();out.write_bytes(raw)
 entries.append({'url':url,'file':str(out),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'executed':False})
(D/'upstream/binding.json').write_text(json.dumps({'at':datetime.now().astimezone().isoformat(),'files':entries,'limits':limits.query()},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'files':len(entries),'state':'PUBLIC_OFFICIAL_TRAINING_SOURCE_SAVED_NOT_EXECUTED'}))
