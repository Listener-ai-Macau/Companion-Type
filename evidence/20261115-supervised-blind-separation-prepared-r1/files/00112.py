from pathlib import Path
import json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
import numpy as np
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/supervised-blind-separation-r1'
K=Path('E:/CodexData/Companion/.model-cache/supervised-blind-separation-20261115/validation-audio-only');K.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
original=read(C/'validation-audio-only.json');rows=[]
(C/'validation-before-input-file-split.json').write_text(json.dumps(original,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for item in read(C/'validation-examples.json'):
    assert sha(item['file'])==item['sha256'];x=np.load(item['file'],allow_pickle=False)[0]
    assert x.shape==(32000,) and x.dtype==np.float32
    p=K/(item['id']+'.npy');np.save(p,x,allow_pickle=False)
    rows.append({**{k:v for k,v in item.items() if k not in ['file','sha256','kind','sourceTargetsIncludeExactInactiveZero']},'file':str(p),'sha256':sha(p)})
(C/'validation-audio-only.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'validationInputOnlyFiles':len(rows),'targetSamplesInInputFiles':0,'newNeuralCalls':0}))
