"""Acquire only the official alternate serialization of the retained model."""
from pathlib import Path
from datetime import datetime,timedelta
import hashlib,json,shutil,sys,urllib.request,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
R=S.parent.parent;J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
cache=Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107/hf-reference-f667ed7')
run=E/'native8-reference-fidelity-r1';assert not run.exists();run.mkdir();cache.mkdir(exist_ok=False)
assert shutil.disk_usage(cache).free>50*1024**3
rev='f667ed73aee57d40cc39428eb768b4fd87a0a29e';repo='nvidia/Nemotron-3-Diarization'
base='https://huggingface.co/'+repo+'/resolve/'+rev+'/'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def fetch(url,path,cap):
    n=0;h=hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-fixed-reference-check'}),timeout=45) as response,path.open('xb') as out:
        while chunk:=response.read(1024**2):
            n+=len(chunk);assert n<=cap;out.write(chunk);h.update(chunk)
    return {'bytes':n,'sha256':h.hexdigest()}
metadata=run/'pinned-tree.json';fetch('https://huggingface.co/api/models/'+repo+'/tree/'+rev,metadata,2*1024**2)
tree=json.loads(metadata.read_text(encoding='utf-8'));rows={r['path']:r for r in tree};files={}
for name in ['config.json','processor_config.json','model.safetensors','README.md']:
    row=rows[name];assert row['size']<410*1024**2
    info=fetch(base+name,cache/name,row['size']);assert info['bytes']==row['size']
    if row.get('lfs'):assert info['sha256']==row['lfs']['oid']
    files[name]=info
    atomic_json(run/'download-progress.json',{'files':files,'limits':limits.query()})
    print(json.dumps({'downloaded':name,**info}),flush=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
original=read(J/'igpu-native8-r3/audio-only.json')
control=next(r for r in original if r['meeting']=='cpu-native8-control61')
english=next(r for r in original if r['meeting']=='ES2003b')
cases=[]
for source,label,native in [(control,'Chinese-control61','cpu-native8-control61'),(english,'ES2003b-control61','ES2003b')]:
    assert sha(source['audio'])==source['audioSha256']
    with wave.open(source['audio'],'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,16000)
        pcm=f.readframes(61*16000);assert len(pcm)==61*16000*2
    audio=run/(label+'.wav')
    with wave.open(str(audio),'wb') as f:f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(pcm)
    native_root=E/'igpu-native8-r3/probabilities'/native
    cases.append({'id':label,'audio':str(audio),'audioSha256':sha(audio),'pcmSha256':hashlib.sha256(pcm).hexdigest(),
        'frames':976000,'sourceAudioSha256':source['audioSha256'],'sourceOffsetSamples':0,
        'nativeProbabilities':str(native_root/'probabilities.npy'),'nativeManifest':str(native_root/'probabilities.json'),
        'nativeManifestSha256':sha(native_root/'probabilities.json'),'comparePrefixFrames':5440})
blas=read(J/'context-activity-r1/silero-owner-observe-r4/protocol.json')['cpuBlas']
transformers=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/transformers')
dependencies=[S/'nemotron_reference_control_20261117.py',S/'companion_community1_adapter_20261115.py',S/'moss_windows_resource_limits_20261104.py',S/'durable_model_state_20261117.py']
dependencies+=list((transformers/'models/nemotron3_diarization').glob('*.py'))
dependencies+=[transformers/'models/nemotron_asr_streaming/feature_extraction_nemotron_asr_streaming.py']
protocol={'at':datetime.now().astimezone().isoformat(),'repo':repo,'revision':rev,'modelRoot':str(cache),'files':files,'cases':cases,
 'runtimePython':'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',
 'dependencies':{str(p):sha(p) for p in dependencies},'cpuBlas':blas,
 'cpuBudgetOwnerQuote':'允许约 25% CPU，继续后台实测','cpuPercentMaximum':25,'torchThreads':4,'blasThreads':1,
 'privateCommitBytes':2147483648,'minimumAvailableBytes':3414499000,'ramStableSeconds':60,
 'stopAt':(datetime.now().astimezone()+timedelta(minutes=20)).isoformat(),
 'modelDtype':'float32','attentionImplementation':'eager','device':'cpu','training':False,'referenceLabelsRead':False,
 'scope':'Same retained speaker model, independently published Transformers implementation. Not another model, no optimization/weight updates or threshold grid.',
 'geometry':{'chunk_length':340,'chunk_right_context':40,'chunk_left_context':0,'fifo_length':40,'speaker_cache_update_period':300,'speaker_cache_length':264},
 'comparison':'First5440 frames only: two complete27.2s chunks with sufficient original future context in both full native and61s reference. Ending/tail frames are excluded rather than aligned by labels.',
 'diagnosticBranchRule':{'activityThreshold':0.5,'materialActivityDisagreementFraction':0.01,
    'materialMeanAbsolutePosteriorDifference':0.01,'action':'A material discrepancy triggers frontend/weights/implementation diagnosis before any diarizer training. A near match retains the original model-quality diagnosis. This is no accuracy acceptance gate.'},
 'cpuTemperatureMode':'owner-authorized-observe-only','hardwareOsThermalControlsChanged':False,
 'nativeBaselineChanged':False,'finalHoldoutOpened':False,'qualityQualified':False}
atomic_json(run/'protocol.json',protocol)
print(json.dumps({'run':str(run),'protocolSha256':sha(run/'protocol.json'),'newNeuralCalls':0,'weightsAcquiredBytes':files['model.safetensors']['bytes']}),flush=True)
