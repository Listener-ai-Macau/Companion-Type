"""CPU metadata/file fault cases only; no torch/model forward or training."""
from pathlib import Path
from datetime import datetime
import json,struct,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from meeting_acoustic_contract_20261116 import write_float_checkpoint,sha
from durable_model_state_20261117 import atomic_json
from tdt_adaptation_checkpoint_20261116 import committed_tdt_checkpoint
from tdt_adaptation_contract_20261117 import valid_resume_position,checkpoint_identity,require_final_checkpoint
from run_owned_tdt_adaptation_20261117 import observed_updates
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
out=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/cpu-recovery-contract-r1')
out.mkdir(parents=True,exist_ok=False);checks=[]
def rejected(label,function):
    try:function()
    except (RuntimeError,ValueError,KeyError):checks.append(label);return
    raise AssertionError('Invalid case accepted: '+label)
for examples in list(range(4,475,4))+[475]:
    assert valid_resume_position(examples,(examples+3)//4)==(examples,(examples+3)//4)
for examples,updates in [(0,0),(1,1),(474,119),(475,118),(476,119),(True,1)]:
    rejected('resume-'+str(examples)+'-'+str(updates),lambda:valid_resume_position(examples,updates))
binding={'recipe':'owned-metadata-fixture'}
for generation in [1,2]:
    payload=out/('payload-'+str(generation)+'.safetensors')
    data=struct.pack('<3f',generation,.25,-.5)
    encoded=write_float_checkpoint(payload,[('parameter::fixture',[3])],lambda name,start,count:data[start*4:(start+count)*4])
    receipt={'binding':binding,'file':payload.name,**encoded,'completedExamples':4*generation,
        'optimizerUpdates':generation,'orderSha256':'fixed-order','frozenDigest':'fixed-factory','preflightOnly':False}
    proof=out/('receipt-'+str(generation)+'.json');atomic_json(proof,receipt)
    atomic_json(out/'latest-checkpoint.json',{'binding':binding,'receipt':proof.name,'receiptSha256':sha(proof)})
_,current=committed_tdt_checkpoint(out,binding);assert current['completedExamples']==8
pointer=out/'latest-checkpoint.json';raw=pointer.read_bytes();pointer.write_bytes(b'\0'*len(raw))
_,previous=committed_tdt_checkpoint(out,binding)
assert previous['completedExamples']==4 and previous['pointerSelection']['usedPrevious'] and not any(pointer.read_bytes())
checks.append('corrupt-pointer-recovers-only-hash-verified-previous-with-explicit-provenance')
rejected('foreign-binding',lambda:committed_tdt_checkpoint(out,{'recipe':'foreign'}))
payload=out/previous['file'];original=payload.read_bytes();payload.write_bytes(original[:-1]+bytes([original[-1]^1]))
rejected('corrupt-committed-payload-not-silently-accepted',lambda:committed_tdt_checkpoint(out,binding))
final_receipt={**previous,'completedExamples':475,'optimizerUpdates':119}
final={'finalCheckpoint':checkpoint_identity(final_receipt)}
assert require_final_checkpoint(final_receipt,final)==final['finalCheckpoint']
rejected('validation-cannot-evaluate-preflight-weights',lambda:require_final_checkpoint({**final_receipt,'preflightOnly':True},final))
rejected('validation-cannot-use-earlier-checkpoint',lambda:require_final_checkpoint(previous,final))
rejected('validation-payload-binding-differs',lambda:require_final_checkpoint({**final_receipt,'sha256':'different'},final))
base={'parameterUpdates':0,'candidateOptimizerUpdates':0,'completedTrainingExamples':0,
    'phase':'baseline','state':'FIXTURE','observedAt':'2026-11-17T08:00:00+08:00'}
assert observed_updates({**base,'phase':'preflight','parameterUpdates':1})['preflightParameterUpdates']==1
assert observed_updates({**base,'phase':'resume-1','candidateOptimizerUpdates':119,'completedTrainingExamples':475})['parameterUpdatesThisProcess']==0
assert observed_updates(None)['countsUnknown'] and observed_updates(None)['parameterUpdatesThisProcess'] is None
checks.append('supervisor-separates-preflight-process-candidate-and-unknown-update-counts')
assert 'torch' not in sys.modules
sources=['tdt_adaptation_checkpoint_20261116.py','tdt_adaptation_contract_20261117.py','tdt_domain_adaptation_20261116.py','run_owned_tdt_adaptation_20261117.py']
for name in sources:compile((S/name).read_bytes(),str(S/name),'exec')
report={'at':datetime.now().astimezone().isoformat(),'state':'PASS_TDT_METADATA_RECOVERY_AND_FINAL_CHECKPOINT_BINDING',
    'validOptimizerBoundariesChecked':119,'rejectedFaultCases':checks,
    'sourceSha256':{n:sha(S/n) for n in sources},'gpuPreflightPassed':False,
    'actualGpuTensorAdamRngRoundtripExecuted':False,'torchImported':False,'newNeuralCalls':0,'parameterUpdates':0,
    'limits':limits.query()}
atomic_json(out/'result.json',report);print(json.dumps(report))
