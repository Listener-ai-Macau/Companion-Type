"""Invoke disabled/missing-data CLIs; neither may create an inference or score."""
from pathlib import Path
from datetime import datetime
import json,subprocess,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from meeting_acoustic_contract_20261116 import read,sha
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
out=E/'language-specific-adaptation-r1/execution-gates-proof-r1';out.mkdir(parents=True,exist_ok=False)
protocol=J/'language-specific-adaptation-r1/prepared-r1/protocol.json';P=read(protocol)
worker=S/'tdt_domain_adaptation_20261116.py';forbidden=out/'must-not-be-created'
program="""import runpy,sys,json
sys.path.insert(0,sys.argv[1]);worker,protocol,run=sys.argv[2:]
sys.argv=[worker,'--protocol',protocol,'--phase','baseline','--run',run]
try:runpy.run_path(worker,run_name='__main__')
except RuntimeError as error:
 assert str(error)=='GPU execution not enabled in this frozen preparation',str(error)
 assert 'torch' not in sys.modules
 print(json.dumps({'disabledBeforeTorchImport':True,'torchImported':False,'error':str(error)}))
else:raise AssertionError('Disabled GPU execution was accepted')
"""
result=subprocess.run([P['runtime']['python'],'-c',program,str(S),str(worker),str(protocol),str(forbidden)],
    capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
assert result.returncode==0,(result.stdout,result.stderr)
assert not forbidden.exists();disabled=json.loads(result.stdout)
score=out/'unearned-score.json';control=protocol.with_name('scoring-control.json')
command=['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',
    str(S/'score_tdt_adaptation_20261117.py'),'--control',str(control),
    '--run',str(out/'nonexistent-training-run'),'--output',str(score)]
scored=subprocess.run(command,capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
assert scored.returncode!=0 and 'training-completed.json' in scored.stderr and not score.exists(),(scored.stdout,scored.stderr)
(out/'expected-missing-training-error.log').write_text(scored.stdout+scored.stderr,encoding='utf-8')
report={'state':'PASS_DISABLED_GPU_AND_MISSING_TRAINING_FAIL_CLOSED',
    'at':datetime.now().astimezone().isoformat(),'disabledGpuProof':disabled,
    'inferenceRunDirectoryCreated':False,'scoreWithoutCompletedTrainingCreated':False,
    'protocolSha256':sha(protocol),'workerSha256':sha(worker),'scorerSha256':sha(S/'score_tdt_adaptation_20261117.py'),
    'newNeuralCalls':0,'parameterUpdates':0,'limits':limits.query()}
atomic_json(out/'result.json',report);print(json.dumps(report))
