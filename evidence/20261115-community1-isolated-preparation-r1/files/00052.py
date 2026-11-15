"""Public dependency import control. No neural model or GPU initialization."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,traceback
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYANNOTE_METRICS_ENABLED='0')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-preflight-r1'
site=Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115/isolated-torchaudio-r1')
sys.path.insert(0,str(site))
report={'state':'STARTING_ISOLATED_TORCHAUDIO_IMPORT','at':datetime.now().astimezone().isoformat(),
 'isolatedSite':str(site),'existingRuntimeChanged':False,'gatedModelAccessed':False,'newNeuralCalls':0,'qualityQualified':False}
try:
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 report.update(torchVersion=torch.__version__,torchOrigin=torch.__file__,hipVersion=torch.version.hip)
 assert torch.__version__=='2.11.0+rocm10.0.0' and not torch.cuda.is_initialized()
 import torchaudio
 assert Path(torchaudio.__file__).is_relative_to(site) and torchaudio.__version__.startswith('2.11.1')
 # A constant is reproduced by the documented identity-rate operation exactly.
 samples=torch.tensor([[0.,.25,-.5,.75,0.,-.25,.5,-.75]],dtype=torch.float32)
 identity=torchaudio.functional.resample(samples,16000,16000)
 assert torch.equal(identity,samples)
 # Exercise actual resampling on a zero signal; expected value is analytically
 # zero, including every edge. This does not test model quality or full ABI use.
 zeros=torchaudio.functional.resample(torch.zeros(1,1600),16000,8000)
 assert tuple(zeros.shape)==(1,800) and torch.count_nonzero(zeros).item()==0
 report.update(state='PASS_ISOLATED_TORCHAUDIO_IMPORT_AND_BASIC_CPU_AUDIO_CONTROLS',
  torchaudioVersion=torchaudio.__version__,torchaudioOrigin=torchaudio.__file__,
  gpuInitialized=torch.cuda.is_initialized(),identityRateExact=True,zeroResampleExact=True)
 assert report['gpuInitialized'] is False
except BaseException as error:
 report.update(state='FAIL_ISOLATED_TORCHAUDIO_IMPORT_RETAINED',error=repr(error),traceback=traceback.format_exc())
 raise
finally:
 report['limits']=limits.query()
 target=D/'torchaudio-import-control.json';assert not target.exists()
 target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='traceback'},ensure_ascii=False))
