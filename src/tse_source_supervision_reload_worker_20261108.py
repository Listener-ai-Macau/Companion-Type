"""Independently reload complete frozen base and trained delta, then reproduce PCM."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha,load_models,load_pair
from companion_tse_training_20261108 import make_spatial_extractor
from companion_tse_checkpoint_streamed_20261108 import apply_trainable_weights
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False)
assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'RELOADING_COMPLETE_TSE_BASE_AND_TRAINED_PARAMETERS','pid':os.getpid(),'startedAt':datetime.now().astimezone().isoformat(),'newWeightUpdates':0,'qualityQualified':False};atomic_json(out/'state.json',state,progress=True)
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0)
    base,_,_=load_models(P,out,torch=torch,with_teacher=False);model=make_spatial_extractor(base,torch=torch).to('cuda:0').eval();checkpoint=P['checkpoint'];assert checkpoint['completedSteps']==128
    receipt=apply_trainable_weights(model,checkpoint['trainableWeights'],checkpoint['trainableWeightsSha256'],torch=torch)
    example=P['example'];pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');torch.cuda.synchronize();start=time.perf_counter()
    with torch.no_grad():value=(model(pair,profile)[0]*peak).float().cpu().numpy()
    torch.cuda.synchronize();elapsed=time.perf_counter()-start;divisor=max(1.,float(np.max(np.abs(value))));pcm=np.rint(value/divisor*32768).clip(-32768,32767).astype('<i2');expected=P['expectedValidationOutput'];assert sha(expected['audio'])==expected['audioSha256']
    with wave.open(expected['audio'],'rb') as f:assert f.getframerate()==16000 and f.getnchannels()==1 and f.getsampwidth()==2;original=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2')
    assert original.shape==pcm.shape;max_lsb=int(np.max(np.abs(original.astype(np.int32)-pcm.astype(np.int32))));assert max_lsb<=P['pcmMaximumLsbDifference']
    state.update(state='PASS_INDEPENDENT_TRAINED_WEIGHT_RELOAD_AND_PCM_REPRODUCTION',checkpoint=checkpoint['trainableWeightsSha256'],weights=receipt,exampleId=example['id'],audioSeconds=example['audioSeconds'],referenceProvidedToInference=False,pcmBitIdentical=bool(np.array_equal(pcm,original)),pcmMaximumLsbDifference=max_lsb,expectedAudioSha256=expected['audioSha256'],inferenceSeconds=elapsed,allTrainingParametersReloaded=True,exactFrozenBaseRequired=True,recognizerLoaded=False)
except BaseException as error:state.update(state='TRAINED_WEIGHT_RELOAD_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
