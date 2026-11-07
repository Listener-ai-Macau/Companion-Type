"""One fixed local-identity hypothesis, cached batches; no ASR text or GT input."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,importlib.util,json,os,sys,time,traceback,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-ps4-local-presence-r1');parent=C.parent/'practical-conditioned-ps4-full-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
P=read(C/'protocol.json');assert sha(__file__)==P['workerSourceSha256'] and sha(C/'audio-only.json')==P['inputPlanSha256']
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);target=C/'state.json';assert args.resume==target.exists();tick=time.perf_counter()
binding={'protocolSha256':sha(C/'protocol.json'),'inputPlanSha256':P['inputPlanSha256']}
state={'state':'PREPARING_LOCAL_NATIVE_IDENTITY_AUDIT','pid':os.getpid(),'at':datetime.now().astimezone().isoformat(timespec='seconds'),'binding':binding,'newForwardBatches':0,'reusedBatches':0,'completedWindows':0,'referenceOrAsrTextPassed':False,'qualityQualified':False}
if target.exists():
    old=read(target);assert old['binding']==binding
    archive=C/('prior-state-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
atomic_json(target,state)
try:
    frontend=read(parent/'audio-frontend-source.json')
    for f in frontend['files']:assert sha(f['file'])==f['sha256']
    sys.path.insert(0,frontend['pythonPath'])
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip and torch.cuda.device_count()==1
    gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
    torch.cuda.set_device(0);ready=read(parent/'model-ready.json')
    for f in ready['files']:assert sha(f['file'])==f['sha256']
    spec=importlib.util.spec_from_file_location('pinned_ps4_local',Path(ready['sourceRoot'])/'inference.py');author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
    model=author.build_model(torch.device('cuda:0'));checkpoint=torch.load(ready['weight'],map_location='cpu',weights_only=True,mmap=True)
    weights=checkpoint.get('model',checkpoint.get('state_dict',checkpoint))
    if all(k.startswith('module.') for k in weights):weights={k.removeprefix('module.'):v for k,v in weights.items()}
    loaded=model.load_state_dict(weights,strict=True);assert not loaded.missing_keys and not loaded.unexpected_keys
    del checkpoint,weights
    def pcm(file,start=0,end=None):
        with wave.open(file,'rb') as stream:
            assert stream.getframerate()==16000 and stream.getnchannels()==1 and stream.getsampwidth()==2
            hi=stream.getnframes() if end is None else end;stream.setpos(start)
            return np.frombuffer(stream.readframes(hi-start),dtype='<i2').astype(np.float32)/32768
    def encode(values):
        value=torch.from_numpy(np.stack(values)).to('cuda:0')
        with torch.inference_mode():
            features=model.preEmphasis(value);features=model.spk_encoder(features)+1e-8
            features=features.log();features-=features.mean(dim=-1,keepdim=True);features=features.permute(0,2,1)
            emb=model.spk_model(features);emb=emb[-1] if isinstance(emb,tuple) else emb
            return torch.nn.functional.normalize(emb,dim=-1)
    anchors=read(parent/'global-anchors.json');prototypes=[];people=[]
    for anchor in anchors:
        assert sha(anchor['audio'])==anchor['audioSha256'];value=pcm(anchor['audio']);peak=float(np.max(np.abs(value)));assert peak>0
        prototypes.append(encode([value/peak])[0]);people.append(anchor['speaker'])
    matrix=torch.stack(prototypes);plan=read(C/'audio-only.json');all_windows=[]
    for item in plan:
        assert sha(item['audio'])==item['audioSha256']
        for window in item['windows']:all_windows.append({**window,'id':item['id'],'audio':item['audio'],'requestedSpeaker':item['requestedSpeaker'],'sourceRootStartSample':item['sourceRootStartSample']})
    state.update(totalWindows=len(all_windows),gpu=gpu.name,state='ENCODING_FROZEN_LOCAL_WINDOWS')
    folder=C/'batches';folder.mkdir(exist_ok=True);results=[]
    for lo in range(0,len(all_windows),P['batchSize']):
        selected=all_windows[lo:lo+P['batchSize']];file=folder/('%06d.json'%lo)
        if file.exists():
            packet=read(file);assert packet['binding']==binding and packet['selected']==selected
            batch=packet['results'];state['reusedBatches']+=1
        else:
            values=[];positions=[];batch=[]
            for index,item in enumerate(selected):
                value=pcm(item['audio'],item['startSample'],item['endSample']);peak=float(np.max(np.abs(value)))
                batch.append({k:item[k] for k in ['id','startSample','endSample','requestedSpeaker','sourceRootStartSample']})
                if peak==0:batch[-1].update(exactDigitalZero=True,targetIsTop1=False,scores=None)
                else:values.append(value/peak);positions.append(index)
            if values:
                torch.cuda.synchronize();started=time.perf_counter();vectors=encode(values)
                scores=(vectors@matrix.T).detach().cpu().tolist();torch.cuda.synchronize()
                state['newForwardBatches']+=1
                for index,cosines in zip(positions,scores):
                    pairs={p:float(c) for p,c in zip(people,cosines)};top=sorted(pairs,key=lambda p:(-pairs[p],p))[0]
                    batch[index].update(scores=pairs,top1Speaker=top,targetIsTop1=top==batch[index]['requestedSpeaker'],exactDigitalZero=False)
            atomic_json(file,{'binding':binding,'selected':selected,'results':batch})
            time.sleep(1)
        results.extend(batch);state['completedWindows']=len(results);state['limits']=limits.query();atomic_json(target,state,progress=True)
    atomic_json(C/'local-scores.json',{'binding':binding,'results':results,'allWindowScoresRetained':True,'referenceUsed':False,'asrTextUsed':False})
    state.update(state='COMPLETE_LOCAL_IDENTITY_HYPOTHESIS_UNQUALIFIED')
except BaseException as error:
    state.update(state='FAILED_LOCAL_IDENTITY_HYPOTHESIS_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state),flush=True)
