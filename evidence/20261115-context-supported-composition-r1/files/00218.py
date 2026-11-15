"""Verify and flush every completed two-stream waveform before ASR."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/supervised-blind-separation-r1/natural-composition-r1'
p=argparse.ArgumentParser();p.add_argument('--control',type=Path,default=C);C=p.parse_args().control
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
protocol=read(C/'protocol.json');run=Path(protocol['separationRun'])
state=read(run/'state.json');assert state['state']=='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING'
assert len(state['results'])==32
items=[]
for case in state['results']:
    assert len(case['streams'])==2
    for stream in case['streams']:
        file=Path(stream['file']);assert sha(file)==stream['sha256']
        with file.open('r+b') as f:f.flush();os.fsync(f.fileno())
        assert sha(file)==stream['sha256'];items.append(dict(file=str(file),sha256=stream['sha256']))
target=C/'persisted-waveforms.json';assert not target.exists()
target.write_text(json.dumps(dict(state='PASS_ALL64_FLOAT_OUTPUTS_HASH_VERIFIED_AND_FLUSHED_BEFORE_ASR',
    at=datetime.now().astimezone().isoformat(),sourceStateSha256=sha(run/'state.json'),items=items,
    numericalOrPolicyChange=False,neuralCalls=0),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(state='PASS_ALL64_FLOAT_OUTPUTS_HASH_VERIFIED_AND_FLUSHED_BEFORE_ASR',files=len(items))))
