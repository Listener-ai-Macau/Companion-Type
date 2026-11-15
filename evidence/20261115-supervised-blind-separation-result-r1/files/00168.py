"""Closed two-source supervision, independent of target-person identities."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,math,shutil,sys,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
import numpy as np
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'supervised-blind-separation-r1';C.mkdir(exist_ok=True)
K=Path('E:/CodexData/Companion/.model-cache/supervised-blind-separation-20261115');K.mkdir(exist_ok=True)
OLD=R/'docs/handoffs/20261108-tse-source-supervision'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'data-ready.json').exists()
verified={};summaries={};all_meetings={};all_hashes={}
def pcm(row):
    p=Path(row['audio']);digest=row['audioSha256']
    if str(p) not in verified:assert sha(p)==digest;verified[str(p)]=digest
    with wave.open(str(p),'rb') as f:
        assert (f.getframerate(),f.getsampwidth(),f.getnchannels())==(16000,2,2)
        n=f.getnframes();raw=f.readframes(n)
    assert n/16000==row['audioSeconds']
    return np.frombuffer(raw,dtype='<i2').reshape(-1,2)[:,0].astype(np.int32)
for role,name in [('train','training-units.json'),('validation','synthetic-validation-units.json')]:
    original=read(OLD/name);seen=set();units=[];examples=[];excluded=Counter()
    folder=K/role;folder.mkdir(exist_ok=True)
    for row in original:
        if row['kind']=='absent_known_identity':excluded['old-person-conditioned-absence-not-source-silence']+=1;continue
        key=row['mixture']['audioSha256']
        if key in seen:excluded['duplicate-mixture']+=1;continue
        seen.add(key);mixture=pcm(row['mixture'])
        assert 1<=len(row['targets'])<=2
        sources=[pcm(t['component']) for t in row['targets']]
        if len(sources)==1:sources.append(np.zeros_like(mixture))
        targets=np.stack(sources);assert targets.shape==(2,len(mixture))
        assert np.array_equal(targets.sum(0),mixture),'All source components must exactly explain the mixture'
        unit=dict(id=row['id'],role=role,meeting=row['meeting'],kind='two-source' if len(row['targets'])==2 else 'single-source',
                  mixtureSha256=key,sourceFrames=len(mixture),originalUnitManifest=str(OLD/name),
                  originalSources=[dict(file=t['component']['audio'],sha256=t['component']['audioSha256']) for t in row['targets']],
                  completeKnownAdditiveSum=True,notNaturalOverlap=True,physicalChannel=0)
        # Fixed2s windows cover every source sample; the final endpoint may
        # overlap the previous window. No transcript/error/identity selection.
        starts=list(range(0,max(0,len(mixture)-32000)+1,32000))
        if starts[-1]+32000<len(mixture):starts.append(len(mixture)-32000)
        for index,start in enumerate(starts):
            count=min(32000,len(mixture)-start);x=np.zeros(32000,dtype=np.float32);y=np.zeros((2,32000),dtype=np.float32)
            x[:count]=mixture[start:start+count]/32768;y[:,:count]=targets[:,start:start+count]/32768
            assert np.array_equal(x,y.sum(0)) and float(np.square(y,dtype=np.float64).sum())>0
            example=row['id']+'-window-'+str(index).zfill(2);path=folder/(example+'.npy');assert not path.exists()
            # Input and its two exact target sources share one small array.
            np.save(path,np.vstack([x,y]),allow_pickle=False)
            examples.append(dict(id=example,unit=row['id'],role=role,meeting=row['meeting'],kind=unit['kind'],
                                 file=str(path),sha256=sha(path),sourceStartFrame=start,validFrames=count,
                                 frames=32000,sourceTargetsIncludeExactInactiveZero=unit['kind']=='single-source'))
        units.append(unit)
    write(C/(role+'-units.json'),units)
    write(C/(role+'-examples.json'),examples)
    write(C/(role+'-audio-only.json'),[{k:v for k,v in row.items() if k not in ['kind','sourceTargetsIncludeExactInactiveZero']} for row in examples])
    summaries[role]=dict(originalConditionalUnits=len(original),uniqueSourceUnits=len(units),examples=len(examples),
                         counts=dict(Counter(r['kind'] for r in units)),excluded=dict(excluded),
                         fullUnitSeconds=sum(r['sourceFrames'] for r in units)/16000,
                         twoSecondTrainingExposureSeconds=len(examples)*2,
                         overlappingTailExamplesExplicit=True)
    all_meetings[role]={r['meeting'] for r in units};all_hashes[role]=seen
assert not all_meetings['train']&all_meetings['validation'] and not all_hashes['train']&all_hashes['validation']
assert not all_meetings['train']&{'20200623_S_R001S07C01','S_R004S03C01','L_R003S01C02','L_R003S03C02'}
result=dict(state='COMPLETE_CLOSED_SINGLE_AND_TWO_SOURCE_BLIND_SEPARATION_SUPERVISION',
            at=datetime.now().astimezone().isoformat(),summaries=summaries,
            meetings={k:sorted(v) for k,v in all_meetings.items()},sourceHashChecks=len(verified),
            allMixturesExactlyEqualBothTargetsSum=True,sourceAndValidationDisjointByMeeting=True,
            personProfilesOrIdentityLabelsUsed=False,
            inputAudioOnlyManifestNote='Inference loader reads only array[0];array[1:3] are independent supervised source waveforms, never supplied to forward. Synthetic scorer reads them after prediction.',
            publicSource='AISHELL4 official raw observed nonoverlap excerpts, first microphone. They contain real room background; these are exact artificial additive mixtures, not clean isolated speakers from natural overlapping meetings.',
            labelCorrection='Exclude all old target-person-absent queries; do not turn unknown real voices into zeros. Single-source targets are the actual complete raw input plus a truly absent source zero.',
            zeroInput='Exact whole digital silence bypasses the already-verified separator with zero outputs; not an undefined all-zero SA-SDR training target.',
            limitations=['Small public training subset, no claim of physical speaker/room or pretrained-model independence.','Validation sources were already used for earlier diagnostics; fixed original complex-word clips remain development, not final qualification.','Overlapping final2s windows increase exposure without increasing unique audio.'],
            newNeuralCalls=0,newTrainingUpdates=0,ownerParticipationRequired=False,finalHoldoutOpened=False,
            qualityQualified=False,limits=limits.query())
write(C/'data-ready.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ['limits','limitations']},ensure_ascii=False))
