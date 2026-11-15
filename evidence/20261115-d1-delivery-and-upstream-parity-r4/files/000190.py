"""Post-decision diagnostic: quantify silence shortcuts without another model call."""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,os,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-tse-supervised-adaptation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
import numpy as np
P=read(C/'training-protocol-r4.json');review=read(C/'training-review.json');assert review['state']=='FIXED_TRAINING_PASS_REJECTED_VALIDATION_REGRESSION'
before={r['id']:r for r in read(C/'baseline-validation.json')['examples']};after={r['id']:r for r in read(C/'adapted-validation.json')['examples']};examples={r['id']:r for r in read(P['dataManifest'])};rows=[]
def pcm(file,channels):
    with wave.open(file,'rb') as f:assert f.getnchannels()==channels and f.getsampwidth()==2 and f.getframerate()==16000;return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float64).reshape(-1,channels)/32768
for identity in P['validationOrder']:
    x=examples[identity];a,b=before[identity],after[identity];assert sha(x['audio'])==x['audioSha256'];source=pcm(x['audio'],2)[:,0];mask=np.zeros(len(source),dtype=bool);start=x['sourceStartSample']/16000
    for interval in x['targetUtterancesForTrainingOnly']:mask[max(0,math.floor((interval['start']-start)*16000)):min(len(mask),math.ceil((interval['end']-start)*16000))]=True
    zero_loss=float(np.mean(np.abs(source)*mask)/max(float(np.mean(np.abs(source))),1e-4*float(np.max(np.abs(source))))) if x['category']=='present_solo' else 0.
    active={}
    if mask.any():
        for arm,value in [('baseline',a),('adapted',b)]:
            assert sha(value['audio'])==value['audioSha256'];output=pcm(value['audio'],1)[:,0]*value['pcmExportDivisor'];assert len(output)==len(source);active[arm]=float(np.sqrt(np.mean(output[mask]**2))/max(float(np.sqrt(np.mean(source[mask]**2))),1e-12))
    rows.append({'id':identity,'category':x['category'],'zeroOutputWaveformLoss':zero_loss,'baselineWaveformLoss':a['waveformLoss'],'adaptedWaveformLoss':b['waveformLoss'],'baselineOutputRmsRatio':a['outputToInputRmsRatio'],'adaptedOutputRmsRatio':b['outputToInputRmsRatio'],'targetActiveOutputToOriginalMixtureRms':active,'teacherCeBefore':a['presentTargetTeacherCe'],'teacherCeAfter':b['presentTargetTeacherCe']})
groups={}
for category in ['present_solo','present_overlap','absent_other_speech']:
    subset=[r for r in rows if r['category']==category];mean=lambda key:sum(r[key] for r in subset)/len(subset);a,b=mean('baselineOutputRmsRatio'),mean('adaptedOutputRmsRatio');groups[category]={'examples':len(subset),'meanZeroOutputWaveformLoss':mean('zeroOutputWaveformLoss'),'meanBaselineWaveformLoss':mean('baselineWaveformLoss'),'meanAdaptedWaveformLoss':mean('adaptedWaveformLoss'),'meanOutputRmsAfterDividedByBefore':b/a,'meanOutputAmplitudeReductionFraction':1-b/a,'targetActiveMeanOutputToOriginalMixtureRms':{arm:sum(r['targetActiveOutputToOriginalMixtureRms'][arm] for r in subset)/len(subset) for arm in ['baseline','adapted']} if category!='absent_other_speech' else None}
result={'at':datetime.now().astimezone().isoformat(),'state':'POST_REJECTION_OBJECTIVE_SILENCE_SHORTCUT_DIAGNOSTIC','trainingReviewSha256':sha(C/'training-review.json'),'originalRejectionMadeBeforeThisDiagnostic':True,'categories':groups,'perExample':rows,'measuredFact':'After/before mean output RMS is strongly reduced in present-solo, present-overlap and absent cases. No word accuracy inferred from loss or amplitude.','mathematicalFact':'The configured waveform term is exactly zero for an all-zero output on every absent and overlap example. On overlap it supervises only inactive intervals; positive target preservation relies solely on recognizer CE. Zero-output solo waveform loss is explicitly measured as a control.','interpretation':'Observed broad attenuation is consistent with a silence shortcut in the combined supervision. This does not prove the pretrained backbone cannot extract speakers, nor that ASR guidance is always invalid. Do not repair by a validation-tuned output gain or threshold.','nextMethod':'Use known target audio components from controlled mixtures of separate real nonoverlapping TRAIN utterances (clearly distinguish synthesized mixtures from natural overlap), add target-present waveform/source consistency supervision with negative-target cases, and freeze a new source-meeting validation split before the next trial. Do not tune learning rate or select a step on these48 examples. Preserve the untouched final holdout.','newModelCalls':0,'newWeightUpdates':0,'referencesUsedForDiagnosticOnly':True,'qualityQualified':False}
assert not (C/'objective-diagnostic.json').exists();atomic_json(C/'objective-diagnostic.json',result);print(json.dumps({'state':result['state'],'categories':groups,'nextMethod':result['nextMethod']},ensure_ascii=False),flush=True)
