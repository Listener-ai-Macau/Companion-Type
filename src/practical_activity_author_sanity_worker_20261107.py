"""One learned activity candidate on raw mixtures; exact native encoder classes."""
from pathlib import Path
from datetime import datetime
import argparse,ast,hashlib,importlib.util,json,math,os,sys,time,traceback,types,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True,choices=['pilot','short']);parser.add_argument('--resume',action='store_true');args=parser.parse_args()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1/author-sanity')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
P=read(C/'protocol.json');assert sha(__file__)==P['workerSourceSha256']
for file,key in [('audio-only.json','audioOnlySha256'),('automatic-enrollments.json','enrollmentPlanSha256'),('model-ready.json','modelReadySha256')]:assert sha(C/file)==P[key]
binding={'protocolSha256':sha(C/'protocol.json'),'workerSourceSha256':P['workerSourceSha256'],'modelReadySha256':P['modelReadySha256']}
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);target=C/(args.stage+'-state.json');assert target.exists()==args.resume;started=time.perf_counter()
state={'state':'PREPARING_MATCHED_TARGET_ACTIVITY','pid':os.getpid(),'stage':args.stage,'startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'binding':binding,'newNeuralCalls':0,'reusedOutputs':0,'completedInputs':0,'referenceOrTextPassedToModel':False,'qualityQualified':False}
if target.exists():
    old=read(target);assert old['binding']==binding
    archive=C/('prior-'+args.stage+'-state-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
atomic_json(target,state)
def phase(name):
    state.update(state=name,limits=limits.query());atomic_json(target,state);print(name,flush=True)
try:
    ready=read(C/'model-ready.json')
    for file in ready['files']:assert sha(file['file'])==file['sha256']
    frontend=read(ready['audioFrontendSource'])
    for file in frontend['files']:assert sha(file['file'])==file['sha256']
    sys.path.insert(0,frontend['pythonPath'])
    phase('IMPORTING_NUMPY')
    import numpy as np
    phase('IMPORTING_TORCH')
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip and torch.cuda.device_count()==1
    gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030');torch.cuda.set_device(0);phase('PREPARING_EXACT_NATIVE_ENCODER_CLASSES')
    # Execute byte-pinned native classes, omitting the unrelated SDK registry wrapper.
    msroot=Path(ready['modelscopeRoot'])
    for name in ['modelscope','modelscope.models','modelscope.models.audio','modelscope.models.audio.sv']:
        module=types.ModuleType(name);module.__path__=[str(msroot/Path(*name.split('.')))];sys.modules[name]=module
        if '.' in name:parent,short=name.rsplit('.',1);setattr(sys.modules[parent],short,module)
    def load_module(name,path):
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
        parent,short=name.rsplit('.',1);setattr(sys.modules[parent],short,module);return module
    folder=msroot/'modelscope/models/audio/sv';pool=load_module('modelscope.models.audio.sv.pooling_layers',folder/'pooling_layers.py');fusion=load_module('modelscope.models.audio.sv.fusion',folder/'fusion.py')
    source=ast.parse((folder/'ERes2NetV2.py').read_text(encoding='utf8'));wanted=['ReLU','BasicBlockERes2NetV2','BasicBlockERes2NetV2AFF','ERes2NetV2'];classes=[node for node in source.body if isinstance(node,ast.ClassDef) and node.name in wanted];assert [node.name for node in classes]==wanted
    class_hash=hashlib.sha256(ast.dump(ast.Module(body=classes,type_ignores=[]),include_attributes=False).encode()).hexdigest();assert class_hash==P['nativeEncoderClassAstSha256']
    module=types.ModuleType('modelscope.models.audio.sv.ERes2NetV2');module.__dict__.update(torch=torch,nn=torch.nn,F=torch.nn.functional,math=math,pooling_layers=pool,AFF=fusion.AFF)
    exec(compile(ast.Module(body=classes,type_ignores=[]),str(folder/'ERes2NetV2.py'),'exec'),module.__dict__);sys.modules[module.__name__]=module;setattr(sys.modules['modelscope.models.audio.sv'],'ERes2NetV2',module)
    strict_receipts=[];original_load=torch.nn.Module.load_state_dict
    def digest_state(model):
        h=hashlib.sha256()
        for key,value in model.state_dict().items():
            value=value.detach().cpu().contiguous();h.update(key.encode()+b'\0'+str(value.dtype).encode()+b'\0');h.update(value.numpy().tobytes())
        return h.hexdigest()
    def checked_load(model,weights,strict=True,assign=False):
        result=original_load(model,weights,strict=True,assign=assign)
        assert not result.missing_keys and not result.unexpected_keys
        for key,value in model.state_dict().items():assert torch.equal(value,weights[key].to(device=value.device,dtype=value.dtype)),key
        strict_receipts.append({'class':type(model).__name__,'tensorCount':len(model.state_dict()),'everyTensorValueEqual':True,'allParametersRequired':True,'loadedStateSha256':digest_state(model)})
        return result
    torch.nn.Module.load_state_dict=checked_load
    phase('IMPORTING_PINNED_NOMOPVAD')
    sys.path.insert(0,ready['sourceRoot']);import nomo_pvad
    featureproof=read(C/'gpu-feature-numeric-proof.json')
    assert featureproof['state']=='PASS_NATIVE_GPU_KALDI_FEATURES_INDEPENDENT_NUMPY_REFERENCE' and sha(C/'gpu-feature-numeric-proof.json')==P['gpuFeatureProofSha256']
    assert P['featureDevice']=='selected_gpu'
    native_feature=nomo_pvad._eres2netv2_fbank
    def gpu_feature(wav,sample_rate=16000):return native_feature(wav.to('cuda:0'),sample_rate)
    nomo_pvad._eres2netv2_fbank=gpu_feature
    phase('BUILDING_AND_STRICT_LOADING_MATCHED_MODELS')
    model=nomo_pvad.NomoPVAD(ready['weight'],ready['enrollmentDirectory'],device='cuda:0');model._ensure_eres()
    model_record=next(r for r in strict_receipts if r['class']=='NomoPVADNet');encoder_record=[r for r in strict_receipts if r['class']=='ERes2NetV2'][-1]
    assert digest_state(model.model)==model_record['loadedStateSha256'] and digest_state(model._eres)==encoder_record['loadedStateSha256']
    atomic_json(C/('loader-proof-'+args.stage+'-'+str(os.getpid())+'.json'),{'binding':binding,'nativeClassAstSha256':class_hash,'nativeClassSourceUnmodified':True,'unrelatedModelScopeSdkRegistryNotExecuted':True,'strictLoads':strict_receipts,'gpuModelAndEnrollmentStateBytesVerified':True,'matchedEmbeddingSpace':True,'gpu':gpu.name,'limits':limits.query()});phase('MATCHED_MODELS_VERIFIED_BEFORE_FIRST_NEURAL_CALL')
    def pcm(path):
        with wave.open(path,'rb') as stream:
            assert stream.getframerate()==16000 and stream.getnchannels()==1 and stream.getsampwidth()==2
            return np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768
    anchors=read(C/'automatic-enrollments.json');embfile=C/'native-enrollment-vectors.json'
    if embfile.exists():
        packet=read(embfile);assert packet['binding']==binding;embeddings=packet['vectors'];assert len(embeddings)==len(anchors);state['reusedOutputs']+=len(anchors)
    else:
        embeddings={}
        for anchor in anchors:
            phase('ENCODING_MATCHED_AUTOMATIC_PROFILES')
            assert sha(anchor['audio'])==anchor['audioSha256'];vector=model.extract_emb(pcm(anchor['audio']));assert vector.shape==(1,192) and torch.isfinite(vector).all()
            embeddings[anchor['meeting']+':'+str(anchor['speaker'])]=vector.detach().cpu().tolist();state['newNeuralCalls']+=1;state['completedInputs']+=1;atomic_json(target,state,progress=True);time.sleep(1)
        atomic_json(embfile,{'binding':binding,'vectors':embeddings,'matchingNativeEres2netv2':True,'referenceUsed':False})
    plan=read(C/'audio-only.json');selected=plan[:1] if args.stage=='pilot' else plan;outdir=C/'outputs';outdir.mkdir(exist_ok=True);outputs=[]
    for case in selected:
        assert sha(case['audio'])==case['audioSha256'];audio=pcm(case['audio']);assert len(audio)==case['endSample']-case['startSample']
        for person in case['allAnonymousTargets']:
            key=case['id']+'-speaker-'+str(person);file=outdir/(key+'.json');anchor=next(a for a in anchors if a['meeting']==case['meeting'] and a['speaker']==person)
            if file.exists():
                result=read(file);assert result['binding']==binding and result['inputAudioSha256']==case['audioSha256'] and result['enrollmentAudioSha256']==anchor['audioSha256'];state['reusedOutputs']+=1
            else:
                emb=torch.tensor(embeddings[case['meeting']+':'+str(person)],dtype=torch.float32,device='cuda:0')
                torch.cuda.synchronize();tick=time.perf_counter();probs=model.probs_on(emb,audio);torch.cuda.synchronize();elapsed=time.perf_counter()-tick
                assert np.isfinite(probs).all() and np.logical_and(probs>=0,probs<=1).all()
                feature_count=(len(audio)-400)//160+1;expected=(feature_count+15)//16;assert len(probs)==expected
                result={'id':key,'meeting':case['meeting'],'speaker':person,'binding':binding,'inputAudioSha256':case['audioSha256'],'enrollmentAudioSha256':anchor['audioSha256'],'probabilities':probs.tolist(),'featureFrames':feature_count,'chunkSamples':2560,'chunkCount':len(probs),'inputSamples':len(audio),'lastChunkClippedAtOriginalInputEnd':True,'authorOfflineProbsOnUnmodified':True,'inferenceSeconds':elapsed,'referenceOrAsrTextUsed':False}
                atomic_json(file,result);state['newNeuralCalls']+=1;time.sleep(1)
            outputs.append(str(file));state['completedInputs']+=1;state['completedQueries']=len(outputs);state['limits']=limits.query();atomic_json(target,state,progress=True)
    atomic_json(C/(args.stage+'-manifest.json'),{'binding':binding,'outputs':outputs,'queryCount':len(outputs),'newNeuralCalls':state['newNeuralCalls'],'reusedOutputs':state['reusedOutputs'],'allOriginalProbabilitiesRetained':True})
    state.update(state='COMPLETE_TARGET_ACTIVITY_'+args.stage.upper()+'_UNQUALIFIED')
except BaseException as error:state.update(state='FAILED_TARGET_ACTIVITY_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-started,limits=limits.query());atomic_json(target,state);print(json.dumps(state),flush=True)
