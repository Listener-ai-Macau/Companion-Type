"""Probe public API and PCM input without loading a model or starting GPU."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,traceback
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYANNOTE_METRICS_ENABLED='0')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-preflight-r1'
root=Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115')
sys.path[:0]=[str(root/'isolated-pyannote-r1'),str(root/'isolated-torchaudio-r1')]
report={'state':'STARTING_ISOLATED_PYANNOTE_API_PROBE','at':datetime.now().astimezone().isoformat(),
 'existingRuntimeChanged':False,'gatedWeightsAccessed':False,'newNeuralCalls':0,'qualityQualified':False}
try:
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 assert torch.__version__=='2.11.0+rocm10.0.0' and not torch.cuda.is_initialized()
 from pyannote.audio import Pipeline
 import pyannote.audio
 from pyannote.audio.core.io import Audio,TORCHCODEC_AVAILABLE
 from pyannote.audio.telemetry.metrics import is_metrics_enabled
 from pyannote.core import Segment
 assert Path(pyannote.audio.__file__).is_relative_to(root/'isolated-pyannote-r1')
 assert not is_metrics_enabled()
 pcm=torch.tensor([-32768,-12345,-1,0,1,12345,32767,0],dtype=torch.int16).repeat(2000)
 waveform=pcm.to(torch.float32).reshape(1,-1)/32768
 input={'waveform':waveform,'sample_rate':16000}
 audio=Audio(sample_rate=16000,mono='downmix')
 actual,rate=audio(input)
 assert rate==16000 and torch.equal(actual,waveform)
 cropped,crop_rate=audio.crop(input,Segment(.125,.625))
 assert crop_rate==16000 and torch.equal(cropped,waveform[:,2000:10000])
 assert not torch.cuda.is_initialized()
 report.update(state='PASS_ISOLATED_PYANNOTE_IMPORT_AND_OFFICIAL_IN_MEMORY_PCM_EXACT',
  torchVersion=torch.__version__,torchOrigin=torch.__file__,pyannoteOrigin=pyannote.audio.__file__,
  gpuInitialized=False,telemetryEnabled=False,wholePcmExact=True,cropPcmExact=True,
  torchcodecNativeDecoderAvailable=TORCHCODEC_AVAILABLE,
  pipelineFromPretrainedCalled=False)
except BaseException as error:
 report.update(state='FAIL_ISOLATED_PYANNOTE_IMPORT_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
 report['limits']=limits.query();target=D/'pyannote-import-control.json';assert not target.exists()
 target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='traceback'},ensure_ascii=False))
