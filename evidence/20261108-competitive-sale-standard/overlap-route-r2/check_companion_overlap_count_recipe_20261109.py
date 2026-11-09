"""Compare new count-only output against the retained published-recipe functions."""
from pathlib import Path
import hashlib,json,os,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109/automatic-cross-meeting-r2/independent-overlap-candidate-r1';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from bounded_speaker_20261107 import powerset_labels,bounded_votes,vote_segments
import numpy as np
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
rows=[]
for name in ['S_R004S03C01','L_R003S01C02']:
 source=Path('E:/CodexData/Companion/.model-cache/bounded-speaker-20261107-full-r1')/name;manifest=read(source/'segment.json');prediction=read(C/(name+'-prediction.json'));logits=np.load(source/'segment.npy',mmap_mode='r',allow_pickle=False);labels=powerset_labels(logits)
 # Identity-free comparison: no embeddings or clustered globalperson labels.
 _,expected,_=bounded_votes(labels,[],np.asarray([0],dtype=np.int32),manifest['meta'],prediction['sourceFrames']);assert int(expected.max())<=2
 dummy_votes=np.zeros((len(expected),2),dtype=np.uint8)
 old=vote_segments(dummy_votes,expected,manifest['meta'],0.,0.);old=[{'start':r['start'],'end':min(r['end'],prediction['sourceFrames']/16000)} for r in old if r['speaker']==1]
 assert old==prediction['regions'],'Count-only regions diverge from existing author-recipe count and coordinate functions'
 rows.append({'meeting':name,'sourceFrames':prediction['sourceFrames'],'localSpeakerCountFrames':len(expected),'countOnlyRegionsEqualExistingPublishedRecipeExactly':True,'expectedFrameCountSha256':hashlib.sha256(expected.tobytes()).hexdigest(),'sourceLabelNamesOrEmbeddingsUsed':False})
result={'state':'PASS_SAME_LOCAL_SPEAKER_COUNT_AND_COORDINATES','cases':rows,'zeroDurationGapFilteringExplicit':True,'newNeuralCalls':0,'limits':limits.query(),'saleQualified':False};(C/'author-count-recipe-proof.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
