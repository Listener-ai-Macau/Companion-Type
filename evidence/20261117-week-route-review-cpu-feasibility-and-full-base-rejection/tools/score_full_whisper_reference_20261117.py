"""Reuse the original12-clip lexical scorer and its original admission gate."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import argparse,hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from score_sequential_meetings_20261115 import measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,default=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/english-full-base-r1'));args=parser.parse_args();C=args.control
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
B=read(J/'english-asr-specialist-r1/scoring-binding.json')
for file,digest in B['files'].items():assert sha(file)==digest
P=read(C/'protocol.json');state=read(C/'run/completed.json')
assert state['state']=='COMPLETE_FULL_BASE_12_CLIPS_PENDING_INDEPENDENT_SCORE'
assert len(state['completed'])==12
refs={r['id']:r for r in read(B['reference'])};moss={r['id']:r for r in read(B['mossScore'])['cases']}
rows=[];groups=defaultdict(list)
for item in state['completed']:
 assert sha(item['file'])==item['sha256'];packet=read(item['file']);case=refs[item['id']];prior=moss[item['id']]
 assert packet['naturalEos'] and not packet['referenceRead'] and not packet['wordsRewritten']
 assert case['role']=='validation' and case['language']=='English'
 assert packet['case']['pcmSha256']==case['pcmSha256'] and packet['case']['frames']==case['frames']
 score=measure(case['rawReferenceText'],packet['hypothesis'],'English')
 assert score['referenceUnits']==prior['raw']['referenceUnits']
 row={'id':case['id'],'meeting':case['meeting'],**score,'mossRawErrors':prior['raw']['errors'],
  'qwenRawErrors':prior['baselineRaw']['errors'],'inferenceSeconds':packet['seconds']}
 rows.append(row);groups[case['meeting']].append(row)
def total(items):
 n=sum(r['referenceUnits'] for r in items);e=sum(r['errors'] for r in items);m=sum(r['mossRawErrors'] for r in items)
 return {'cases':len(items),'referenceUnits':n,'errors':e,'errorRate':e/n,'mossErrors':m,
  'relativeErrorReductionVsMoss':(m-e)/m,'inferenceSeconds':sum(r['inferenceSeconds'] for r in items),
  **{k:sum(r[k] for r in items) for k in ['substitutions','deletions','insertions']}}
aggregate=total(rows);meetings=[{'meeting':k,**total(v)} for k,v in groups.items()]
assert aggregate['referenceUnits']==709 and aggregate['mossErrors']==124
advance=aggregate['errors']<=P['gate']['maximumEnglishErrors'] and all(r['errors']<=r['mossErrors'] for r in meetings)
result={'at':datetime.now().astimezone().isoformat(),'state':'PASS_FIXED_FULL_BASE_ADMISSION_WHOLE_MEETINGS_PENDING' if advance else 'REJECT_FIXED_FULL_BASE_ADMISSION_NO_GRID',
 'aggregate':aggregate,'meetings':meetings,'cases':rows,'advanceToWholeEnglish':advance,'originalGate':P['gate'],
 'priorTurboQ8Errors':195,'priorFullPrecisionTdtErrors':123,'sameOriginal709WordsAndAllAudioBytes':True,
 'scorerSha256':sha(__file__),'originalMeasureSourceSha256':sha(S/'score_sequential_meetings_20261115.py'),
 'priorScoringBindingSha256':sha(J/'english-asr-specialist-r1/scoring-binding.json'),
 'completedInferenceSha256':sha(C/'run/completed.json'),'modelSha256':P['modelSha256'],
 'wordFivePercentFloorPassedOnExposedClips':aggregate['errorRate']<.05,'wholeMeetingOrPersonQualityProven':False,
 'newTrainingUpdates':0,'newInferenceByScorer':0,'finalHoldoutOpened':False,'qualityQualified':False,'saleQualified':False,
 'next':'Run original complete English meetings with the same fixed native profile.' if advance else 'Retain and end this full-base profile. No parameter/precision grid or claim that all pretrained English architectures are exhausted.'}
assert not(C/'score.json').exists();atomic_json(C/'score.json',result)
print(json.dumps({k:result[k] for k in ['state','aggregate','meetings','advanceToWholeEnglish','qualityQualified']},ensure_ascii=False))
