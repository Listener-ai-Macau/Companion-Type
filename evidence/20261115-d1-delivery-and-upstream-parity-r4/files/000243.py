"""Use the author's supported GPU log-mel path under the same host RAM cap."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,time,traceback,wave
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1')
inventory=json.loads((C/'hip-inventory.json').read_text());assert inventory['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
os.environ.update(HIP_VISIBLE_DEVICES=str(inventory['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
os.environ.pop('CUDA_VISIBLE_DEVICES',None);os.environ.pop('ROCR_VISIBLE_DEVICES',None)
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
target=C/'processor-gpu-proof.json';assert not target.exists();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();assert not pressure.low()
state={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARING_AUTHOR_GPU_INPUT_PATH','modelLoaded':False,'neuralInferenceAdded':0,'referenceOpened':False,'results':[],'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def save(stage):
    state.update(stage=stage,limits=limits.query());atomic_json(target,state)
save('BEFORE_IMPORTS')
try:
    import torch,numpy as np,transformers
    from transformers import AutoProcessor
    torch.set_num_threads(1);assert torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0);torch.cuda.set_device(0)
    root='E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/model';processor=AutoProcessor.from_pretrained(root,local_files_only=True)
    assert processor.feature_extractor.dither==0
    cache=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/processor-control');cache.mkdir(exist_ok=False)
    np.save(cache/'official-mel-filters-f32.npy',processor.feature_extractor.mel_filters.astype(np.float32))
    audio=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/engine-smoke30s-restored.wav')
    with wave.open(str(audio),'rb') as f:
        assert f.getframerate()==16000 and f.getsampwidth()==2 and f.getnchannels()==1;original=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
    for ident,samples in [('synthetic-silence3s',np.zeros(3*16000,dtype=np.float32)),('public-compat30s',original)]:
        save('BEFORE_INPUT_'+ident);t=time.perf_counter()
        inputs=processor.apply_transcription_request(audio=samples,language='Chinese',processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':'cuda:0'}})
        torch.cuda.synchronize();seconds=time.perf_counter()-t;assert all(torch.isfinite(value).all() for value in inputs.values())
        assert inputs['input_ids'].dtype==torch.long
        np.save(cache/(ident+'-waveform.npy'),samples);np.save(cache/(ident+'-features.npy'),inputs['input_features'].cpu().numpy())
        np.save(cache/(ident+'-mask.npy'),inputs['input_features_mask'].cpu().numpy())
        state['results'].append({'case':ident,'seconds':seconds,'inputShapes':{k:list(v.shape) for k,v in inputs.items()},'sampleCount':len(samples),'features':str(cache/(ident+'-features.npy'))})
        save('AFTER_INPUT_'+ident)
    state.update(state='PASS_AUTHOR_GPU_PROCESSOR_NO_NEURAL_WEIGHTS_NUMERIC_CHECK_PENDING',featureConfig={'nFft':processor.feature_extractor.n_fft,'hopLength':processor.feature_extractor.hop_length,'nSamples':processor.feature_extractor.n_samples,'nWindow':processor.feature_extractor.n_window,'dither':processor.feature_extractor.dither},officialGpuPathUnmodified=True,qualityQualified=False)
except BaseException as error:
    state.update(state='AUTHOR_GPU_PROCESSOR_FAILED_NOT_MODEL_QUALITY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    pressure.close();save('FINISHED_OR_EXITED');print(json.dumps(state),flush=True)
