"""Independent unchanged-PCM timing inspection; never align or infer words."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import sys
import wave

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'model-research/src'; sys.path.insert(0,str(S))
import numpy as np
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure
from practical_io_20261107 import atomic_json
from meeting_acoustic_contract_20261116 import read, require, sha

J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/microphone-diagnostic-r1'
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
pressure=SystemRamPressure(); pairing=read(J/'pairing.json')
require(not (J/'timebase-review.json').exists(),'Preserve completed timing inspection')
# Declare the independent check before seeing its result. A correlation
# amplitude across two acoustic transfer functions is not a clock criterion.
criteria={'searchLagSamples':8000,'maximumAbsolutePeakLagSamples':1600,
          'allPairsMustPass':True,'amplitudeThresholdUsed':False,
          'waveformOrReferenceShiftAllowed':False}

def pcm(item):
    require(sha(item['audio'])==item['audioSha256'],'Prepared waveform changed')
    with wave.open(item['audio'],'rb') as stream:
        return np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float64)

rows=[]
try:
    for pair in pairing['pairs']:
        require(not pressure.low(),'Windows low RAM')
        x,y=pcm(pair['distant']),pcm(pair['headsetMix'])
        require(len(x)==len(y)==pair['frames'],'Timing input frame mismatch')
        x-=x.mean(); y-=y.mean()
        nfft=1 << (2*len(x)-1).bit_length()
        spectrum=np.fft.rfft(x,nfft)*np.conj(np.fft.rfft(y,nfft))
        corr=np.fft.irfft(spectrum,nfft)
        search=np.concatenate((corr[-8000:],corr[:8001]))
        index=int(np.argmax(np.abs(search))); lag=index-8000
        coefficient=float(search[index]/np.sqrt(np.dot(x,x)*np.dot(y,y)))
        rows.append({'id':pair['id'],'waveformPeakLagSamples':lag,
                     'waveformPeakLagMs':lag/16,'signedNormalizedPeak':coefficient,
                     'envelopePeakLagMs':pair['timebaseInspection']['bestEnvelopeLagMs'],
                     'withinOriginal100MsTimingBound':abs(lag)<=1600,
                     'audioOrReferenceShiftApplied':False})
        del x,y,spectrum,corr,search
    passed=all(r['withinOriginal100MsTimingBound'] for r in rows)
    report={'state':'INDEPENDENT_MICROPHONE_TIMEBASE_INSPECTION_'+('PASS' if passed else 'UNRESOLVED'),
            'at':datetime.now().astimezone().isoformat(timespec='seconds'),
            'criteria':criteria,'rows':rows,'allPairsPass':passed,
            'originalEnvelopeAmplitudeGuard':{'minimumRequired':.5,
                'observedMinimum':pairing['inspection']['minimumEnvelopeCorrelation'],
                'passed':False,'failurePreserved':True,
                'assessment':'The initial preparation guard conflated cross-microphone amplitude agreement with sample-clock agreement. It failed before any inference. Do not lower it or select/drop/shift clips to pass. Inspect full unchanged-PCM correlation lags independently and official acquisition documentation.'},
            'officialDocumentation':[
                {'url':'https://groups.inf.ed.ac.uk/ami/corpus/meetingrooms.shtml',
                 'supports':'Synchronization section: all audio ADCs share a 48kHz word clock; channels sampled at precisely the same instant.'},
                {'url':'https://groups.inf.ed.ac.uk/ami/corpus/dataproblems.shtml',
                 'supports':'ES2003b has no listed audio discontinuity; EN2001a dropout was zero-padded on the common timeline. This is not a claim that the corpus is error-free.'}],
            'interpretation':'No waveform alignment has been applied. Passing only checks for gross view/timebase mismatch within the original100ms bound. It does not prove sample-perfect acoustic arrival alignment or equal intelligibility.',
            'pairingSha256':sha(J/'pairing.json'),'sourceSha256':sha(__file__),
            'newNeuralCalls':0,'trainingUpdates':0,'qualityQualified':False,'limits':limits.query()}
    atomic_json(J/'timebase-review.json',report)
    print(json.dumps({'state':report['state'],'maxAbsoluteWaveformPeakLagMs':max(abs(r['waveformPeakLagMs']) for r in rows),
                      'allPairsPass':passed,'pairs':len(rows),'newNeuralCalls':0},ensure_ascii=False))
finally:
    pressure.close()
