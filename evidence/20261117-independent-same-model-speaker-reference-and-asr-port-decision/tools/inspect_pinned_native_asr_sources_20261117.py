"""Read public pinned source/tokenizer indexes; no models or training data."""
from pathlib import Path
from datetime import datetime
import json,sys,urllib.request
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
out=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/native-vulkan-port-r1')
out.mkdir(parents=True,exist_ok=True)
urls={
    'nemo-v030-tree':'https://api.github.com/repos/NVIDIA/NeMo-Speech.cpp/git/trees/v0.3.0?recursive=1',
    'parakeet-pinned-tree':'https://huggingface.co/api/models/nvidia/parakeet-tdt-0.6b-v3/tree/541d1f99c6b0c3cd0b11a95167540bb8edefd82b'}
for name,url in urls.items():
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-source-inspection'}),timeout=30) as response:
        raw=response.read(4*1024**2+1)
    assert len(raw)<=4*1024**2
    d=json.loads(raw);(out/(name+'.json')).write_bytes(raw)
    if name=='nemo-v030-tree':
        print(json.dumps({'name':name,'treeSha':d.get('sha'),'truncated':d.get('truncated'),
            'paths':[r['path'] for r in d.get('tree',[]) if r['path'].startswith(('src/runtime/ggml/','src/asr/'))
                and any(x in r['path'].lower() for x in ['loader','model','token','tdt','conformer','runtime'])]},ensure_ascii=False))
    else:print(json.dumps({'name':name,'files':[{'path':r['path'],'bytes':r.get('size')} for r in d]},ensure_ascii=False))
