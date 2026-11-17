"""Read ONNX top-level metadata without loading weights or running a model."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json
root=Path('E:/CodexData/Companion/.model-cache/parakeet-v3-int8-cpu-official20261117')
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
def varint(f):
 value=0;shift=0
 while True:
  b=f.read(1)
  if not b:raise EOFError
  b=b[0];value|=(b&127)<<shift
  if b<128:return value
  shift+=7;assert shift<=70
def entry(data):
 import io
 f=io.BytesIO(data);v={}
 while f.tell()<len(data):
  tag=varint(f);assert tag&7==2
  v[tag>>3]=f.read(varint(f)).decode('utf-8')
 return v[1],v[2]
rows=[]
for p in root.glob('*.onnx'):
 meta={}
 with p.open('rb') as f:
  while f.tell()<p.stat().st_size:
   tag=varint(f);wire=tag&7;number=tag>>3
   if wire==0:varint(f)
   elif wire==1:f.seek(8,1)
   elif wire==5:f.seek(4,1)
   elif wire==2:
    n=varint(f)
    if number==14:
     assert n<1024**2;k,v=entry(f.read(n));meta[k]=v
    else:f.seek(n,1)
   else:raise ValueError((number,wire))
 rows.append(dict(file=str(p),metadata=meta))
result=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),state='READ_ONLY_MODEL_EXPORT_CONTRACT_METADATA',models=rows,newInference=0,newTrainingUpdates=0)
target=C/'selected-cpu-export-contract-metadata-r1.json';assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
