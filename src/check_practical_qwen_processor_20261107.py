"""Actual native input preparation with synthetic audio; zero neural weights."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,traceback
os.environ.update(HIP_VISIBLE_DEVICES='-1',CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1');target=C/'processor-proof-r2.json';assert not target.exists()
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();assert not pressure.low()
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARING_NATIVE_INPUT_ONLY','neuralModelLoaded':False,'neuralInferenceAdded':0,'referenceOpened':False,'syntheticAudioOnly':True}
def checkpoint(stage):
    result.update(stage=stage,updatedAt=datetime.now().astimezone().isoformat(timespec='seconds'),limits=limits.query());atomic_json(target,result)
checkpoint('BEFORE_TORCH_IMPORT')
try:
    import torch
    checkpoint('AFTER_TORCH_BEFORE_NUMPY')
    import numpy as np
    checkpoint('AFTER_NUMPY_BEFORE_TRANSFORMERS')
    import transformers
    checkpoint('BEFORE_AUTO_PROCESSOR_IMPORT')
    from transformers import AutoProcessor
    checkpoint('AFTER_AUTO_PROCESSOR_IMPORT')
    assert transformers.__version__=='5.22.1';torch.set_num_threads(1)
    root='E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/model'
    processor=AutoProcessor.from_pretrained(root,local_files_only=True)
    checkpoint('AFTER_PROCESSOR_BUILT_BEFORE_INPUT_PREPARATION')
    inputs=processor.apply_transcription_request(audio=np.zeros(3*16000,dtype=np.float32),language='Chinese',audio_kwargs={'sampling_rate':16000}).to('cpu',torch.bfloat16)
    assert all(torch.isfinite(value).all() for value in inputs.values()) and inputs['input_ids'].dtype==torch.long
    assert inputs['input_features_mask'].sum()>0 and not torch.cuda.is_initialized()
    result.update(state='PASS_OFFICIAL_NATIVE_PROCESSOR_SYNTHETIC_INPUT_NO_NEURAL_WEIGHTS',inputShapes={k:list(v.shape) for k,v in inputs.items()},inputDtypes={k:str(v.dtype) for k,v in inputs.items()},processorClass=type(processor).__name__,torchCudaInitialized=False,qualityQualified=False)
except BaseException as error:
    result.update(state='NATIVE_PROCESSOR_PREPARATION_FAILED_NOT_MODEL_QUALITY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    pressure.close();result['limits']=limits.query();atomic_json(target,result);print(json.dumps(result),flush=True)
