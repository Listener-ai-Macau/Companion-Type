from pathlib import Path
from datetime import datetime
import json,urllib.request
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/english-asr-specialist-r1'
assert not C.exists();C.mkdir()
url='https://huggingface.co/api/models/handy-computer/whisper-large-v3-turbo-gguf?blobs=true'
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-model-provenance/1.0'}),timeout=25) as response:
  raw=response.read(2*1024**2);assert response.read(1)==b''
 data=json.loads(raw);(C/'publisher-metadata.json').write_bytes(raw)
 rows=[r for r in data['siblings'] if r['rfilename']=='whisper-large-v3-turbo-Q8_0.gguf'];assert len(rows)==1
 result={'state':'PUBLIC_SINGLE_SPECIALIST_METADATA_READ_NO_MODEL_DOWNLOAD_OR_INFERENCE','at':datetime.now().astimezone().isoformat(),'url':url,
  'repository':data['id'],'revision':data['sha'],'gated':data.get('gated'),'file':rows[0],'newNeuralCalls':0,'qualityQualified':False}
 assert not result['gated'];(C/'source.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
except BaseException as error:
 (C/'metadata-failure.json').write_text(json.dumps({'at':datetime.now().astimezone().isoformat(),'url':url,'error':repr(error),'modelDownloaded':False,'newNeuralCalls':0},indent=2)+'\n',encoding='utf-8');raise
