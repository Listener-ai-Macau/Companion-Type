"""Actual published CPU signal processor and labels; no model or optimizer."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from meeting_acoustic_contract_20261116 import read,sha,require
from durable_model_state_20261117 import atomic_json
from moss_target_only_batch_20261117 import prepare_target_only_batch
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=E/'language-specific-adaptation-r1/chinese-moss-contract-r1'
out=C/'native-input-r1';out.mkdir(parents=True,exist_ok=False)
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
pressure=SystemRamPressure();began=time.monotonic()
state={'at':datetime.now().astimezone().isoformat(),'state':'PREPARING_CHINESE_MOSS_NATIVE_SIGNAL_AND_LABELS',
    'sourceSha256':sha(__file__),'batchHelperSha256':sha(S/'moss_target_only_batch_20261117.py'),
    'modelInstances':0,'neuralCalls':0,'optimizerInstances':0,'parameterUpdates':0,
    'trainingEnabled':False,'qualityQualified':False,'completed':[]}
def save(**values):
    state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state)
def stop():
    import psutil
    require(not pressure.low() and psutil.virtual_memory().available>=3414499000,'Original RAM floor')
    require(time.monotonic()-began<300,'Five-minute signal-only deadline')
    require(not(out/'stop.request').exists(),'Owned stop requested')
try:
    stop();save();proof=read(C/'export-r1/completed.json')
    require(proof['examples']==5027 and sha(proof['manifest'])==proof['manifestSha256'],'Frozen5027 targets differ')
    rows=[json.loads(line) for line in Path(proof['manifest']).read_text(encoding='utf-8').splitlines()]
    ids=list(dict.fromkeys([proof['minimumTarget']['id'],proof['maximumTarget']['id'],
        max(rows,key=lambda row:row['source']['frames'])['source']['id'],rows[0]['source']['id']]))
    chosen=[next(row for row in rows if row['source']['id']==identity) for identity in ids]
    state['selectedIds']=ids;state['selection']='Shortest answer, longest answer, longest audio, first fixed source; training data only.'
    save(state='IMPORTING_TORCH_FOR_SIGNAL_ONLY_NO_MODEL')
    import torch
    from companion_community1_adapter_20261115 import pin_rocm_blas
    B=read(J/'full-binding.json')
    state['blasThreadPin']=pin_rocm_blas(B['blas'],B['blasSha256'])
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
    require(not torch.cuda.is_initialized(),'Signal-only verification initialized a GPU')
    import numpy as np,transformers
    from transformers import AutoProcessor
    processor=AutoProcessor.from_pretrained(E/'native-model',local_files_only=True,trust_remote_code=False)
    require(processor.audio_token_id==151671 and processor.feature_extractor.sampling_rate==16000,'Pinned native frontend differs')
    audios=[];targets=[];target_ids=[]
    for row in chosen:
        stop();source=row['source'];require(sha(source['audio'])==source['audioSha256'],'Actual selected PCM differs')
        with wave.open(source['audio'],'rb') as w:
            require((w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,source['frames']),
                'Original mono source format differs')
            raw=w.readframes(w.getnframes())
        audios.append(np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768)
        targets.append(row['conversation'][2]['content']);target_ids.append(row['targetTokenIdsIncludingEos'])
    for side in ('left','right'):
        stop();processor.tokenizer.padding_side=side
        request,details=prepare_target_only_batch(processor,audios,targets,torch=torch,
            expected_target_ids=target_ids,heartbeat=stop)
        require(request['input_features'].device.type=='cpu' and torch.isfinite(request['input_features']).all(),
            'Invalid CPU signal features')
        require(not torch.is_grad_enabled() and all(not value.requires_grad for value in request.values() if torch.is_tensor(value)),
            'Signal-only batch acquired a gradient graph')
        state['completed'].append({'paddingSide':side,'cases':[{'id':identity,**detail} for identity,detail in zip(ids,details)],
            'inputFeatureShape':list(request['input_features'].shape),
            'inputFeatureSha256':hashlib.sha256(request['input_features'].contiguous().numpy().tobytes()).hexdigest(),
            'allOriginalTargetTokensAndEosSupervisedOnly':True,'allPromptExpandedAudioAndPaddingMasked':True})
        del request;save(state='CHECKED_ACTUAL_CHINESE_NATIVE_SIGNAL_AND_LABELS')
    require(not torch.cuda.is_initialized(),'Signal-only audit acquired GPU state')
    save(state='PASS_REAL_CHINESE_MOSS_NATIVE_SIGNAL_AUDIO_EXPANSION_AND_TARGET_ONLY_LEFT_RIGHT_LABELS_NO_MODEL',
        sourceManifestSha256=proof['manifestSha256'],processorSourceSha256=sha(Path(transformers.__file__).parent/'models/moss_transcribe_diarize/processing_moss_transcribe_diarize.py'),
        actualAudioFeatureExpansionProvenOnSelectedInputs=True,actualModelForwardBackwardProven=False,
        trainingAdmitted=False,gpuInitialized=False,cpuOrIntegratedGpuTraining=False,
        originalAishellCrossCorpusPersonIsolationProven=False,
        torchVersion=torch.__version__,transformersVersion=transformers.__version__,elapsedSeconds=time.monotonic()-began)
    atomic_json(out/'completed.json',state);print(json.dumps(state,ensure_ascii=False))
except BaseException as error:
    import traceback
    save(state='FAILED_CHINESE_NATIVE_SIGNAL_INPUT_RETAINED_NO_RETRY',error=repr(error),traceback=traceback.format_exc());raise
finally:pressure.close()
