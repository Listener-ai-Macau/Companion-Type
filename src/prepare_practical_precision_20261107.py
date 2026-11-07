"""Prepare an isolated, exact-source precision control. No training or inference."""
from pathlib import Path
from datetime import datetime
import concurrent.futures,hashlib,json,os,shutil,urllib.request
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=R/'docs/handoffs/20261107-model-generation-recovery';C=base/'native8-precision-preparation';C.mkdir(exist_ok=True);prep=base/'nemotron-speaker-20261107-prep';E=Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107');S=E/'conversion-source';S.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));meta=read(prep/'model-metadata.json')
def get(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-source-fidelity-20261107'}),timeout=45)
def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
commit=json.load(get('https://api.github.com/repos/NVIDIA/NeMo-Speech.cpp/commits/v0.3.0'))['sha'];tree=read(prep/'runtime-source-tree.json');submodule=next(r['sha'] for r in tree['tree'] if r['path']=='llama.cpp');ggml_tree=json.load(get('https://api.github.com/repos/ggml-org/llama.cpp/git/trees/'+submodule+'?recursive=1'));assert not ggml_tree.get('truncated')
(C/'source-revisions.json').write_text(json.dumps({'nvidiaCommit':commit,'ggmlCommit':submodule,'modelRevision':meta['sha']},indent=2),encoding='utf8')
files=[('NVIDIA/NeMo-Speech.cpp',commit,r['path'],r['sha'],S/r['path']) for r in tree['tree'] if r['type']=='blob' and (r['path'].startswith('conversion/') and r['path'].endswith('.py') or r['path']=='LICENSE')]
files += [('ggml-org/llama.cpp',submodule,r['path'],r['sha'],S/'llama.cpp'/r['path']) for r in ggml_tree['tree'] if r['type']=='blob' and (r['path'].startswith('gguf-py/gguf/') and r['path'].endswith('.py') or r['path']=='LICENSE')]
def fetch(item):
    repo,revision,path,blob,dest=item;url='https://raw.githubusercontent.com/'+repo+'/'+revision+'/'+path;dest.parent.mkdir(parents=True,exist_ok=True)
    data=dest.read_bytes() if dest.exists() else get(url).read();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob,'Upstream source changed versus frozen Git blob'
    if not dest.exists():dest.write_bytes(data)
    return {'repository':repo,'revision':revision,'path':path,'gitBlob':blob,'sha256':hashlib.sha256(data).hexdigest(),'localFile':str(dest)}
with concurrent.futures.ThreadPoolExecutor(4) as pool:receipts=list(pool.map(fetch,files))
weight=next(x for x in meta['siblings'] if x['rfilename']=='Nemotron-3-Diarization.nemo');model=E/weight['rfilename'];url='https://huggingface.co/nvidia/Nemotron-3-Diarization/resolve/'+meta['sha']+'/'+weight['rfilename']
if not model.exists():
    temporary=model.with_suffix('.nemo.part')
    with get(url) as source,temporary.open('wb') as target:shutil.copyfileobj(source,target,1024*1024);target.flush();os.fsync(target.fileno())
    assert temporary.stat().st_size==weight['lfs']['size'] and sha(temporary)==weight['lfs']['sha256'];os.replace(temporary,model)
assert model.stat().st_size==weight['lfs']['size'] and sha(model)==weight['lfs']['sha256']
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARED_EXACT_AUTHOR_CONVERTER_AND_CHECKPOINT_NO_INFERENCE','checkpoint':str(model),'checkpointSha256':weight['lfs']['sha256'],'checkpointBytes':model.stat().st_size,'sourceRoot':str(S),'sourceFiles':receipts,'modelRevision':meta['sha'],'hypothesis':'Check deployment quantization before training or clustering tuning. First reproduce publishedQ8 tensors from exact official checkpoint/converter; only if provenance/metadata/tensors match, create higher-precision weights and compare the same fullL/S recordings with all inference/score settings fixed. Keep every failure and regression.','newNeuralInference':False,'trainingPerformed':False,'originalQualityTargetsUnchanged':True,'privateCommitLimitBytes':2147483648,'noGlobalPackageChanges':True}
(C/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:record[k] for k in ['state','checkpointBytes','checkpointSha256','sourceRoot']},ensure_ascii=False),flush=True)
