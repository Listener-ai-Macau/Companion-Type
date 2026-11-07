"""Pin one official native-HF ASR control; no community ONNX or training."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,urllib.request
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--metadata-only',action='store_true');a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1'
E=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/model')
C.mkdir(exist_ok=True);E.mkdir(parents=True,exist_ok=True)
model='Qwen/Qwen3-ASR-0.6B-hf';rev='7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c'
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def fetch_json(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-native-model-control'}),timeout=30))
data=fetch_json('https://huggingface.co/api/models/'+model+'/revision/'+rev+'?blobs=true');assert data['sha']==rev
files=[]
for item in data['siblings']:
    name=item['rfilename']
    if name=='.gitattributes':continue
    if a.metadata_only and name=='model.safetensors':continue
    assert '/' not in name and name in ['README.md','chat_template.jinja','config.json','generation_config.json','model.safetensors','processor_config.json','tokenizer.json','tokenizer_config.json']
    dest=E/name;expected=item.get('lfs',{}).get('sha256');expected_blob=item.get('blobId');size=item['size']
    def digest(path):
        with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    if not dest.exists():
        part=dest.with_suffix(dest.suffix+'.part');assert not part.exists(),'Preserve partial download and inspect before a retry'
        url='https://huggingface.co/'+model+'/resolve/'+rev+'/'+name+'?download=true'
        atomic_json(C/'download-state.json',{'at':now(),'state':'DOWNLOADING_PINNED_PUBLIC_MODEL','file':name,'expectedBytes':size,'inferenceStarted':False})
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-native-model-control'}),timeout=45) as response,part.open('xb') as stream:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                stream.write(chunk)
            stream.flush();os.fsync(stream.fileno())
        assert part.stat().st_size==size
        if expected:assert digest(part)==expected
        else:assert hashlib.sha1(b'blob '+str(size).encode()+b'\0'+part.read_bytes()).hexdigest()==expected_blob
        os.replace(part,dest)
    assert dest.stat().st_size==size
    actual=digest(dest)
    if expected:assert actual==expected
    else:assert hashlib.sha1(b'blob '+str(size).encode()+b'\0'+dest.read_bytes()).hexdigest()==expected_blob
    files.append({'file':str(dest),'bytes':size,'sha256':actual,'verifiedAgainst':'LFS SHA256' if expected else 'Pinned Git blob SHA1'})
    atomic_json(C/'download-state.json',{'at':now(),'state':'PINNED_FILE_VERIFIED','file':name,'completedFiles':len(files),'inferenceStarted':False})
if a.metadata_only:
    atomic_json(C/'metadata-only.json',{'at':now(),'state':'PINNED_PROCESSOR_METADATA_VERIFIED_NO_MODEL_WEIGHTS_READY_CLAIM','files':files,'inferenceStarted':False})
    print(json.dumps({'state':'PINNED_PROCESSOR_METADATA_VERIFIED_NO_MODEL_WEIGHTS_READY_CLAIM','files':len(files)}));raise SystemExit(0)
protocol={'modelId':model,'revision':rev,'modelRoot':str(E),'files':files,'backend':'official_native_transformers','dtype':'bfloat16','attnImplementation':'eager','maxNewTokens':512,'doSample':False,'language':'Chinese','prompt':None,'batchSize':1,'windowSamples':480000,'cpuPercent':5,'privateCommitLimitBytes':2*1024**3,'devicePolicy':'Enumerate current HIP descriptions; unique external RX6800XT only, no ordinal guess or integrated fallback.','cooperativePauseSeconds':1.,'earlyGate':'Public engine-smoke30s-restored.wav and original S first30s, fixed before inference; no reference/hotwords to worker. Require natural EOS, no loop, finite complete inputs and correct output format. Then both same full Chinese development meetings if resource/execution gate passes; quality gate still5%.','qualified':False}
protocol.update(featureDevice='selected_gpu',textPostprocessing='direct_tokenizer_skip_special_tokens_only_no_cleanup_no_repetition_fix',supportedGpuFeatureNumericProof=str(C/'processor-numeric-proof.json'))
atomic_json(C/'protocol.json',protocol)
atomic_json(C/'prepared.json',{'at':now(),'state':'PINNED_OFFICIAL_NATIVE_HF_MODEL_READY_NO_INFERENCE','protocol':str(C/'protocol.json'),'oldFailureBoundary':'Previous Qwen1.7B community mixed-precision ONNX+sherpa repeated. Not retrying that graph/decoder or deleting repeats. This uses an official Qwen-hosted native checkpoint and existing Transformers5.22.1 implementation, greedy unfiltered generation, no repetition penalty or reference prompt. Native HIP long-decoder crash history remains unresolved; no long run before short control.','weightsBytes':sum(f['bytes'] for f in files),'modelLicenseTag':data.get('cardData',{}).get('license'),'noGlobalPackagesInstalled':True,'source':'https://huggingface.co/'+model+'/tree/'+rev,'fullQualityQualified':False})
print(json.dumps({'state':'PINNED_OFFICIAL_NATIVE_HF_MODEL_READY_NO_INFERENCE','files':len(files),'weightsBytes':sum(f['bytes'] for f in files)}))
