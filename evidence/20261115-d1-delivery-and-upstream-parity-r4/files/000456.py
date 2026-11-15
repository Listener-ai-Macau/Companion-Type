"""Import-only isolation for native preparation failure; zero neural calls."""
from pathlib import Path
import os,json,sys
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1');limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
state={'state':'BEFORE_NUMPY','environment':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','HIP_VISIBLE_DEVICES']},'neuralCalls':0}
def save():state['limits']=limits.query();atomic_json(C/'import-only-probe.json',state);print(json.dumps(state),flush=True)
save()
import numpy
state.update(state='AFTER_NUMPY',numpyVersion=numpy.__version__);save()
import torch
state.update(state='AFTER_TORCH',torchVersion=torch.__version__);save()
frontend=json.loads((C.parent/'practical-conditioned-ps4-full-r1/audio-frontend-source.json').read_text());sys.path.insert(0,frontend['pythonPath'])
import torchaudio.compliance.kaldi
state.update(state='AFTER_NATIVE_KALDI_FRONTEND_ZERO_NEURAL_CALLS');save()
