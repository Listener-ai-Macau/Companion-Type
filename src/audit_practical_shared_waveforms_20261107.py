"""Same-root separated-track waveform similarity; no neural calls or filtering."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import json,wave
import numpy as np
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
B=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery');C=B/'practical-target-activity-r1';read=lambda p:json.loads(Path(p).read_text());limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert not (C/'waveform-cause-review.json').exists();byroot=defaultdict(list)
for r in read(B/'practical-conditioned-ps4-full-r1/asr-manifest-r2.json'):byroot[r['rootIndex']].append(r)
dups=read(C/'merge-and-lane-cause-review.json')['sharedTextPairs'];dupids={frozenset((r['left'],r['right'])):r for r in dups}
def pcm(file):
    with wave.open(file,'rb') as f:return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float64)/32768
rows=[]
for root,lanes in byroot.items():
    audio={r['id']:pcm(r['audio']) for r in lanes}
    for i,left in enumerate(lanes):
        for right in lanes[i+1:]:
            a=audio[left['id']];b=audio[right['id']];assert len(a)==len(b);a=a-a.mean();b=b-b.mean()
            aa=float(np.einsum('i,i->',a,a));bb=float(np.einsum('i,i->',b,b));ab=float(np.einsum('i,i->',a,b));correlation=ab/(aa*bb)**.5 if aa>0 and bb>0 else None
            duplicate=dupids.get(frozenset((left['id'],right['id'])))
            rows.append({'rootIndex':root,'left':left['id'],'right':right['id'],'zeroLagCenteredWaveformCorrelation':correlation,'leftRms':(aa/len(a))**.5,'rightRms':(bb/len(b))**.5,
                'sharedNormalizedCharacters':duplicate['longestSharedNormalizedCharacters'] if duplicate else 0,'sharedRawText':duplicate['sharedRawAsrText'] if duplicate else None})
groups={}
for group,selected in [('longSharedText',[r for r in rows if r['sharedNormalizedCharacters']>=8]),('withoutLongSharedText',[r for r in rows if r['sharedNormalizedCharacters']<8])]:
    values=[r['zeroLagCenteredWaveformCorrelation'] for r in selected if r['zeroLagCenteredWaveformCorrelation'] is not None]
    groups[group]={'pairCount':len(selected),'medianZeroLagCorrelation':float(np.median(values)) if values else None,'minimum':min(values) if values else None,'maximum':max(values) if values else None}
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'SEPARATED_AUDIO_SIMILARITY_DIAGNOSTIC_ONLY','groups':groups,
    'longestSharedTextPairs':[next(r for r in rows if frozenset((r['left'],r['right']))==frozenset((d['left'],d['right']))) for d in dups[:10]],'allPairs':rows,
    'scope':'Zero-lag centered waveform correlation over each unmodified30s pair. Strong similarity plus independently emitted long matching text supports shared acoustic content in those outputs. It is not clean-source SI-SDR, separation quality ground truth, or proof that all excess words came from leakage; low correlation does not rule out leakage/reverberation/ASR additions.',
    'newNeuralCalls':0,'noTextOrAudioChanged':True,'noCorrelationCutoffUsedToFilterAnything':True,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'waveform-cause-review.json',result);print(json.dumps({k:result[k] for k in ['state','groups','longestSharedTextPairs','scope']},ensure_ascii=False),flush=True)
