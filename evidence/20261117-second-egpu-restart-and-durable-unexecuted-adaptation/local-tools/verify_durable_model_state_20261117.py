"""Own temporary files only; simulate corrupt latest metadata, not a PC reset."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=128*1024**2)
from durable_model_state_20261117 import atomic_json,read_snapshot
out=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/system-restart-20261116-2315/journal-verification-r2')
out.mkdir(exist_ok=False);path=out/'owned-state.json'
atomic_json(path,{'generation':1,'completedBlocks':1},progress=True)
atomic_json(path,{'generation':2,'completedBlocks':2},progress=True)
latest,latest_origin=read_snapshot(path);assert latest['generation']==2 and not latest_origin['usedPrevious']
old_bytes=path.read_bytes();(out/'second-generation-before-simulated-corruption.json').write_bytes(old_bytes)
corrupt_bytes=b'\0'*len(old_bytes);path.write_bytes(corrupt_bytes)
recovered,origin=read_snapshot(path)
assert recovered=={'generation':1,'completedBlocks':1} and origin['usedPrevious'] and not any(path.read_bytes())
atomic_json(path,{'generation':3,'completedBlocks':3},progress=True)
third,_=read_snapshot(path);assert third['generation']==3
previous=json.loads(path.with_name(path.name+'.previous').read_bytes());assert previous['generation']==1
archive=path.with_name(path.name+'.corrupt-'+hashlib.sha256(corrupt_bytes).hexdigest())
assert archive.read_bytes()==corrupt_bytes
report={'state':'PASS_FSYNC_PREVIOUS_SNAPSHOT_EXPLICIT_RECOVERY_AND_CORRUPT_BYTES_PRESERVATION',
    'latestCorruptionDetected':True,'previousGenerationRecovered':1,'corruptPrimaryWasNotSilentlyRepaired':True,
    'futureSuccessfulWritePreservesLastValidBackup':True,'futureSuccessfulWriteArchivesCorruptOriginalBytes':True,
    'actualAbruptPowerLossTested':False,
    'pcRestartedByTest':False,'newNeuralCalls':0,'parameterUpdates':0,
    'sourceSha256':hashlib.sha256((S/'durable_model_state_20261117.py').read_bytes()).hexdigest(),
    'limits':limits.query()}
(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
