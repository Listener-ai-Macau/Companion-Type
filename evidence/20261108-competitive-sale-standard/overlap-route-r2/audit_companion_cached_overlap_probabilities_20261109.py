"""Separate cached acoustic misses from journal assembly bugs; no inference/tuning."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os,sys,json,hashlib,re
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109/automatic-cross-meeting-r2';BASE=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from practical_nemotron_worker_20261107 import probability_segments
from reference_textgrid_20261104 import read_reference_intervals
import numpy as np
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
P=read(BASE/'protocol.json');meeting='L_R003S01C02';folder=BASE/'results'/meeting;state=read(folder/'state.json');cache=Path(P['probabilityCacheRoot'])/meeting;manifest=read(cache/'probabilities.json');assert sha(cache/'probabilities.json')==state['probabilityManifestSha256'];assert manifest['protocolSha256']==sha(BASE/'protocol.json') and manifest['audioSha256']==state['audioSha256'];a=np.load(cache/'probabilities.npy',mmap_mode='r',allow_pickle=False);n=manifest['committedFrames'];assert n==state['completedNeuralFrames'] and hashlib.sha256(memoryview(a[:n]).cast('B')).hexdigest()==manifest['committedPrefixSha256']
cadence=state['nativeSecondsPerFrame'];rebuilt=probability_segments(a,n,cadence,state['audioSeconds'],.5);journal=read(folder/'speaker-journal.json');assert rebuilt==journal['segments'],'Cached acoustic output andjournal assembly diverge; investigate before model conclusion'
case=next(x for x in read(BASE/'scoring-only.json') if x['meeting']==meeting);assert sha(case['reference'])==case['referenceSha256'];ref=[r for r in read_reference_intervals(case['reference']) if re.sub(r'<[^>]*>','',r['text']).strip()];review=read(folder/'review.json');mapping={key:int(value['matchedAnonymousGroup'].removeprefix('speaker_')) for key,value in review['perReferenceSpeakerForEvaluationOnly'].items()};truth=np.zeros((n,8),dtype=bool)
centres=(np.arange(n)+.5)*cadence
for row in ref:
 start=int(np.searchsorted(centres,row['start'],side='left'));end=int(np.searchsorted(centres,row['end'],side='left'));truth[start:end,mapping[row['speaker']]]=True
native=np.zeros((n,8),dtype=bool)
for speaker in range(8):
 value=a[:n,speaker];last=np.maximum.accumulate(np.where(value!=.5,np.arange(n),-1));native[:,speaker]=(last>=0)&(value[np.maximum(last,0)]>.5)
overlap=truth.sum(1)>=2;miss=overlap&(native.sum(1)<2);missing_voice=truth&~native;values=a[:n][missing_voice&miss[:,None]];q={str(p):float(np.quantile(values,p)) for p in (0,.1,.25,.5,.75,.9,1)}
result={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'CACHED_ACOUSTIC_OUTPUT_REPRODUCES_JOURNAL_EXACTLY','meeting':meeting,'audioSha256':manifest['audioSha256'],'probabilityManifestSha256':sha(cache/'probabilities.json'),'committedProbabilityPrefixSha256':manifest['committedPrefixSha256'],'committedFrames':n,'journalSegmentsReproducedExactly':len(rebuilt),'runtimeDecoderSourceSha256':sha(M/'src/practical_nemotron_worker_20261107.py'),'thresholdUnchanged':.5,'frameCentresPolicy':'Use cachednative10ms cadence atframecentre for reference diagnostics; continuous-time exact interval metrics kept separately. Fixedfullnative mapping evaluation-only.','trueOverlapFrameSeconds':int(overlap.sum())*cadence,'missedOverlapFrameSeconds':int(miss.sum())*cadence,'missedOverlapFractionOfFrames':float(miss.sum()/overlap.sum()),'missingTrueVoicePosterior':{'voiceFrames':len(values),'quantiles':q,'fractionBelow0_1':float(np.mean(values<.1)),'fractionAtOrAbove0_4':float(np.mean(values>=.4)),'interpretation':'Diagnostic distribution only; no cutoff selection, threshold trial or newlabel result. Missing true voice scores are read after inference with reference mapping, never supplied to runtime.'},'conclusion':'Existingcached probabilities reconstruct all656journal segments exactly. The missedsecond-voice activity is present before source routing/separation; this batch found no journal assembly bug. Replacing groupnames or accepting two-model identity agreement cannot restore unpredicted voices. No claim nativeframework numeric equivalence or fundamentalmodel ceiling.','newModelInference':False,'newWeightsOrThresholds':False,'productChanged':False,'saleQualified':False,'limits':limits.query()};(C/'cached-overlap-probability-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
