from pathlib import Path
from datetime import datetime
import hashlib,json,math,os,shutil,sys,urllib.request,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from reference_textgrid_20261104 import read_reference_intervals
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'independent-voice-return-probe-r1';C.mkdir(exist_ok=True)
K=Path('E:/CodexData/Companion/.model-cache/wespeaker-public-20261115');K.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'audio-only.json').exists()
revision='837717ddb9ff5507820346191109dc79c958d614';repo='pyannote/wespeaker-voxceleb-resnet34-LM'
metadata=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'/revision/'+revision,timeout=30))
assert metadata['gated'] is False and not metadata['private'] and metadata['sha']==revision
assert metadata['cardData']['license']=='cc-by-4.0'
tree=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'/tree/'+revision,timeout=30))
write(C/'public-model-metadata.json',dict(repository=repo,metadata=metadata,tree=tree,accountOrTokenUsed=False))
files=[]
for name in ['pytorch_model.bin','config.yaml','README.md']:
    info=next(x for x in tree if x['path']==name);out=K/name
    if not out.exists():
        partial=out.with_suffix(out.suffix+'.part');assert not partial.exists()
        with urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+revision+'/'+name,timeout=45) as response,partial.open('xb') as f:
            count=0
            while block:=response.read(256*1024):count+=len(block);assert count<=info['size'];f.write(block)
        assert count==info['size']
        if 'lfs' in info:assert sha(partial)==info['lfs']['oid']
        partial.replace(out)
    assert out.stat().st_size==info['size']
    if 'lfs' in info:assert sha(out)==info['lfs']['oid']
    files.append(dict(file=str(out),bytes=out.stat().st_size,sha256=sha(out)))
write(C/'model-binding.json',dict(repository=repo,revision=revision,gated=False,accountOrTokenUsed=False,files=files))
audio=Path('E:/CodexData/Companion/.model-cache/ordinary-combination-study-20261114/ordinary-mic0.wav')
assert sha(audio)=='8928600b2cc089ed3ae413cb9fed1706149075f70fd37cb11f7b87aecc05067c'
reference=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/official-annotations/20200623_S_R001S07C01.TextGrid')
assert sha(reference)=='d876d6c4b713ba3b0fb3bd189db0d753c09e66abbde616a6fa2d6ec63e80b04a'
rows=sorted([r for r in read_reference_intervals(reference) if r['text'].strip()],key=lambda r:(r['start'],r['end'],r['speaker']))
eligible=[r for r in rows if 3<=r['end']-r['start']<=8 and not any(o is not r and o['start']<r['end'] and o['end']>r['start'] for o in rows)]
people=sorted({r['speaker'] for r in rows});assert len(people)==4
profiles=[next(r for r in eligible if r['speaker']==person and r['end']<1040.94) for person in people]
queries=[r for r in eligible if r['speaker']=='003-M' and r['start']>=1484.118704][:3]
assert len(queries)==3
audio_only=[];scoring=[]
with wave.open(str(audio),'rb') as src:
    assert (src.getframerate(),src.getnchannels(),src.getsampwidth())==(16000,1,2)
    for i,row in enumerate(profiles+queries):
        low=math.ceil(row['start']*16000);high=math.ceil(row['end']*16000)
        src.setpos(low);pcm=src.readframes(high-low);out=K/'audio'/('clip-'+str(i+1).zfill(2)+'.wav');out.parent.mkdir(exist_ok=True)
        assert not out.exists()
        with wave.open(str(out),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm)
        item=dict(id='clip-'+str(i+1).zfill(2),audio=str(out),audioSha256=sha(out),audioSeconds=(high-low)/16000)
        audio_only.append(item);scoring.append(dict(**item,role='profile' if i<4 else 'query',referenceSpeaker=row['speaker'],sourceStartFrame=low,sourceEndFrame=high,referenceUtterance=row))
write(C/'audio-only.json',audio_only);write(C/'scoring-only.json',scoring)
write(C/'planned-probe.json',dict(state='FROZEN_PUBLIC_REFERENCE_ASSISTED_VOICE_DISCRIMINATION_DIAGNOSIS_NOT_DIARIZATION',
    at=datetime.now().astimezone().isoformat(),selection='Earliest complete3–8s lexical nonoverlap utterance of each of4reference people before1040.94s; first3complete3–8s nonoverlap utterances of returning003-M after1484.118704s. Deterministic first by annotation time, no model output used. No padding or enhancement.',
    neuralInput='Seven anonymous mic0 clips only; no labels, profiles/queries or speaker counts supplied to the neural extractor.',
    diagnosticOnly='Reference-assisted cuts and4profile identities supplied only to independent diagnostic scorer. Successful ranking cannot establish unsupervised speaker counting, whole-meeting DER, actual segmentation/clustering or product quality.',
    keepRule='All3return queries must have highest cosine against their own earlier profile. Otherwise stop this fixed probe; no new reference profiles, durations, thresholds or selected query variants. Passing permits designing one original whole-meeting combination only.',
    numericalControl='Unmodified public checkpoint FP32 CPU/GPU first waveform fbank max<=.003,mean<=.0001; complete embeddings cosine>=.9999. No tolerance changes after results.',
    reason='Original full official/native Nemotron and neutral-cache control reproduce high-confidence long-absence identity confusion. Two fixed small public adapters failed. An independent speaker-verification representation differs from reaveraging Nemotron embeddings or tuning its cache.',
    originalAudioSha256=sha(audio),originalReferenceSha256=sha(reference),
    ownerParticipationRequired=False,accountOrTokenUsed=False,newTraining=False,qualityQualified=False,
    finalHoldoutOpened=False,allInputPublic=True,limits=limits.query()))
print(json.dumps({'control':str(C),'publicModelFiles':files,'clips':len(audio_only),'seconds':sum(r['audioSeconds'] for r in audio_only)},ensure_ascii=False))
