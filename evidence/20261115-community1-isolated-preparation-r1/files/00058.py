"""Transport control: original overlap and fractional times survive export."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import hashlib,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from pyannote.core import Annotation,Segment
from companion_community1_adapter_20261115 import export_output,sha
import numpy as np
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-comparison-r1'
control=Path('E:/CodexData/Companion/product-d1d2-20261114/community1-comparison-r1/output-contract-r1')
regular=Annotation(uri='technical_transport_control')
regular[Segment(.123456,1.987654),'first']='SPEAKER_00'
regular[Segment(1.111111,2.333333),'second']='SPEAKER_01'
exclusive=Annotation(uri='technical_transport_control')
exclusive[Segment(.123456,1.111111),'first']='SPEAKER_00'
exclusive[Segment(1.111111,2.333333),'second']='SPEAKER_01'
before=[(float(s.start),float(s.end),str(t),str(p)) for s,t,p in regular.itertracks(yield_label=True)]
output=SimpleNamespace(speaker_diarization=regular,exclusive_speaker_diarization=exclusive,
 speaker_embeddings=np.array([[1.,0.,0.],[0.,1.,0.]],dtype=np.float32))
receipt=export_output(output,control,case={'meeting':'technical_transport_control','audioSeconds':3.,'audioSha256':'0'*64},
 binding={'scope':'Constructed transport control; no model, reference or quality inference'})
saved=json.loads((control/'raw-output.json').read_text(encoding='utf-8'))
after=[(r['start'],r['end'],r['track'],r['speaker']) for r in saved['regular']]
assert before==after and saved['regular']!=saved['exclusiveDiagnosticOnly']
lines=(control/'predicted.rttm').read_text().splitlines();assert len(lines)==2
for line,row in zip(lines,saved['regular']):
 f=line.split();assert abs(float(f[3])-row['start'])<5.1e-10 and abs(float(f[3])+float(f[4])-row['end'])<1e-9
assert saved['regular'][1]['start']<saved['regular'][0]['end']
assert receipt['exclusiveOutputUsedForQualification'] is False
report={'state':'PASS_OUTPUT_TRANSPORT_PRESERVES_ORIGINAL_OVERLAP_AND_FLOAT_TIMES',
 'at':datetime.now().astimezone().isoformat(),'rawFloatTimesExact':True,'regularOverlapPreserved':True,
 'exclusiveSeparate':True,'rttmPrecisionSeconds':1e-9,'newNeuralCalls':0,'qualityQualified':False,
 'scope':'Only serialization and input/output contract, constructed intervals, not speech recognition evidence.',
 'adapterSourceSha256':sha(S/'companion_community1_adapter_20261115.py'),'limits':limits.query()}
(D/'output-contract-proof.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
