"""Preserve failed original attempts and freeze a math-preserving memory proof."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-tse-supervised-adaptation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=C/'training-protocol-r1.json';P=read(old);assert all(sha(x['file'])==x['sha256'] for x in P['sourceFiles'])
attempts=[]
for run in ['train-r1','train-r2']:
    controller=read(C/(run+'-controller.json'));assert controller['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM'
    assert (C/run/'extractor-load-proof.json').exists() and (C/run/'frozen-asr-load-proof.json').exists() and not (C/run/'largest-query-gradient-memory.json').exists()
    assert read(C/run/'state.json')['newWeightUpdates']==0
    attempts.append({'run':run,'controller':controller,'bothModelLoadProofsPresent':True,'largestQueryBackwardNotCompleted':True,'progressStateStaleUntilFirstValidation':True,'exactOperationAtKillNotRecorded':True})
atomic_json(C/'training-memory-failure-r1.json',{'at':datetime.now().astimezone().isoformat(),'state':'RETAINED_TWO_ZERO_UPDATE_LOW_RAM_STOPS','protocolSha256':sha(old),'attempts':attempts,'diagnosis':'Both complete exact model load proofs exist before the RAM stop. The original worker never published a largest-query-preflight stage; the displayed loading state is stale. Forward/loss/backward suboperation was not recorded, so do not claim its exact allocation source as measured. Preserve and reduce stored residual-RNN activations with parity proof before retry.','noHyperparameterOrDataChange':True,'newWeightUpdates':0,'qualityQualified':False,'source':'https://docs.pytorch.org/docs/main/utils/checkpoint.html'})
worker=S/'tse_supervised_memory_proof_worker_20261108.py';files=[*P['sourceFiles'],{'file':str(S/'companion_tse_activation_memory_20261108.py'),'sha256':sha(S/'companion_tse_activation_memory_20261108.py')},{'file':str(worker),'sha256':sha(worker)}]
target=C/'activation-memory-proof-protocol-r1.json';assert not target.exists();atomic_json(target,{**P,'state':'FROZEN_MEMORY_ONLY_OUTPUT_AND_GRADIENT_PROOF','workerSha256':sha(worker),'sourceFiles':files,'gradientAbsoluteTolerance':1e-5,'gradientRelativeTolerance':1e-4,'newWeightUpdates':0,'source':'https://docs.pytorch.org/docs/main/utils/checkpoint.html'})
print(json.dumps({'state':'FROZEN_MEMORY_ONLY_PROOF','protocol':str(target)}),flush=True)
