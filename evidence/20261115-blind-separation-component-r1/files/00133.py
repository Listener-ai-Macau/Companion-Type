from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys,urllib.request
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'blind-separation-composition-r1';C.mkdir(exist_ok=True)
K=Path('E:/CodexData/Companion/.model-cache/blind-separation-composition-20261115');K.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'source-binding.json').exists()
revision='6b3774dc79c46ae8bed2a4fa5f706f0ac8c75c61'
paths=['LICENSE','clearvoice/clearvoice/config/inference/MossFormer2_SS_16K.yaml',
       'clearvoice/clearvoice/network_wrapper.py','clearvoice/clearvoice/utils/decode.py']
paths+=['clearvoice/clearvoice/models/mossformer2_ss/'+n for n in ['__init__.py','conv_module.py','fsmn.py','layer_norm.py','mossformer2.py','mossformer2_block.py']]
files=[]
for name in paths:
    url='https://raw.githubusercontent.com/modelscope/ClearerVoice-Studio/'+revision+'/'+name
    target=K/'source'/name;target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():target.write_bytes(urllib.request.urlopen(url,timeout=30).read())
    files.append(dict(file=str(target),sha256=sha(target),source=url,bytes=target.stat().st_size))
write(C/'source-binding.json',dict(repository='https://github.com/modelscope/ClearerVoice-Studio',revision=revision,files=files))
repo='alibabasglab/MossFormer2_SS_16K';revision='407cb030cd66340918ebb6c8cc63b18f8592cdbe'
meta=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'/revision/'+revision,timeout=30))
assert meta['sha']==revision and meta['gated'] is False and meta['cardData']['license']=='apache-2.0'
tree=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'/tree/'+revision,timeout=30))
write(C/'public-model-metadata.json',dict(metadata=meta,tree=tree,accountOrTokenUsed=False))
files=[]
for name in ['README.md','last_best_checkpoint','last_best_checkpoint.pt']:
    info=next(x for x in tree if x['path']==name)
    target=K/'model'/name;target.parent.mkdir(exist_ok=True)
    if not target.exists():
        assert shutil.disk_usage(K).free>30*1024**3+info['size']
        partial=target.with_suffix(target.suffix+'.part');assert not partial.exists()
        with urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+revision+'/'+name,timeout=45) as response,partial.open('xb') as out:
            n=0
            while block:=response.read(256*1024):n+=len(block);assert n<=info['size'];out.write(block)
        assert n==info['size']
        if 'lfs' in info:assert sha(partial)==info['lfs']['oid']
        partial.replace(target)
    assert target.stat().st_size==info['size']
    if 'lfs' in info:assert sha(target)==info['lfs']['oid']
    files.append(dict(file=str(target),bytes=target.stat().st_size,sha256=sha(target)))
write(C/'model-binding.json',dict(repository=repo,revision=revision,gated=False,accountOrTokenUsed=False,files=files))
old=D/'context-matched-baseline-r3';audio=read(old/'audio-only.json');assert len(audio)==32
write(C/'audio-only.json',audio)
write(C/'preparation.json',dict(state='PUBLIC_BLIND_TWO_OUTPUT_SEPARATION_COMPOSITION_INPUTS_READY',
    at=datetime.now().astimezone().isoformat(),sourceRoot=str(K/'source/clearvoice/clearvoice'),
    checkpoint=str(K/'model/last_best_checkpoint.pt'),cases=32,
    reuseOriginalCohort=True,baselineScoring=str(old/'baseline-score.json'),
    distinction='Public pretrained16k blind two-output separation; no speaker identity/profile/reference/true count supplied. Earlier failed22M speaker-conditioned extraction models and their shrinking/omission objectives are not reused.',
    firstDecision='One fixed component/numerical check then all original12natural multi-turn overlap windows and20single short-response controls through both outputs and unchanged native ASR. Count every word from both streams, including duplicates, leakage and empty-reference insertions. No output selection using reference or transcription confidence.',
    score='Diagnostic two-stream optimal reference utterance combination (ORC-style character distance), temporal order within each stream, all reference utterances assigned exactly once; original full-meeting gates/labels stay unchanged.',
    stop='No parameter/model/window/threshold sweep. Keep only if overlap total improves, neither source or single-speaker controls regress. Passing still requires full original meeting/person gates before adoption.',
    allAudioPublic=True,ownerParticipationRequired=False,finalHoldoutOpened=False,
    newNeuralCalls=0,newTrainingUpdates=0,qualityQualified=False,productDefaultChanged=False,limits=limits.query()))
print(json.dumps({'control':str(C),'sourceRoot':str(K/'source/clearvoice/clearvoice'),'modelFiles':files,'cases':32},ensure_ascii=False))
