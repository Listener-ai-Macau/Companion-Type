"""Bounded waveform codec diagnostics and posthoc predicted-gate coverage."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import hashlib,json,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_gss_numpy_backend_20261108 import load_backend
from full_meeting_transcript_metrics_20261103 import normalize
from reference_textgrid_20261104 import read_reference_intervals
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation';B=C.parent/'20261107-model-generation-recovery'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);assert not (C/'codec-and-gate-audit.json').exists()
import numpy as np
_,spectral,_,_,_=load_backend(read(C/'numpy-backend.json'))
def load(file):
    with wave.open(str(file),'rb') as f:return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,f.getnchannels())
def merge(spans):
    result=[]
    for a,b in sorted(spans):
        if b<=a:continue
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(b,result[-1][1]))
        else:result.append((a,b))
    return result
coverage=[];codec=[];review=read(C/'review.json')
for case in read(C/'audio-only.json'):
    raw=load(case['audio']);decoded=load(case['compressedDecodedAudio']);assert raw.shape==decoded.shape
    weighted_phase=weight=0.;phase_bin_count=0
    for lo in range(0,len(raw),80000):
        a=spectral.stft(raw[lo:lo+80000].T.astype(np.float64)/32768,size=1024,shift=256,fading=True)
        b=spectral.stft(decoded[lo:lo+80000].T.astype(np.float64)/32768,size=1024,shift=256,fading=True)
        cross=a[0]*a[1].conj();cross_decoded=b[0]*b[1].conj();power=np.abs(cross)
        freq=np.arange(a.shape[-1])*16000/1024
        valid=(power>max(float(power.max())*1e-4,np.finfo(float).tiny)) & ((freq>=100)&(freq<=7500))[None,:]
        error=np.abs(np.angle(cross_decoded*cross.conj()))
        weighted_phase+=float(np.sum(error[valid]*power[valid]));weight+=float(power[valid].sum());phase_bin_count+=int(valid.sum())
    codec.append({'case':case['id'],'sampleFramesEqual':True,'rawChannelsDistinct':not np.array_equal(raw[:,0],raw[:,1]),
        'decodedChannelsDistinct':not np.array_equal(decoded[:,0],decoded[:,1]),
        'rawChannelCorrelation':float(np.corrcoef(raw.T)[0,1]),'decodedChannelCorrelation':float(np.corrcoef(decoded.T)[0,1]),
        'pcmErrorRmsPerChannel':np.sqrt(np.mean((decoded.astype(np.float64)-raw)**2,axis=0)).tolist(),
        'powerWeightedInterchannelPhaseAbsoluteErrorRadians':weighted_phase/weight if weight else None,'measuredTimeFrequencyBins':phase_bin_count,
        'measurement':'100..7500Hz,5sblocks,native1024Blackman/256STFT; raw cross-power>1e-4blockmaximum. Fixed diagnostic only, no codec-selection or accuracy gate.'})
    lo=case['rootStartSample']/16000;hi=case['rootEndSample']/16000;journal=read(case['journal'])['segments']
    source=next(r for r in read(B/'practical-target-activity-r1/scoring-only.json') if r['meeting']==case['meeting'])
    assert sha(source['reference'])==source['referenceSha256'];truth=read_reference_intervals(source['reference'])
    for row in [r for r in review['perPerson'] if r['case']==case['id']]:
        slot=row['predictedSlot'];predicted=merge([(max(lo,r['start']),min(hi,r['end'])) for r in journal if r['speaker']==slot]) if slot is not None else []
        utterances=[]
        for ref in [r for r in truth if r['speaker']==row['referencePersonForScoringOnly'] and lo<=(r['start']+r['end'])/2<hi and normalize(r['text'])]:
            a=max(lo,ref['start']);b=min(hi,ref['end']);covered=sum(max(0,min(b,d)-max(a,c)) for c,d in predicted)
            utterances.append({'start':ref['start'],'end':ref['end'],'text':ref['text'],'withinClipSeconds':b-a,
                'predictedTargetCoverageSeconds':covered,'predictedTargetCoverageFraction':covered/(b-a) if b>a else None,
                'completelyRemovedByPredictedGate':covered==0,'fullyContainedInClip':ref['start']>=lo and ref['end']<=hi})
        coverage.append({'case':case['id'],'referencePersonForPosthocAudit':row['referencePersonForScoringOnly'],
            'predictedSlot':slot,'predictedActiveSeconds':sum(b-a for a,b in predicted),
            'referenceTargetSeconds':sum(r['withinClipSeconds'] for r in utterances),
            'coveredTargetSeconds':sum(r['predictedTargetCoverageSeconds'] for r in utterances),
            'fullyContainedCompletelyRemovedCharacters':sum(len(normalize(r['text'])) for r in utterances if r['fullyContainedInClip'] and r['completelyRemovedByPredictedGate']),
            'utterances':utterances,'ordinaryBypassDoesNotApplyThisGate':case['kind']=='ordinary-regression'})
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CODEC_SPATIAL_DIFFERENCE_AND_PREDICTED_GATE_COVERAGE_AUDITED',
    'sourceReviewSha256':sha(C/'review.json'),'codecDiagnostics':codec,'predictedGateCoverage':coverage,
    'flacLosslessBitIdentityAlreadyVerified':True,'newModelCalls':0,'generatedTextChanged':False,
    'referenceOnlyUsedForPosthocCoverage':True,'noPerPersonWinnerSelected':True,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'codec-and-gate-audit.json',result)
print(json.dumps({'state':result['state'],'codec':[{'case':r['case'],'phaseErrorRadians':r['powerWeightedInterchannelPhaseAbsoluteErrorRadians']} for r in codec],
    'lostEntireInteriorReferenceWords':[{'case':r['case'],'person':r['referencePersonForPosthocAudit'],'removedChars':r['fullyContainedCompletelyRemovedCharacters'],'coveredSeconds':r['coveredTargetSeconds'],'referenceSeconds':r['referenceTargetSeconds']} for r in coverage if r['fullyContainedCompletelyRemovedCharacters'] and not r['ordinaryBypassDoesNotApplyThisGate']]},ensure_ascii=False),flush=True)
