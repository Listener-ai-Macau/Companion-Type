"""CPU-only remix diagnostic, not isolated-source or word qualification."""
from pathlib import Path
from datetime import datetime
import hashlib,json,wave,sys
import numpy as np
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
T=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/supervised-blind-separation-r1'
C=T/'natural-window-unit-alignment-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load_outputs(control):
    protocol=read(control/'protocol.json');state=read(Path(protocol['separationRun'])/'state.json')
    assert state['state']=='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING'
    return {r['id']:r for r in state['results']}
old=load_outputs(T/'natural-composition-r1');new=load_outputs(C);rows=[]
for case in read(C/'audio-only.json'):
    assert sha(case['wav'])==case['wavSha256']
    with wave.open(case['wav'],'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,16000)
        x=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float64)/32768
    energy=float(x@x);assert energy>0
    values={}
    for label,bank in [('oldWholeClipScale',old),('alignedWindowScale',new)]:
        channels=[]
        for item in bank[case['id']]['streams']:
            assert sha(item['file'])==item['sha256']
            samples=np.load(item['file'],allow_pickle=False).astype(np.float64)
            assert samples.shape==x.shape and np.isfinite(samples).all();channels.append(samples)
        summed=channels[0]+channels[1];summed_energy=float(summed@summed)
        values[label]=dict(remixErrorEnergyRatio=float((summed-x)@(summed-x))/energy,
            remixToInputRmsRatio=float(np.sqrt(summed_energy/energy)),
            remixCosine=float(summed@x)/np.sqrt(summed_energy*energy) if summed_energy else None)
    rows.append(dict(id=case['id'],condition=case['condition'],meeting=case['meeting'],**values))
summary={}
for condition in sorted({r['condition'] for r in rows}):
    selected=[r for r in rows if r['condition']==condition]
    summary[condition]={label:{key:float(np.mean([r[label][key] for r in selected])) for key in selected[0][label]} for label in ['oldWholeClipScale','alignedWindowScale']}
target=C/'waveform-unit-order-diagnostic.json';assert not target.exists()
target.write_text(json.dumps(dict(state='COMPLETE_CPU_ONLY_WHOLE_WAVEFORM_REMIX_DIAGNOSTIC',
    at=datetime.now().astimezone().isoformat(),summary=summary,rows=rows,newNeuralCalls=0,
    qualityQualified=False,referencesUsed=False,wordsOrWaveformsModified=False,
    scope='Only compares sum of two streams with original microphone mixture. This is not SI-SNR against clean targets, speaker identity, or a replacement for the frozen natural-word gate.'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary))
