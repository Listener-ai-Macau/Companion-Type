from pathlib import Path
from datetime import datetime
import json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
import numpy as np
from blind_separation_composition_20261115 import read_audio
from companion_community1_adapter_20261115 import sha
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/blind-separation-composition-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
target=C/'derived-waveform-diagnostic.json';assert not target.exists()
protocol=read(C/'protocol.json');state=read(Path(protocol['separationRun'])/'state.json')
assert state['state']=='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING'
rows=[]
for case in read(C/'audio-only.json'):
    item=next(r for r in state['results'] if r['id']==case['id']);original=read_audio(case,np)
    streams=[]
    for channel in item['streams']:
        assert sha(channel['file'])==channel['sha256'];value=np.load(channel['file'],allow_pickle=False)
        assert value.shape==original.shape and value.dtype==np.float32 and np.isfinite(value).all();streams.append(value)
    rms=lambda x:float(np.sqrt(np.mean(x.astype(np.float64)**2)))
    base=rms(original);assert base>0
    ratios=[rms(s)/base for s in streams]
    rows.append(dict(id=case['id'],condition=case['condition'],frames=len(original),inputRms=base,
                     outputRmsRatios=ratios,sumResidualRmsRatio=rms(original-streams[0]-streams[1])/base,
                     originalAmplitudeInput=True,noPerStreamOutputGain=True,
                     noSamplesClipped=True,samplesOutsideUnitRange=sum(int((np.abs(s)>1).sum()) for s in streams),
                     anonymousChannelSwaps=sum(t['swapped'] for t in item['stitching'])))
groups={}
for condition in sorted({r['condition'] for r in rows}):
    items=[r for r in rows if r['condition']==condition]
    groups[condition]=dict(cases=len(items),medianLouderStreamRmsRatio=float(np.median([max(r['outputRmsRatios']) for r in items])),
                          medianQuieterStreamRmsRatio=float(np.median([min(r['outputRmsRatios']) for r in items])),
                          medianSumResidualRatio=float(np.median([r['sumResidualRmsRatio'] for r in items])),
                          samplesOutsideUnitRange=sum(r['samplesOutsideUnitRange'] for r in items))
result=dict(state='COMPLETE_EXISTING_FLOAT_OUTPUT_PRESERVATION_DIAGNOSTIC',at=datetime.now().astimezone().isoformat(),
            groups=groups,cases=rows,newNeuralCalls=0,newTrainingUpdates=0,qualityQualified=False,
            interpretation='Natural single-mic recordings have no exact isolated source waveforms. Energy/sum residual is not SI-SNRi, acoustic separation quality or word recovery. No gains, outputs, decoding or frozen keep rules changed after observing this diagnostic.',limits=limits.query())
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':result['state'],'groups':groups},ensure_ascii=False))
