"""Non-neural CPU control for an observational cache wrapper."""
from pathlib import Path
import ctypes,hashlib,json,os,sys
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
import torch,numpy as np
torch.set_num_threads(1);torch.set_num_interop_threads(1)
lib=ctypes.CDLL(str(Path(sys.prefix)/'Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'))
lib.openblas_set_num_threads(1)
from transformers.models.nemotron3_diarization.configuration_nemotron3_diarization import Nemotron3DiarizationStreamingConfig
from transformers.models.nemotron3_diarization.modeling_nemotron3_diarization import Nemotron3DiarizationSpeakerCache
from trace_nemotron_cache_20261115 import install_cache_trace
D=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/nemotron-cache-trace-r1')
P=json.loads((D/'protocol.json').read_text())
out=Path('E:/CodexData/Companion/product-d1d2-20261114/nemotron-cache-trace-r1/cpu-control-r1');out.mkdir(parents=True)
config=Nemotron3DiarizationStreamingConfig()
assert config.num_speakers==8 and config.speaker_cache_length==264
cache=Nemotron3DiarizationSpeakerCache(config,fifo_length=40,speaker_cache_update_period=300)
generator=torch.Generator(device='cpu').manual_seed(20261115)
silence=torch.randn((512,),generator=generator)
packets=[]
with torch.inference_mode():
 for i in range(5):
  chunk=torch.randn((1,380,512),generator=generator)
  full=torch.cat([cache.get_embeds(chunk),chunk],dim=1)
  logits=torch.randn((1,full.shape[1]*8,8),generator=generator)
  logits[:,:,0]+=3
  cache.update(full,logits,silence,340)
  packets.append({'chunk':chunk,'logits':logits,
    'embeds':cache.embeds.clone(),'probs':cache.probs.clone(),'fifo':cache.fifo.clone(),
    'cacheFrames':cache.num_cache_frames,'fifoFrames':cache.num_fifo_frames})
 baseline=[cache.embeds.clone(),cache.probs.clone(),cache.fifo.clone()]
 original=Nemotron3DiarizationSpeakerCache.update
 restore=install_cache_trace(out/'trace',expected_source_sha256=P['upstreamCacheSourceSha256'],audio_seconds=136)
 observed=Nemotron3DiarizationSpeakerCache(config,fifo_length=40,speaker_cache_update_period=300)
 for i,packet in enumerate(packets):
  full=torch.cat([observed.get_embeds(packet['chunk']),packet['chunk']],dim=1)
  observed.update(full,packet['logits'],silence,340)
  assert observed.num_cache_frames==packet['cacheFrames'] and observed.num_fifo_frames==packet['fifoFrames']
  assert all(torch.equal(getattr(observed,key),packet[key]) for key in ['embeds','probs','fifo'])
  saved=np.load(out/'trace'/('cache-%04d.npy'%(i+1)),allow_pickle=False)
  assert np.array_equal(saved,observed.probs[:,:observed.num_cache_frames].numpy())
 restore();assert Nemotron3DiarizationSpeakerCache.update is original
 assert all(torch.equal(x,y) for x,y in zip(baseline,[observed.embeds,observed.probs,observed.fifo]))
state={'state':'PASS_CPU_ONLY_OBSERVATIONAL_WRAPPER_EXACT_CACHE_TENSORS_AND_RESTORE',
 'updates':5,'upstreamCompressionActuallyExercised':cache.is_compressed,
 'allCacheEmbeddingsProbabilitiesFifoAndSizesExact':True,'wrapperRestored':True,
 'modelLoaded':False,'gpuInitialized':False,'newNeuralCalls':0,
 'fullModelOutputExactControlStillRequired':True,'qualityQualified':False,'limits':limits.query()}
(out/'result.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
print(json.dumps(state))
