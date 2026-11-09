"""Evaluate fixed independent-overlap union on both full cached meetings."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter,defaultdict
import hashlib,json,sys,re,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109/automatic-cross-meeting-r2';O=C/'independent-overlap-candidate-r1';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from reference_textgrid_20261104 import read_reference_intervals
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources=read(R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/scoring-only.json');runs=[]
for source in ([] if '--third' in sys.argv else sources):
 prediction=read(O/(source['meeting']+'-prediction.json'));assert prediction['sourceSha256']==source['audioSha256'];assert sha(source['reference'])==source['referenceSha256'];journal=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results'/source['meeting']/'speaker-journal.json';assert sha(journal)==prediction['journalSha256'];reference=[r for r in read_reference_intervals(source['reference']) if re.sub(r'<[^>]*>','',r['text']).strip()];events=defaultdict(lambda:defaultdict(Counter));events[0];events[source['audioSeconds']]
 for side,rows in [('reference',reference),('native',read(journal)['segments']),('independent',[{**r,'speaker':'independent_positive'} for r in prediction['regions']])]:
  for row in rows:events[row['start']][side][str(row['speaker'])]+=1;events[row['end']][side][str(row['speaker'])]-=1
 active={s:Counter() for s in ['reference','native','independent']};totals={k:Counter() for k in ['native','independent','union']};changed=Counter();newlycaught=[];edges=sorted(events);true=0
 for a,b in zip(edges,edges[1:]):
  for side in active:active[side].update(events[a].get(side,{}))
  nr=sum(v>0 for v in active['reference'].values());native=sum(v>0 for v in active['native'].values())>=2;independent=sum(v>0 for v in active['independent'].values())>0;truth=nr>=2;seconds=b-a
  if truth:true+=seconds
  for key,positive in [('native',native),('independent',independent),('union',native or independent)]:
   if truth:totals[key]['caughtSeconds' if positive else 'missedSeconds']+=seconds
   elif positive:totals[key]['falsePositiveSeconds']+=seconds
   if positive:totals[key]['predictedPositiveSeconds']+=seconds
  if independent and not native:
   changed['newlyCaughtTrueOverlapSeconds' if truth else 'newFalsePositiveSeconds']+=seconds
   if truth:
    if newlycaught and newlycaught[-1]['end']==a:newlycaught[-1]['end']=b
    else:newlycaught.append({'start':a,'end':b})
 metrics={}
 for key,c in totals.items():metrics[key]={**dict(c),'recall':c['caughtSeconds']/true if true else None,'precision':c['caughtSeconds']/c['predictedPositiveSeconds'] if c['predictedPositiveSeconds'] else None}
 base=read(C/source['meeting']/'full-overlap-routing-review.json');assert abs(base['trueOverlapSeconds']-true)<1e-6 and abs(base['predictedOverlapSeconds']-totals['native']['predictedPositiveSeconds'])<1e-6
 result={'meeting':source['meeting'],'sourceSha256':source['audioSha256'],'referenceSha256':source['referenceSha256'],'audioSeconds':source['audioSeconds'],'trueOverlapSeconds':true,'metrics':metrics,'changedRegions':dict(changed),'newlyCaughtTrueOverlapRegionsForScoringOnly':newlycaught,'sourceFramesPreservedExactlyOnce':prediction['sourceFramesPreservedExactlyOnce'],'routeTimes':prediction['secondsByRoute'],'additionalUnknownTargetIdentityIsNotGuessed':True,'newNeuralCalls':0,'wordRecoveryProven':False,'saleQualified':False};write(O/(source['meeting']+'-review.json'),result);runs.append(result)
if '--third' not in sys.argv:
 output={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'INDEPENDENT_OVERLAP_UNION_EVALUATED_NO_CONTENT_PROMOTION','cases':runs,'fixedPolicy':'Keep frozenlocalpowerset argmax andauthorroundedmean; unionpositive withnative8 predictedoverlap. No threshold/model/hotword/reference-person-count tuning. No positiveacceptance from seeinganswers.','decision':'Retain as research routing candidate only if the observed recall/false-positive tradeoff justifies followup. Source/content protection still not met and unknown second-person identity remains unresolved; do not replace rawASR, claim recoveredwords, integrate productdefault, or call salequalified. Ordinary ASRbaseline and all original gates remain unchanged.','sourceModelInferenceCostNotMeasuredThisBatch':'Cached neuraloutputs were reused, so subsecond reconstruction is not fresh detector inference latency. Existing complete modelrun costs remain separately recorded.','limits':limits.query(),'newWeightsTrainingDownloadsOrApiCalls':False,'saleQualified':False};write(O/'result.json',output);print(json.dumps([{k:r[k] for k in ['meeting','trueOverlapSeconds','metrics','changedRegions','sourceFramesPreservedExactlyOnce']} for r in runs],ensure_ascii=False))
else:
 import numpy as np
 import wave
 from companion_local_overlap_regions_20261109 import local_overlap_regions
 from companion_meeting_route_plan_20261109 import plan_routes
 T=O/'third-meeting-r1';run=read(T/'run.json');assert run['state']=='COMPLETE_FRESH_THIRD_MEETING_SEGMENTATION';source=read(C.parent/'ordinary-full-r1/full/scoring-only.json')[0];P=read(T/'protocol.json');cache=Path(P['boundedCacheRoot'])/source['meeting'];manifest=read(cache/'segment.json');a=np.load(cache/'segment.npy',mmap_mode='r',allow_pickle=False);assert manifest['done']==manifest['total']==len(a) and manifest['state']=='COMPLETE_SEGMENTATION_CACHE';assert manifest['binding']['audioSha256']==source['audioSha256'] and manifest['binding']['segmentationSha256']==P['segmentation']['sha256'];assert hashlib.sha256(memoryview(np.asarray(a)).cast('B')).hexdigest()==manifest['committedPrefixSha256']
 with wave.open(source['audio'],'rb') as f:frames=f.getnframes()
 regions,metadata=local_overlap_regions(a,manifest['meta'],source_frames=frames);routes=plan_routes([],source_frames=frames,sample_rate=16000,overlap_regions=regions)
 write(T/'prediction.json',{'meeting':source['meeting'],'sourceSha256':source['audioSha256'],'segmentationManifestSha256':sha(cache/'segment.json'),'committedSegmentationSha256':manifest['committedPrefixSha256'],'regions':regions,'metadata':metadata,'routes':routes,'sourceFramesPreservedExactlyOnce':sum(r['endSample']-r['startSample'] for r in routes)==frames,'freshNativeJournalOrAsrNotRun':True,'globalIdentityInvented':False,'productDefaultChanged':False})
 # Reference evaluation starts only after fresh inference has exited.
 assert sha(source['reference'])==source['referenceSha256'];reference=[r for r in read_reference_intervals(source['reference']) if re.sub(r'<[^>]*>','',r['text']).strip()];events=defaultdict(lambda:defaultdict(Counter));events[0];events[source['audioSeconds']]
 for side,rows in [('reference',reference),('independent',[{**r,'speaker':'overlap'} for r in regions])]:
  for row in rows:events[row['start']][side][str(row['speaker'])]+=1;events[row['end']][side][str(row['speaker'])]-=1
 active={s:Counter() for s in ['reference','independent']};total=Counter();edges=sorted(events)
 for begin,end in zip(edges,edges[1:]):
  for side in active:active[side].update(events[begin].get(side,{}))
  nr=sum(v>0 for v in active['reference'].values());positive=sum(v>0 for v in active['independent'].values())>0;seconds=end-begin
  if nr>=2:total['trueOverlapSeconds']+=seconds;total['caughtSeconds' if positive else 'missedSeconds']+=seconds
  elif positive:total['falsePositiveSeconds']+=seconds
  if positive:total['predictedPositiveSeconds']+=seconds
 result={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'COMPLETE_FRESH_THIRD_MEETING_LOCAL_OVERLAP_NOT_QUALIFIED','meeting':source['meeting'],'audioSeconds':source['audioSeconds'],'sourceSha256':source['audioSha256'],'referenceSha256':source['referenceSha256'],'metrics':{**dict(total),'recall':total['caughtSeconds']/total['trueOverlapSeconds'],'precision':total['caughtSeconds']/total['predictedPositiveSeconds'] if total['predictedPositiveSeconds'] else None},'sourceFramesPreservedExactlyOnce':True,'sourcePreviouslyUsedForTseValidation':True,'firstFreshDiarizationSegmentationOnThisWholeMeeting':True,'fullNativeJournalOrUnionNotMeasuredOnThirdMeeting':True,'finalHeldoutOpened':False,'referencePassedToInference':False,'inferenceRun':run,'noNewAsrOrWordCerClaim':True,'thresholdsOrWeightsChanged':False,'saleQualified':False};write(T/'review.json',result);print(json.dumps(result,ensure_ascii=False))
