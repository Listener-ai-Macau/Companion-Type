"""Native author feature primitive only, with owned BLAS thread control."""
from pathlib import Path
import os,json,sys,wave
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1');read=lambda p:json.loads(Path(p).read_text());limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
state={'state':'IMPORTING_FEATURE_PRIMITIVE_ONLY','completedNeuralCalls':0}
def save():state['limits']=limits.query();atomic_json(C/'cpu-feature-probe.json',state);print(json.dumps(state),flush=True)
save()
import numpy as np
import torch
torch.set_num_threads(1);torch.set_num_interop_threads(1)
from threadpoolctl import threadpool_info,threadpool_limits
state['threadpoolsBefore']=threadpool_info();save()
front=read(C.parent/'practical-conditioned-ps4-full-r1/audio-frontend-source.json');sys.path.insert(0,front['pythonPath']);sys.path.insert(0,read(C/'model-ready.json')['sourceRoot']);import nomo_pvad
with threadpool_limits(limits=1):
    state.update(state='BEFORE_AUTHOR_CPU_FBANK_WITH_EXPLICIT_BLAS_LIMIT',threadpoolsAfter=threadpool_info());save()
    anchor=read(C/'automatic-enrollments.json')[0]
    with wave.open(anchor['audio'],'rb') as stream:pcm=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768
    fbank=nomo_pvad._eres2netv2_fbank(torch.from_numpy(pcm))
    state.update(state='COMPLETE_AUTHOR_CPU_FBANK_ZERO_NEURAL_CALLS',featureShape=list(fbank.shape),finite=bool(torch.isfinite(fbank).all()));save()
