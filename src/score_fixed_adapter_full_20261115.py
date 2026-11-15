"""One frozen full-meeting candidate score, independent of the model worker."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from reference_textgrid_20261104 import read_reference_intervals
from rapidfuzz.distance import Levenshtein
R=S.parent.parent
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
D=C/'d1d2-execution/fixed-adapter-full-r1'
p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);a=p.parse_args()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
source=(S/'full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
start=source.index('def normalize(');end=source.index('\ndef ',start+1)
scope={'re':__import__('re'),'unicodedata':__import__('unicodedata')};exec(source[start:end],scope)
normalize=scope['normalize']
cases=read(D/'audio-only.json');case=cases[a.index]
reference_case=next(c for c in read(C/'d1d2-execution/cached-global-identity-r1/scoring-only.json') if c['meeting']==case['meeting'])
assert reference_case['audioSha256']==case['audioSha256']
assert sha(reference_case['reference'])==reference_case['referenceSha256']
directory=D/'full/transcripts'/case['meeting'];state=read(directory/'completed-state.json')
assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
assert state['allAudioSamplesCoveredOnce'] and state['allAsrTextPreserved']
assert state['modelOutputSha256']==sha(directory/'model-output.json')
doc=read(directory/'model-output.json');assert doc['isFinal']
rows=read_reference_intervals(reference_case['reference'])
ref=normalize(''.join(row['text'] for row in sorted(rows,key=lambda r:(r['start'],r['end']))))
if a.index==0:
 base=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-author-boundaries-r6/full/transcripts'/case['meeting']/'model-output.json'
 baseline=read(base)['text'];expected=461
else:
 base=C/'combination-study-r1/exclusive-frozen/transcripts'/('qwen-'+case['meeting'])/'attribution-review.json'
 baseline=read(base)['rawWindowText'];expected=1037
def score(text):
 hyp=normalize(text);ops=Levenshtein.editops(ref,hyp)
 return {'referenceCharacters':len(ref),'recognizedCharacters':len(hyp),'totalEdits':len(ops),
   'edits':{tag:sum(op.tag==tag for op in ops) for tag in ['replace','delete','insert']},
   'cer':len(ops)/len(ref),'strictRawCerLessThan5Percent':len(ops)/len(ref)<.05}
b=score(baseline);candidate=score(doc['text']);assert b['totalEdits']==expected
report={'state':'COMPLETE_FROZEN_ADAPTER_FULL_MEETING_RAW_TEXT_SCORE',
 'at':datetime.now().astimezone().isoformat(),'meeting':case['meeting'],'audioSeconds':case['audioSeconds'],
 'audioSha256':case['audioSha256'],'referenceSha256':reference_case['referenceSha256'],
 'baselineSource':str(base),'baselineSourceSha256':sha(base),'baseline':b,'candidate':candidate,
 'candidateOutputSha256':state['modelOutputSha256'],'candidateStateSha256':sha(directory/'completed-state.json'),
 'editsReduced':b['totalEdits']-candidate['totalEdits'],
 'normalizationSourceSha256':hashlib.sha256(source[start:end].encode()).hexdigest(),
 'noScoringDefinitionsChanged':True,'noReferenceUsedDuringInference':True,'newTrainingUpdates':0,
 'allAudioSamplesCoveredOnce':True,'allRawAsrTextPreserved':True,'qualityQualified':False,
 'scope':'Full chronological original ASR characters only; overlap has no unique merged order. This is not per-person text, diarization, minutes, device or sale acceptance.',
 'limits':limits.query()}
out=D/('raw-score-'+case['meeting']+'.json');assert not out.exists()
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
