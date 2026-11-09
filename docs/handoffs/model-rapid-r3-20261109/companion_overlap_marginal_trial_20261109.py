"""One frozen posterior-marginal trial across all three prepared full meetings."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter,defaultdict
import argparse,hashlib,json,os,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';PARENT=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109';PREV=PARENT/'automatic-cross-meeting-r2/independent-overlap-candidate-r1';C=R/'docs/handoffs/20261109-overlap-marginal-r1';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);pressure=SystemRamPressure()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('phase',choices=['infer','score']);a=p.parse_args()
if a.phase=='infer':
 import numpy as np
 from companion_local_overlap_regions_20261109 import posterior_overlap_regions
 C.mkdir(exist_ok=False)
 old=read(R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/audio-only.json');new=read(PARENT/'ordinary-full-r1/audio-only.json');cases=old+new
 write(C/'protocol.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'workerSha256':sha(__file__),'sourceSha256':sha(M/'src/companion_local_overlap_regions_20261109.py'),'policy':'Exactly one fixed alternative: normalizedpowerset7logprobabilities→sumexp mutuallyexclusivepairclasses4..6→uniform crosswindowmean→0.5binarycutoff. Sameframegeometry andsourceframes. No threshold/temperature/min-duration/padding sweep or permeeting choice. Compare both standalone and existingnativeunion on allavailable3meetings. Allresults/failures retained.','whyDifferent':'Existing method uses hard7classargmax then roundedlocalcount, discarding split probability mass. New method marginalizes the desired binary event beforedecision. This is a hypothesis about decision information loss, not a proven modelbug or officialrecommendedpipeline.','primaryReferences':['https://raw.githubusercontent.com/pyannote/pyannote-audio/main/src/pyannote/audio/utils/powerset.py','https://www.isca-archive.org/interspeech_2023/plaquet23_interspeech.pdf','https://arxiv.org/abs/2409.15885'],'referenceLabelsOrTextsReadByInference':False,'newModelInferenceOrWeights':False,'finalHeldoutOpened':False,'saleQualified':False})
 write(C/'audio-only.json',cases)
 for case in cases:
  if pressure.low():raise RuntimeError('ActualWindowsLOWRAM;stopthisworker')
  base=(Path('E:/CodexData/Companion/.model-cache/bounded-speaker-20261107-full-r1') if case['meeting']!='20200805_S_R001S01C01' else Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/third-meeting-overlap-r1'))/case['meeting'];manifest=read(base/'segment.json');assert manifest['done']==manifest['total'] and manifest['binding']['audioSha256']==case['audioSha256'];values=np.load(base/'segment.npy',mmap_mode='r',allow_pickle=False);assert hashlib.sha256(memoryview(np.asarray(values)).cast('B')).hexdigest()==manifest['committedPrefixSha256'];frames=round(case['audioSeconds']*16000);regions,metadata,probability=posterior_overlap_regions(values,manifest['meta'],source_frames=frames);np.savez_compressed(C/(case['meeting']+'-posterior.npz'),overlap=probability);write(C/(case['meeting']+'-prediction.json'),{'meeting':case['meeting'],'sourceSha256':case['audioSha256'],'sourceFrames':frames,'regions':regions,'metadata':metadata,'segmentManifestSha256':sha(base/'segment.json'),'posteriorArraySha256':hashlib.sha256(probability.tobytes()).hexdigest(),'referenceRead':False});print(json.dumps({'meeting':case['meeting'],'regions':len(regions)},ensure_ascii=False),flush=True)
else:
 import re
 from reference_textgrid_20261104 import read_reference_intervals
 sources=read(R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/scoring-only.json')+read(PARENT/'ordinary-full-r1/full/scoring-only.json');reviews=[]
 for source in sources:
  prediction=read(C/(source['meeting']+'-prediction.json'));assert prediction['sourceSha256']==source['audioSha256'] and sha(source['reference'])==source['referenceSha256'];reference=[r for r in read_reference_intervals(source['reference']) if re.sub(r'<[^>]*>','',r['text']).strip()];third=source['meeting']=='20200805_S_R001S01C01';old=read(PREV/'third-meeting-r1/prediction.json') if third else read(PREV/(source['meeting']+'-prediction.json'));native=[] if third else read(R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results'/source['meeting']/'speaker-journal.json')['segments'];events=defaultdict(lambda:defaultdict(Counter));events[0];events[source['audioSeconds']]
  for side,rows in [('reference',reference),('native',native),('hard',[{**r,'speaker':'flag'} for r in old['regions']]),('soft',[{**r,'speaker':'flag'} for r in prediction['regions']])]:
   for row in rows:events[row['start']][side][str(row['speaker'])]+=1;events[row['end']][side][str(row['speaker'])]-=1
  active={s:Counter() for s in ['reference','native','hard','soft']};totals={s:Counter() for s in ['hard','soft']+([] if third else ['native','hard_union','soft_union'])};edges=sorted(events);truth_seconds=0
  for begin,end in zip(edges,edges[1:]):
   for side in active:active[side].update(events[begin].get(side,{}))
   truth=sum(v>0 for v in active['reference'].values())>=2;native_flag=sum(v>0 for v in active['native'].values())>=2;hard=sum(v>0 for v in active['hard'].values())>0;soft=sum(v>0 for v in active['soft'].values())>0;seconds=end-begin
   if truth:truth_seconds+=seconds
   flags={'hard':hard,'soft':soft}
   if not third:flags.update(native=native_flag,hard_union=hard or native_flag,soft_union=soft or native_flag)
   for key,positive in flags.items():
    if truth:totals[key]['caughtSeconds' if positive else 'missedSeconds']+=seconds
    elif positive:totals[key]['falsePositiveSeconds']+=seconds
    if positive:totals[key]['predictedSeconds']+=seconds
  metrics={k:{**dict(v),'recall':v['caughtSeconds']/truth_seconds if truth_seconds else None,'precision':v['caughtSeconds']/v['predictedSeconds'] if v['predictedSeconds'] else None} for k,v in totals.items()};reviews.append({'meeting':source['meeting'],'trueOverlapSeconds':truth_seconds,'metrics':metrics,'thirdNativeUnionNotMeasured':third})
 write(C/'result.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'COMPLETE_FIXED_POSTERIOR_MARGINAL_TRIAL_NOT_QUALIFIED','cases':reviews,'newNeuralCalls':0,'weightsOrThresholdSearch':False,'noAsrOrContentRecoveryClaim':True,'productDefaultChanged':False,'saleQualified':False});print(json.dumps(reviews,ensure_ascii=False))
