"""One predeclared cached local-count candidate; no references, new models or tuning."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import collections,hashlib,json,os,sys,time,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109/automatic-cross-meeting-r2';O=C/'independent-overlap-candidate-r1';O.mkdir(exist_ok=False);sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);pressure=SystemRamPressure()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources=[M/'src/companion_local_overlap_regions_20261109.py',M/'src/companion_meeting_route_plan_20261109.py',M/'src/bounded_speaker_20261107.py',Path(__file__)]
base=R/'docs/handoffs/20261107-model-generation-recovery/bounded-speaker-full-r1';P=read(base/'protocol.json');cases=read(R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/audio-only.json')
write(O/'protocol.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'policy':'For both same complete development meetings, use frozen powerset7 argmax local2voice count from existing neuralcache, published rounded crosswindowmean, no new threshold or min-duration/padding rule. Union with existing native8 positiveoverlap in routeplan. If localdetector flags overlap but journal supplies<2 identities, explicit identity_pending; never invent a person. Preserve rawaudio/text, no default replacement.','whyDifferent':'Prior complete diarization pipeline additionally required embeddings, globalclustering and assignedspeakerlabels. This candidate uses only independent acoustic localvoicecount to find overlap that native8journal omitted; no need re-run/checkpoint shopping.','reportBeforeDecision':'Fullsame-source overlap recall/precision, new ordinary falseoverlap seconds, coverage by2/3voices, preservedallsourceframes. No thresholdfit afterresult. Must not promote if contentprotection unresolved.','sourceFiles':[{'file':str(p),'sha256':sha(p)} for p in sources],'cachedModelProtocol':str(base/'protocol.json'),'cachedModelProtocolSha256':sha(base/'protocol.json'),'newNeuralCalls':0,'newTrainingOrDownloads':False,'saleQualified':False})
import numpy as np
from companion_local_overlap_regions_20261109 import local_overlap_regions
from companion_meeting_route_plan_20261109 import plan_routes
started=time.perf_counter();runs=[]
for case in cases:
 if pressure.low():raise RuntimeError('ActualWindowsLOWRAM;stopthiscandidate')
 cache=Path(P['boundedCacheRoot'])/case['meeting'];manifest=read(cache/'segment.json');a=np.load(cache/'segment.npy',mmap_mode='r',allow_pickle=False);assert manifest['state']=='COMPLETE_SEGMENTATION_CACHE' and manifest['done']==manifest['total']==len(a);assert manifest['binding']['audioSha256']==case['audioSha256'] and manifest['binding']['segmentationSha256']==P['segmentation']['sha256'];assert hashlib.sha256(memoryview(np.asarray(a[:manifest['done']])).cast('B')).hexdigest()==manifest['committedPrefixSha256']
 with wave.open(case['audio'],'rb') as f:frames=f.getnframes();rate=f.getframerate()
 tick=time.perf_counter();regions,metadata=local_overlap_regions(a,manifest['meta'],source_frames=frames);journal=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results'/case['meeting']/'speaker-journal.json';j=read(journal);assert j['audioSha256']==case['audioSha256'];routes=plan_routes(j['segments'],source_frames=frames,sample_rate=rate,overlap_regions=regions);totals=collections.Counter()
 for row in routes:totals[row['route']]+=row['endSample']-row['startSample']
 result={'meeting':case['meeting'],'sourceAudio':case['audio'],'sourceSha256':case['audioSha256'],'journalSha256':sha(journal),'segmentationManifestSha256':sha(cache/'segment.json'),'cachedSegmentCommittedPrefixSha256':manifest['committedPrefixSha256'],'regions':regions,'metadata':metadata,'sourceFrames':frames,'sampleRate':rate,'routes':routes,'sourceFramesPreservedExactlyOnce':sum(totals.values())==frames,'secondsByRoute':{k:v/rate for k,v in totals.items()},'elapsedSeconds':time.perf_counter()-tick,'newNeuralCalls':0,'globalIdentityInvented':False,'audioModifiedOrSuppressed':False,'productDefaultChanged':False,'saleQualified':False};write(O/(case['meeting']+'-prediction.json'),result);runs.append({k:result[k] for k in ['meeting','secondsByRoute','elapsedSeconds','sourceFramesPreservedExactlyOnce']});del a
write(O/'run.json',{'state':'COMPLETE_CACHED_INDEPENDENT_OVERLAP_CANDIDATE','cases':runs,'elapsedSeconds':time.perf_counter()-started,'limits':limits.query(),'newNeuralCalls':0,'saleQualified':False});print(json.dumps(runs,ensure_ascii=False))
