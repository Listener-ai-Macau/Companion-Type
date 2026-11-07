"""Matching frozen native ECAPA identity audit; no text, references or threshold fit."""
from pathlib import Path
from datetime import datetime
import hashlib,importlib.util,json,os,sys,time,traceback,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(C/'identity-policy.json');assert sha(__file__)==P['workerSourceSha256']
assert sha(C/'model-ready.json')==P['modelReadySha256'];assert sha(C/'identity-audio-only.json')==P['audioPlanSha256']
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);target=C/'identity-state.json';assert not target.exists();tick=time.perf_counter()
state={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'LOADING_MATCHED_NATIVE_SPEAKER_ENCODER','newNeuralCalls':0,'referenceOrTextPassed':False,'qualityQualified':False}
atomic_json(target,state)
try:
    frontend=read(C/'audio-frontend-source.json')
    for row in frontend['files']:assert sha(row['file'])==row['sha256']
    sys.path.insert(0,frontend['pythonPath'])
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip and torch.cuda.device_count()==1
    info=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in info.name and info.gcnArchName.startswith('gfx1030')
    torch.cuda.set_device(0)
    ready=read(C/'model-ready.json')
    for item in ready['files']:assert sha(item['file'])==item['sha256']
    spec=importlib.util.spec_from_file_location('pinned_ps4_identity',Path(ready['sourceRoot'])/'inference.py');author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
    model=author.build_model(torch.device('cuda:0'));checkpoint=torch.load(ready['weight'],map_location='cpu',weights_only=True,mmap=True)
    weights=checkpoint.get('model',checkpoint.get('state_dict',checkpoint))
    if all(k.startswith('module.') for k in weights):weights={k.removeprefix('module.'):v for k,v in weights.items()}
    result=model.load_state_dict(weights,strict=True);assert not result.missing_keys and not result.unexpected_keys
    del checkpoint,weights
    plan=read(C/'identity-audio-only.json');embeddings={};latencies=[]
    for item in plan:
        assert sha(item['audio'])==item['audioSha256']
        with wave.open(item['audio'],'rb') as stream:
            assert stream.getframerate()==16000 and stream.getsampwidth()==2 and stream.getnchannels()==1
            value=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768
        peak=float(np.max(np.abs(value)));assert peak>0
        waveform=torch.from_numpy(value/peak).unsqueeze(0).to('cuda:0');torch.cuda.synchronize();start=time.perf_counter()
        with torch.inference_mode():
            # Exact author BSRNN.forward enrollment encoder path; no substitute embedding space.
            features=model.preEmphasis(waveform);features=model.spk_encoder(features)+1e-8
            features=features.log();features=features-features.mean(dim=-1,keepdim=True);features=features.permute(0,2,1)
            embedding=model.spk_model(features);embedding=embedding[-1] if isinstance(embedding,tuple) else embedding
            embedding=torch.nn.functional.normalize(embedding,dim=-1)
        torch.cuda.synchronize();latencies.append(time.perf_counter()-start);assert embedding.shape==(1,192) and torch.isfinite(embedding).all()
        embeddings[item['id']]=embedding.detach().cpu();state['newNeuralCalls']+=1
        state.update(state='VERIFYING_FROZEN_AUDIO_IDENTITIES',lastId=item['id'],limits=limits.query());atomic_json(target,state);time.sleep(1)
    comparisons=[]
    for item in plan:
        if item['kind']!='extracted-lane':continue
        candidates=[r for r in plan if r['kind']=='anchor' and r['meeting']==item['meeting']]
        scores={r['predictedSpeaker']:float((embeddings[item['id']]*embeddings[r['id']]).sum()) for r in candidates}
        ordered=sorted(scores,key=lambda p:(-scores[p],p));best=ordered[0]
        comparisons.append({'id':item['id'],'meeting':item['meeting'],'requestedPredictedSpeaker':item['predictedSpeaker'],
            'top1PredictedSpeaker':best,'targetIsTop1':best==item['predictedSpeaker'],
            'similarities':scores,'top1MinusSecond':scores[best]-scores[ordered[1]] if len(ordered)>1 else None,
            'decisionUsesAudioOnlyFrozenArgmaxNotGroundTruth':True})
    state.update(state='COMPLETE_NATIVE_PS4_IDENTITY_VERIFICATION_AUDIT',comparisons=comparisons,
        sameCheckpointEncoderUsed=True,noAbsoluteThreshold=True,noAudioOrTextDeletedByThisProbe=True,
        inferenceSeconds=sum(latencies),gpu=info.name)
except BaseException as error:
    state.update(state='FAILED_IDENTITY_AUDIT_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state),flush=True)
