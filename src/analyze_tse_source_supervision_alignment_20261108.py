"""Distinguish waveform polarity/delay mismatch from wrong-source or weak extraction."""
from pathlib import Path
from collections import Counter
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read,sha,pcm_read
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-tse-source-supervision');limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
import numpy as np
units={x['id']:x for x in read(C/'synthetic-validation-units.json')};rows=[]
def values(file,divisor=1.):return pcm_read(file,1 if file.endswith('.wav') and 'validation-audio' in file else 2)[:,0].astype(np.float64)/32768*divisor
def compare(y,target):
    y=y-y.mean();target=target-target.mean();yy=float(y@y);tt=float(target@target);dot=float(y@target);gain=dot/max(tt,1e-20);projection=gain*target;residual=y-projection;corr=dot/max((yy*tt)**.5,1e-20);sdr=10*np.log10(max(float(projection@projection),1e-20)/max(float(residual@residual),1e-20));size=1<<((2*len(y)-1).bit_length());cross=np.fft.irfft(np.fft.rfft(y,size)*np.conj(np.fft.rfft(target,size)),size);lags=np.arange(-160,161);subset=cross[lags%size];index=int(np.argmax(np.abs(subset)));lag=int(lags[index]);best=float(subset[index])/max((yy*tt)**.5,1e-20)
    return {'signedCorrelation':corr,'targetProjectionGain':gain,'signInvariantSiSdrDb':float(sdr),'bestDelaySamplesWithin10ms':lag,'bestDelaySignedCorrelation':best,'normalL1':float(np.mean(np.abs(y-target))/max(np.mean(np.abs(target)),1e-10)),'invertedL1':float(np.mean(np.abs(y+target))/max(np.mean(np.abs(target)),1e-10))}
for arm in ['baseline','adapted']:
    for row in read(C/(arm+'-validation.json'))['synthetic']:
        if row['metrics'] is None:continue
        unit=units[row['unitId']];index=int(row['id'].rsplit('--',1)[1]);target=unit['targets'][index]['component'];assert sha(row['audio'])==row['audioSha256'] and sha(target['audio'])==target['audioSha256'];y=values(row['audio'],row['pcmExportDivisor']);truth=values(target['audio']);metrics=compare(y,truth);other=None
        if len(unit['targets'])==2:other=compare(y,values(unit['targets'][1-index]['component']['audio']))
        rows.append({'id':row['id'],'condition':arm,'kind':row['kind'],'meeting':row['meeting'],'target':metrics,'otherComponent':other,'leansTowardOtherSourceAtZeroLag':abs(other['signedCorrelation'])>abs(metrics['signedCorrelation']) if other else None})
summary={}
for arm in ['baseline','adapted']:
    summary[arm]={}
    for kind in ['known_additive_mixture','single_target_preservation']:
        group=[r for r in rows if r['condition']==arm and r['kind']==kind];summary[arm][kind]={'examples':len(group),'negativeZeroLagCorrelations':sum(r['target']['signedCorrelation']<0 for r in group),'meanSignedCorrelation':float(np.mean([r['target']['signedCorrelation'] for r in group])),'meanSiSdrDbSignInvariant':float(np.mean([r['target']['signInvariantSiSdrDb'] for r in group])),'meanAbsBestDelaySamples':float(np.mean([abs(r['target']['bestDelaySamplesWithin10ms']) for r in group])),'meanBestDelayAbsoluteCorrelation':float(np.mean([abs(r['target']['bestDelaySignedCorrelation']) for r in group])),'inversionReducesL1Cases':sum(r['target']['invertedL1']<r['target']['normalL1'] for r in group),'otherSourceCorrelationLargerCases':sum(bool(r['leansTowardOtherSourceAtZeroLag']) for r in group)}
result={'state':'POST_REJECTION_POLARITY_DELAY_AND_SOURCE_CONFUSION_DIAGNOSTIC','predeclaredCandidateRejectionUnchanged':True,'maximumDelaySearchedSamples':160,'sampleRate':16000,'summary':summary,'perExample':rows,'newModelCalls':0,'noGainDelayOrPolarityCorrectionApplied':True,'qualityQualified':False};assert not (C/'alignment-diagnostic.json').exists();atomic_json(C/'alignment-diagnostic.json',result);print(json.dumps({'state':result['state'],'summary':summary}),flush=True)
