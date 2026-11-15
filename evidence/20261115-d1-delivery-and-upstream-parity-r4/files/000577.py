"""Check full AdamW/RNG recovery by reproducing the next update, not just parsing."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,time,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha
from companion_tse_checkpoint_streamed_20261108 import save_checkpoint,restore_checkpoint
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False)
assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'PROVING_BOUNDED_CHECKPOINT_NEXT_UPDATE','pid':os.getpid(),'newMeetingTrainingUpdates':0,'qualityQualified':False};atomic_json(out/'state.json',state,progress=True)
try:
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(20261108);assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0)
    model=torch.nn.Sequential(torch.nn.Linear(32,64),torch.nn.Tanh(),torch.nn.Linear(64,8)).cuda();names=[n for n,p in model.named_parameters()];opt=torch.optim.AdamW(model.parameters(),lr=1e-5,weight_decay=1e-5)
    def step():
        opt.zero_grad(set_to_none=True);x=torch.randn(5,32,device='cuda:0');y=torch.randn(5,8,device='cuda:0');loss=(model(x)-y).square().mean();loss.backward();opt.step();return float(loss)
    step();checkpoint=save_checkpoint(model,opt,torch=torch,root=Path(P['proofCheckpointRoot']),step=1,protocol_sha=sha(args.protocol),parameter_names=names);expected_loss=step();expected={n:p.detach().clone() for n,p in model.named_parameters()};expected_states={n:{k:v.detach().clone() for k,v in opt.state[p].items()} for n,p in model.named_parameters()}
    with torch.no_grad():
        for p in model.parameters():p.zero_()
    opt=torch.optim.AdamW(model.parameters(),lr=1e-5,weight_decay=1e-5);restore_checkpoint(model,opt,checkpoint,torch=torch,protocol_sha=sha(args.protocol),parameter_names=names);actual_loss=step();assert actual_loss==expected_loss
    for n,p in model.named_parameters():
        assert torch.equal(p,expected[n])
        for key,value in opt.state[p].items():assert torch.equal(value,expected_states[n][key])
    # Independent NumPy safetensors parser checks the standard public format.
    from safetensors.numpy import load_file
    independent=load_file(checkpoint['trainableWeights']);assert set(independent)==set(names)
    state.update(state='PASS_BOUNDED_CHECKPOINT_FULL_ADAMW_RNG_NEXT_UPDATE_EXACT',nextLossBitIdentical=True,nextWeightsBitIdentical=True,nextAdamWMomentsAndStepBitIdentical=True,independentNumpyFormatReadPassed=True,maximumCpuScratchBytes=checkpoint['maximumCpuScratchBytes'],checkpoint=checkpoint)
except BaseException as error:state.update(state='BOUNDED_CHECKPOINT_PROOF_FAILED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(wholeWorkerSeconds=time.perf_counter()-tick,finishedAt=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
