from pathlib import Path
import hashlib,json,os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from reference_textgrid_20261104 import read_reference_intervals
from rapidfuzz.distance import Levenshtein
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
D=C/'d1d2-execution/fixed-adapter-full-r1'
source=(S/'full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
start=source.index('def normalize(');end=source.index('\ndef ',start+1)
scope={'re':__import__('re'),'unicodedata':__import__('unicodedata')};exec(source[start:end],scope)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
rows=[]
for case in read(C/'d1d2-execution/cached-global-identity-r1/scoring-only.json'):
 assert hashlib.sha256(Path(case['reference']).read_bytes()).hexdigest()==case['referenceSha256']
 ref=scope['normalize'](''.join(r['text'] for r in sorted(read_reference_intervals(case['reference']),key=lambda r:(r['start'],r['end']))))
 if case['meeting']=='S_R004S03C01':
  file=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-author-boundaries-r6/full/transcripts'/case['meeting']/'model-output.json'
  text=read(file)['text'];expected=(8325,461)
 else:
  file=C/'combination-study-r1/exclusive-frozen/transcripts'/('qwen-'+case['meeting'])/'attribution-review.json'
  text=read(file)['rawWindowText'];expected=(7153,1037)
 hyp=scope['normalize'](text);ops=Levenshtein.editops(ref,hyp)
 assert (len(ref),len(ops))==expected
 rows.append({'meeting':case['meeting'],'referenceCharacters':len(ref),'errors':len(ops),
  'cer':len(ops)/len(ref),'source':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
  'counts':{tag:sum(op.tag==tag for op in ops) for tag in ['replace','delete','insert']}})
out=D/'baseline-score-control.json';assert not out.exists()
out.write_text(json.dumps({'state':'PASS_ORIGINAL_FULL_BASELINE_SCORES_REPRODUCED_BEFORE_CANDIDATE_SCORING',
 'rows':rows,'newNeuralCalls':0,'qualificationReferenceChanged':False,'limits':limits.query()},indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows))
