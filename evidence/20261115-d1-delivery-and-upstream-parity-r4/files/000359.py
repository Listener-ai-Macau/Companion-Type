"""Unmodified pretrained target cue; float outputs, no oracle or activity gate."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,importlib.util,json,os,sys,time,traceback,uuid,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-joint-neural-spatial')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args();P=read(C/'protocol-r2.json');assert sha(__file__)==P['cueWorkerSha256']
for x in P['sourceFiles']:assert sha(x['file'])==x['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();target=C/'cue-state.json';binding={'protocolSha256':sha(C/'protocol-r2.json'),'workerSourceSha256':sha(__file__)}
if target.exists():
    assert args.resume and read(target)['binding']==binding;archive=C/('prior-cue-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
state={'state':'LOADING_MATCHED_TARGET_CUE_MODEL','pid':os.getpid(),'startedAt':datetime.now().astimezone().isoformat(),'binding':binding,'completedInputs':0,'newNeuralCalls':0,'reusedOutputs':0,'referencePassedToWorker':False,'qualityQualified':False}
def save():state['limits']=limits.query();atomic_json(target,state,progress=True)
save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);assert torch.version.hip and torch.cuda.device_count()==1;gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030');torch.cuda.set_device(0)
    ready=read(C/'model-ready.json')
    for x in ready['files']:assert sha(x['file'])==x['sha256']
    frontend=read(C/'audio-frontend-source.json')
    for x in frontend['files']:assert sha(x['file'])==x['sha256']
    sys.path.insert(0,frontend['pythonPath']);module=Path(ready['sourceRoot'])/'inference.py';spec=importlib.util.spec_from_file_location('pinned_joint_cue_author',module);author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author);assert Path(author.torchaudio.__file__).resolve().is_relative_to(Path(frontend['pythonPath']).resolve())
    checkpoint=torch.load(ready['weight'],map_location='cpu',weights_only=True,mmap=True);weights=checkpoint.get('model',checkpoint.get('state_dict',checkpoint));prefixed=all(k.startswith('module.') for k in weights)
    if prefixed:weights={k.removeprefix('module.'):v for k,v in weights.items()}
    model=author.build_model(torch.device('cuda:0'));loaded=model.load_state_dict(weights,strict=True);assert not loaded.missing_keys and not loaded.unexpected_keys
    actual=model.state_dict();assert set(actual)==set(weights);cpu_hash=hashlib.sha256();gpu_hash=hashlib.sha256()
    for key in sorted(weights):
        a=weights[key].detach().contiguous().cpu().numpy().tobytes();b=actual[key].detach().contiguous().cpu().numpy().tobytes();assert a==b;cpu_hash.update(key.encode()+a);gpu_hash.update(key.encode()+b)
    atomic_json(C/'cue-weight-roundtrip.json',{'state':'PASS_EXACT_AUTHOR_STATE_TENSORS_AND_GPU_BYTES','tensors':len(weights),'sourceTensorSha256':cpu_hash.hexdigest(),'deviceTensorSha256':gpu_hash.hexdigest(),'unmodifiedAuthorInference':True,'dtype':'float32','newTrainingRuns':0});del checkpoint,weights,actual,a,b
    state.update(state='GENERATING_ALL_KNOWN_TARGET_CUES',gpu=gpu.name);save();profiles=read(C/'profiles.json');folder=Path(P['derivedAudioRoot'])/'cue-floats';folder.mkdir(exist_ok=True);outputs=[]
    for case in read(C/'spatial-audio-only.json'):
        if case['kind']=='ordinary-regression':continue
        assert sha(case['audio'])==case['audioSha256']
        with wave.open(case['audio'],'rb') as f:
            assert f.getnchannels()==2 and f.getframerate()==16000 and f.getsampwidth()==2;count=f.getnframes();mixed=np.frombuffer(f.readframes(count),dtype='<i2').reshape(-1,2)[:,0].astype(np.float32)/32768
        for person in case['targetPeople']:
            anchor=next(x for x in profiles if x['meeting']==case['meeting'] and x['speaker']==person);assert sha(anchor['audio'])==anchor['audioSha256']
            with wave.open(anchor['audio'],'rb') as f:enroll=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
            enroll_peak=float(np.max(np.abs(enroll)));assert enroll_peak>0;enrollment=torch.from_numpy(enroll/enroll_peak).unsqueeze(0).to('cuda:0');pieces=[]
            for lo in range(0,count,480000):
                hi=min(count,lo+480000);identity=case['id']+f'-speaker-{person}-chunk-{lo}';receipt=C/'cue-outputs'/(identity+'.json');receipt.parent.mkdir(exist_ok=True)
                if receipt.exists():
                    row=read(receipt);assert row['binding']==binding and sha(row['floatAudio'])==row['floatAudioSha256'];state['reusedOutputs']+=1;pieces.append(row);save();continue
                assert not (C/'stop.request').exists();part=mixed[lo:hi];peak=float(np.max(np.abs(part)));assert peak>0;mixture=torch.from_numpy(part/peak).unsqueeze(0).to('cuda:0');torch.cuda.synchronize();start=time.perf_counter()
                with torch.inference_mode():voice=author.extract_speaker(model,mixture,enrollment,torch.device('cuda:0'))
                torch.cuda.synchronize();value=voice.numpy().reshape(-1).astype(np.float32)*peak;assert value.shape==(hi-lo,) and np.isfinite(value).all();elapsed=time.perf_counter()-start;dest=folder/(identity+'-'+uuid.uuid4().hex+'.npy')
                with dest.open('xb') as f:np.save(f,value);f.flush();os.fsync(f.fileno())
                row={'id':identity,'binding':binding,'case':case['id'],'meeting':case['meeting'],'predictedSpeaker':person,'startSampleWithinContext':lo,'endSampleWithinContext':hi,'floatAudio':str(dest),'floatAudioSha256':sha(dest),'profileSha256':anchor['audioSha256'],'sourcePairSha256':case['audioSha256'],'mixtureAuthorPeakNormalization':peak,'outputRestoredToOriginalMic0Amplitude':True,'enrollmentAuthorPeakNormalization':enroll_peak,'inferenceSeconds':elapsed,'referenceUsed':False,'activityGate':False,'voiceAdmission':False}
                atomic_json(receipt,row);pieces.append(row);state['newNeuralCalls']+=1;del voice,mixture,value;save();time.sleep(.25)
            outputs.append({'case':case['id'],'meeting':case['meeting'],'predictedSpeaker':person,'chunks':pieces,'contextSamples':count});state['completedInputs']+=1;save();del enrollment
    assert len(outputs)==11;atomic_json(C/'cue-manifest.json',outputs);state['state']='COMPLETE_ALL_KNOWN_SPEAKER_CUES_UNQUALIFIED'
except BaseException as error:state.update(state='FAILED_CUE_STAGE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state),flush=True)
