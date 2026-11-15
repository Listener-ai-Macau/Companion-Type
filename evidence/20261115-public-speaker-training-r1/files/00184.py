"""Use the original full-continuous-time scorer, never training raster labels."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,runpy,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
p.add_argument('--phase',choices=['baseline','candidate'],required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(a.control/'protocol.json');state=read(a.run/'state.json')
assert state['state']=='COMPLETE_PUBLIC_SPEAKER_VALIDATION_SCORE_PENDING'
assert state['optimizerUpdates']==0 and not state['referenceUsedForValidationInference']
assert sha(a.control/'validation-scoring-only.json')==P['validationScoringSha256']
cases=read(a.control/'validation-scoring-only.json');reports=[]
for case in cases:
 directory=a.run/'results'/case['meeting'];binding=read(directory/'result.json')
 assert binding['allFramesPreserved'] and binding['audioSha256']==case['audioSha256']
 assert sha(directory/'predicted.rttm')==binding['rttmSha256']
 scorer_case=directory/'scoring-case.json';assert not scorer_case.exists()
 scorer_case.write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 sys.argv=[str(S/'score_cross_corpus_diarization_20261103.py'),'--case',str(scorer_case),
  '--rttm',str(directory/'predicted.rttm'),'--out',str(directory/'original-reference-score.json')]
 runpy.run_path(str(S/'score_cross_corpus_diarization_20261103.py'),run_name='__main__')
 reports.append(read(directory/'original-reference-score.json'))
total=sum(r['components']['total'] for r in reports)
error=sum(r['components']['false alarm']+r['components']['missed detection']+r['components']['confusion'] for r in reports)
result={'state':'COMPLETE_PUBLIC_HELD_MEETING_BASELINE_SCORES_BEFORE_TRAINING' if a.phase=='baseline' else 'COMPLETE_PUBLIC_HELD_MEETING_CANDIDATE_SCORES',
 'at':datetime.now().astimezone().isoformat(),'phase':a.phase,'run':str(a.run),
 'reports':reports,'totalReferenceSpeakerSeconds':total,'totalErrorSeconds':error,'aggregateDer':error/total,
 'bothSpeakerDerAtMost10Percent':all(r['components']['diarization error rate']<=.1 for r in reports),
 'originalReferenceAndScorerUnchanged':True,'qualityQualified':False,'saleQualified':False,'newNeuralCalls':0,'limits':limits.query()}
if a.phase=='candidate':
 baseline=read(a.control/'baseline-decision.json');prior={r['meeting']:r for r in baseline['reports']}
 gains={r['meeting']:prior[r['meeting']]['components']['diarization error rate']-r['components']['diarization error rate'] for r in reports}
 keep=all(v>=-1e-12 for v in gains.values()) and error<baseline['totalErrorSeconds']-1e-9
 result.update(baselineAggregateDer=baseline['aggregateDer'],perMeetingDerReduction=gains,
  validationKeepRulePassed=keep,decision='RETAIN_FOR_ORIGINAL_COMPLETE_DEVELOPMENT_GATES_ONLY' if keep else 'REJECT_FIXED_SPEAKER_ADAPTER_NO_CONSISTENT_HELD_MEETING_GAIN',
  automaticProductAdoption=False,fullD2Qualification=False)
target=a.control/(a.phase+'-decision.json');assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['reports','limits']},ensure_ascii=False))
