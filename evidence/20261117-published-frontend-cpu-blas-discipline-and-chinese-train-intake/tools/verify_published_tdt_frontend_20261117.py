"""Run published signal preprocessing only on actual training PCM; no model/optimizer."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from meeting_acoustic_contract_20261116 import read,sha,require
from durable_model_state_20261117 import atomic_json
from tdt_domain_adaptation_20261116 import inspect
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
protocol=J/'language-specific-adaptation-r1/prepared-r3/protocol.json';P=read(protocol);plan=inspect(P)
out=E/'language-specific-adaptation-r1/published-frontend-r4';out.mkdir(parents=True,exist_ok=False)
start=time.monotonic();pressure=SystemRamPressure()
state={'at':datetime.now().astimezone().isoformat(),'state':'PREPARING_PUBLISHED_CPU_SIGNAL_FRONTEND',
    'protocolSha256':sha(protocol),'sourceSha256':sha(__file__),'completed':[],
    'modelInstances':0,'neuralCalls':0,'optimizerInstances':0,'parameterUpdates':0,
    'referenceLabelsRead':False,'trainingManifestReadOnly':True,'qualityQualified':False}
def save(**values):
    state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
def stop():
    import psutil
    require(not pressure.low() and psutil.virtual_memory().available>=P['minimumAvailableBytes'],'Original RAM floor')
    require(time.monotonic()-start<300,'Bounded signal-only audit deadline')
try:
    save();stop()
    rows=[json.loads(l) for l in Path(plan['trainingManifest']).read_text(encoding='utf-8').splitlines() if l]
    require(len(rows)==1828 and all(r['role']=='train-only' for r in rows),'Frozen train-only scope')
    ids=[plan['largestJointCase']['id'],plan['longestCase']['id']]
    residues={}
    for row in rows:residues.setdefault((row['frames']//160)%8,row['id'])
    require(set(residues)==set(range(8)),'Actual source boundary residues incomplete')
    ids=list(dict.fromkeys(ids+[residues[k] for k in sorted(residues)]))
    state['selection']='Frozen largestjoint/longest, then first original training clip for each valid-feature-length residue modulo8; no quality outputs or validation labels used.'
    state['selectedIds']=ids;save()
    save(state='IMPORTING_TORCH_NO_MODEL')
    import torch
    from companion_community1_adapter_20261115 import pin_rocm_blas
    state['blasThreadPin']=pin_rocm_blas(P['blas']['file'],P['blas']['sha256'])
    save(state='PINNED_EXISTING_ROCM_OPENBLAS_ONE_THREAD')
    import numpy as np,transformers
    from transformers import AutoProcessor
    require(torch.__version__==P['runtime']['torch'] and transformers.__version__==P['runtime']['transformers'],'Frozen frontend runtime differs')
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
    require(not torch.cuda.is_initialized(),'Signal audit initialized GPU')
    processor=AutoProcessor.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
    require(processor._decoder_type=='tdt' and processor.feature_extractor.hop_length==160,'Published frontend changed')
    save(state='PUBLISHED_PROCESSOR_READY_WITH_EXISTING_BLAS_PIN')
    for identity in ids:
        stop();row=next(r for r in rows if r['id']==identity);require(sha(row['audio'])==row['audioSha256'],'Original training PCM changed')
        with wave.open(row['audio'],'rb') as w:
            require((w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,row['frames']),'Training PCM geometry')
            raw=w.readframes(w.getnframes())
        samples=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768
        tick=time.perf_counter()
        request=processor(audio=samples,sampling_rate=16000,return_tensors='pt',
            audio_kwargs={'truncation':False,'device':'cpu'})
        feature=request['input_features'];mask=request['attention_mask'];valid=int(mask.sum())
        require(feature.shape==(1,row['frames']//160+1,128),'Published STFT shape differs')
        require(mask.shape==feature.shape[:2] and valid==row['frames']//160,'Original valid feature length differs')
        require(torch.isfinite(feature).all() and feature.device.type=='cpu' and not feature.requires_grad,'Invalid signal features')
        require(torch.count_nonzero(feature[~mask]).item()==0,'Padded feature frame is not zero')
        projected=(valid+7)//8
        cells=projected*(len(row['targetIds'])+1)
        if identity==plan['largestJointCase']['id']:
            require(projected==plan['largestJointCase']['encoderFramesUpperBound'] and cells==plan['largestJointCase']['jointTokenCells'],'Actual largestjoint metadata differs')
        if identity==plan['longestCase']['id']:
            require(projected==plan['longestCase']['encoderFramesUpperBound'] and cells==plan['longestCase']['jointTokenCells'],'Actual longest metadata differs')
        require(all(type(i) is int and 0<=i<8192 and i not in (2,3) for i in row['targetIds']),'Special/pad/blank target entered loss')
        state['completed'].append({'id':identity,'sourceFrames':row['frames'],'featureShape':list(feature.shape),
            'validFeatureFrames':valid,'maskedPaddingFrames':int((~mask).sum()),'encoderFramesExpected':projected,
            'targetSubwords':len(row['targetIds']),'jointTokenCells':cells,'allFinite':True,
            'featureFloat32Sha256':hashlib.sha256(feature.contiguous().numpy().tobytes()).hexdigest(),
            'signalProcessingSeconds':time.perf_counter()-tick})
        del request,feature,mask,samples,raw;save(state='CHECKED_PUBLISHED_SIGNAL_FRONTEND')
    require(not torch.cuda.is_initialized() and not torch.is_grad_enabled(),'Signal-only audit acquired neural execution state')
    save(state='PASS_REAL_PUBLISHED_SIGNAL_FRONTEND_TRAIN_INPUTS_NO_MODEL_OR_TRAINING',
        actualLargestNeuralForwardBackwardProven=False,gpuInitialized=False,
        torchVersion=torch.__version__,transformersVersion=transformers.__version__,
        elapsedSeconds=time.monotonic()-start)
    atomic_json(out/'completed.json',state)
except BaseException as error:save(state='FAILED_SIGNAL_FRONTEND_RETAINED_NO_RETRY',error=repr(error));raise
finally:pressure.close()
print(json.dumps(state,ensure_ascii=False),flush=True)
