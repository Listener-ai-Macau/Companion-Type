"""Prepare one source-grounded acoustic adaptation; no neural model here."""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,os,shutil,sys,urllib.request,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from reference_textgrid_20261104 import read_reference_intervals
import soundfile as sf
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-acoustic-context-r1';C.mkdir(exist_ok=True)
E=Path('E:/CodexData/Companion/.model-cache/public-acoustic-context-20261115/data-r2');E.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'train.json').exists()
sources=[s for s in read(R/'docs/handoffs/20261108-tse-source-supervision/sources.json') if s['role']=='train']
revision='aada72727856313b19d4a030383c426364931dbf'
choice=read(C/'source-coverage-audit.json')['selectedAddition']
assert choice['meeting']=='20200707_L_R001S01C01'
path='train_L/wav/'+choice['meeting']+'.flac'
url='https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+revision+'/'+path
api='https://huggingface.co/api/datasets/AISHELL/AISHELL-4/tree/'+revision+'/train_L/wav?limit=100'
metadata=next(x for x in json.load(urllib.request.urlopen(api,timeout=30)) if x['path']==path)
assert 0<metadata['size']<512*1024**2 and metadata['lfs']['size']==metadata['size']
target=E/'sources'/Path(path).name;target.parent.mkdir(exist_ok=True)
write(C/'new-source-download-r2.json',dict(api=api,metadata=metadata,url=url,startedAt=datetime.now().astimezone().isoformat(),license='AISHELL4 CC-BY-SA-4.0 https://www.openslr.org/111/'))
if not target.exists():
    partial=target.with_suffix('.flac.part');assert not partial.exists()
    assert shutil.disk_usage(E).free>30*1024**3+metadata['size']
    with urllib.request.urlopen(url,timeout=45) as response,partial.open('xb') as out:
        copied=0
        while block:=response.read(256*1024):
            copied+=len(block);assert copied<=metadata['size'];out.write(block)
    assert copied==metadata['size'] and sha(partial)==metadata['lfs']['oid']
    partial.replace(target)
assert target.stat().st_size==metadata['size'] and sha(target)==metadata['lfs']['oid']
reference=Path(choice['reference']);assert sha(reference)==choice['referenceSha256']
sources.append(dict(role='train',meeting=choice['meeting'],localFlac=str(target),
                    expectedWholeFileLfsSha256=metadata['lfs']['oid'],reference=str(reference),
                    referenceSha256=sha(reference),url=url,repositoryRevision=revision,
                    referenceSource='Existing official AISHELL4 annotation archive extraction; raw file retained.'))
training=[];audits=[]
for source in sources:
    assert sha(Path(source['localFlac']))==source['expectedWholeFileLfsSha256']
    assert sha(Path(source['reference']))==source['referenceSha256']
    info=sf.info(source['localFlac']);assert info.channels==8 and info.samplerate==16000 and info.subtype=='PCM_16'
    rows=sorted([r for r in read_reference_intervals(source['reference']) if r['text'].strip()],key=lambda r:(r['start'],r['end'],r['speaker']))
    components=[];end=-1.
    for row in rows:
        if row['start']>=end:components.append([])
        components[-1].append(row);end=max(end,row['end'])
    plans=[]
    for i,component in enumerate(components):
        if len(component)!=1:continue
        contained=[]
        for more in components[i:]:
            if len(more)!=1 or more[0]['end']-component[0]['start']>29.84:break
            contained+=more
        if len({r['speaker'] for r in contained})<2:continue
        if contained[-1]['end']-contained[0]['start']<4:continue
        if not any(r['end']-r['start']<2 for r in contained):continue
        if any('<' in r['text'] or '>' in r['text'] for r in contained):continue
        plans.append(contained)
    selected=[];last=-1.
    for plan in plans:
        if plan[0]['start']>=last+.16:selected.append(plan);last=plan[-1]['end']
    assert len(selected)<=60,'Bounded pilot, not automatic expansion'
    with sf.SoundFile(source['localFlac']) as audio:
        for i,contained in enumerate(selected):
            start,end=contained[0]['start'],contained[-1]['end']
            prior=max((r['end'] for r in rows if r['end']<=start),default=0.)
            following=min((r['start'] for r in rows if r['start']>=end),default=info.frames/16000)
            low=max(0,math.ceil(start*16000)-1280,math.ceil((prior+start)*8000))
            high=min(info.frames,math.ceil(end*16000)+1280,math.ceil((end+following)*8000))
            assert 0<high-low<=480000
            assert not [r for r in rows if r not in contained and math.ceil(r['start']*16000)<high and math.ceil(r['end']*16000)>low]
            audio.seek(low);pcm=audio.read(high-low,dtype='int16',always_2d=True)[:,0].astype('<i2',copy=False).tobytes()
            case=source['meeting']+'-context-'+str(i+1).zfill(2)
            wav=E/'audio'/(case+'.wav');wav.parent.mkdir(exist_ok=True)
            assert not wav.exists()
            with wave.open(str(wav),'wb') as out:
                out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
            training.append(dict(id=case,meeting=source['meeting'],audio=str(wav),audioSha256=sha(wav),
                                 audioSeconds=(high-low)/16000,sourceStartFrame=low,sourceEndFrame=high,
                                 sourceWholeSha256=source['expectedWholeFileLfsSha256'],
                                 referenceSha256=source['referenceSha256'],utterances=contained,
                                 text='\n'.join(r['text'] for r in contained),
                                 overlappingReferenceSpeech=False,atLeastTwoAnnotatedSpeakers=True,
                                 shortUtterances=sum(r['end']-r['start']<2 for r in contained)))
    audits.append(dict(meeting=source['meeting'],eligiblePlans=len(plans),selectedPlans=len(selected),
                       seconds=sum(r['audioSeconds'] for r in training if r['meeting']==source['meeting'])))
assert len(training)>=20,'Insufficient context data; do not train a handful of examples'
validation=read(D/'context-matched-baseline-r3/audio-only.json')
assert not {r['meeting'] for r in training}&{r['meeting'] for r in validation}
assert not {r['meeting'] for r in training}&{'20200623_S_R001S07C01','S_R004S03C01','L_R003S01C02','L_R003S03C02','ES2003b','EN2002a'}
write(C/'train.json',training);write(C/'sources.json',sources)
write(C/'validation-audio-only.json',[dict(id=r['id'],meeting=r['meeting'],condition=r['condition'],audio=r['wav'],audioSha256=r['wavSha256'],audioSeconds=r['audioSeconds'],language=r['language']) for r in validation])
old=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/ordinary-asr-adaptation-r1'
for name in ['isolated-peft.json','capability-controls-audio-only.json','mixed-control-scoring-only.json','capability-control-rule.json']:
    shutil.copyfile(old/name,C/name)
write(C/'preparation.json',dict(state='COMPLETE_PUBLIC_NONOVERLAP_MULTITURN_ACOUSTIC_TRAINING_DATA',
       at=datetime.now().astimezone().isoformat(),trainingCases=len(training),sources=audits,
       totalSeconds=sum(r['audioSeconds'] for r in training),newNeuralCalls=0,newTrainingUpdates=0,
       selection='All chronological greedy disjoint maximal4–29.84s windows within singleton overlap-components, >=2speakers, >=1complete<2s utterance, no annotation markup;80ms original padding capped by neighboring midpoint. Not chosen by model error.',
       nativeAudio='Original16k PCM16 first microphone, no gain/denoising/separation/resampling/synthetic mixing.',
       labels='Original official words, fillers, erhua, number forms retained, newline between nonoverlapping utterances. No ambiguous overlap target; not SOT training.',
       validation='Reuse exact32 previously frozen clips plus existing English and natural mixed controls. Never load validation labels in neural worker.',
       oldTrialDifference='Only audio-encoder last8 q/v LoRA; language-model/base weights frozen. Natural multi-turn contexts with short responses, unlike rejected isolated2–12s language-model-only trial.',
       limitations=['Small Chinese acoustic-adaptation pilot, no proof of generalization or source-model pretraining independence.','The two prior train_L sources were used in older ASR/TSE trials; the coverage-audited added train_L source is not an original development/final case. Physical room/speaker independence not proven.','Validation includes genuine overlaps although training does not; this cannot on its own establish overlap or full-meeting quality.'],
       limits=limits.query(),qualityQualified=False,finalHoldoutOpened=False))
print(json.dumps(read(C/'preparation.json'),ensure_ascii=False))
