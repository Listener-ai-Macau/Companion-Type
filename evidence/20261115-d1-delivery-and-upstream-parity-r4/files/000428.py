"""Preserve the zero-inference dependency failure; create a separate fixed attempt."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
src=Path(__file__).parent;old=read(C/'separation-state.json')
assert old['newNeuralCalls']==0 and "No module named 'torchaudio'" in old['error']
assert sha(src/'practical_ps4_worker_20261107.py')==read(C/'protocol.json')['workerSourceSha256']
assert read(C/'audio-frontend-source.json')['state']=='OFFICIAL_TORCHAUDIO211_PYTHON_SOURCE_VERIFIED_NO_IMPORT_OR_INFERENCE'
dest=src/'practical_ps4_frontend_worker_20261107.py';assert not dest.exists()
s=(src/'practical_ps4_worker_20261107.py').read_text()
s=s.replace('import argparse,hashlib,importlib.util,json,os,time,traceback,wave','import argparse,hashlib,importlib.util,json,os,sys,time,traceback,wave')
s=s.replace("C/'protocol.json'","C/'protocol-r2.json'")
s=s.replace("args.stage+'-state.json'","args.stage+'-state-r2.json'")
for name in ['separation-state','separation-manifest','asr-manifest','weight-roundtrip-asr','weight-roundtrip-separation']:
    s=s.replace("'"+name+".json'","'"+name+"-r2.json'")
for name in ['separation-outputs','asr-outputs']:
    s=s.replace("'"+name+"'","'"+name+"-r2'")
needle="        module_file=Path(ready['sourceRoot'])/'inference.py';"
assert needle in s
s=s.replace(needle,"        frontend=read(C/'audio-frontend-source.json');assert sha(C/'audio-frontend-source.json')==P['audioFrontendManifestSha256']\n        for row in frontend['files']:assert sha(row['file'])==row['sha256']\n        sys.path.insert(0,frontend['pythonPath'])\n"+needle)
needle="        state.update(state='LOADING_MATCHED_PS4_NATIVE_MODEL');"
assert needle in s
s=s.replace(needle,"        assert Path(author.torchaudio.__file__).resolve().is_relative_to(Path(frontend['pythonPath']).resolve())\n"+needle)
ast.parse(s);dest.write_text(s,encoding='utf8')
runner=src/'run_practical_ps4_frontend_20261107.py';assert not runner.exists()
s=(src/'run_practical_ps4_20261107.py').read_text()
s=s.replace("C/'run.json'","C/'run-r2.json'").replace("C/'resources.jsonl'","C/'resources-r2.json'")
s=s.replace("'practical_ps4_worker_20261107.py'","'practical_ps4_frontend_worker_20261107.py'")
for name in ['separation-state','asr-state']:s=s.replace("'"+name+".json'","'"+name+"-r2.json'")
s=s.replace("stage+'-attempt-%04d.log'","stage+'-r2-attempt-%04d.log'")
s=s.replace("'attempt-%04d.json'","'r2-attempt-%04d.json'")
ast.parse(s);runner.write_text(s,encoding='utf8')
P=read(C/'protocol.json');P.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),
    state='FROZEN_ENGINEERED_AUDIO_FRONTEND_FIX_BEFORE_FIRST_SEPARATION',
    parentProtocolSha256=sha(C/'protocol.json'),workerSourceSha256=sha(dest),
    audioFrontendManifestSha256=sha(C/'audio-frontend-source.json'),
    derivedAudioRoot='E:/CodexData/Companion/.model-cache/ps4-target-extraction-20261107/extracted-r2',
    preparationFailure='Original model attempt stopped on missing torchaudio before weights or any inference. Pinned unmodified official Python frontend added only to separation-worker path; standard PCM wave I/O and native Torch are unchanged. No model/audio/retention/scoring setting changed.')
assert not (C/'protocol-r2.json').exists();atomic_json(C/'protocol-r2.json',P)
print(json.dumps({'state':P['state'],'previousNeuralCalls':0,'workerSourceSha256':P['workerSourceSha256']}))
