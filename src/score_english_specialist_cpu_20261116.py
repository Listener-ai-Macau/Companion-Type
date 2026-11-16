"""Frozen strict English lexical score; compare the same12 validation clips only."""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json
from score_sequential_meetings_20261115 import measure
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2)
 B=read(a.control/'scoring-binding.json');assert sha(__file__)==B['scorerSha256']
 for file,digest in B['files'].items():assert sha(file)==digest
 protocol=read(a.control/'protocol.json');state=read(a.run/'inference-state.json');run=read(a.run/'run.json')
 assert state['state']==run['state']=='COMPLETE_ENGLISH_SPECIALIST_CLIPS_SCORING_PENDING'
 reference={r['id']:r for r in read(B['reference'])};old=read(B['mossScore']);base={r['id']:r for r in old['cases']}
 assert {r['id'] for r in state['completed']}=={r['id'] for r in protocol['cases']}
 rows=[];groups=defaultdict(list)
 for item in state['completed']:
  assert sha(item['file'])==item['sha256'];packet=read(item['file']);case=reference[item['id']];previous=base[item['id']]
  assert case['language']=='English' and case['role']=='validation' and packet['naturalEos'] and not packet['wasTruncated']
  assert packet['case']['pcmSha256']==case['pcmSha256'] and packet['case']['frames']==case['frames']
  score=measure(case['rawReferenceText'],packet['hypothesis'],'English')
  row={'id':case['id'],'meeting':case['meeting'],'role':case['role'],'reference':case['rawReferenceText'],
   'hypothesis':packet['hypothesis'],'nativeRaw':packet['rawDecoded'],**score,'mossRawErrors':previous['raw']['errors'],
   'qwenRawErrors':previous['baselineRaw']['errors'],'audioSeconds':case['audioSeconds'],'inferenceSeconds':packet['seconds']}
  assert row['referenceUnits']==previous['raw']['referenceUnits'];rows.append(row);groups[case['meeting']].append(row)
 def total(items):
  n=sum(r['referenceUnits'] for r in items);e=sum(r['errors'] for r in items);m=sum(r['mossRawErrors'] for r in items);q=sum(r['qwenRawErrors'] for r in items)
  return {'cases':len(items),'referenceUnits':n,'errors':e,'errorRate':e/n,'mossErrors':m,'mossErrorRate':m/n,'qwenErrors':q,'qwenErrorRate':q/n,
   'relativeErrorReductionVsMoss':(m-e)/m,'inferenceSeconds':sum(r['inferenceSeconds'] for r in items),'audioSeconds':sum(r['audioSeconds'] for r in items),
   **{k:sum(r[k] for r in items) for k in ['substitutions','deletions','insertions']}}
 aggregate=total(rows);meetings=[dict(meeting=k,**total(v)) for k,v in groups.items()]
 assert aggregate['cases']==12 and aggregate['referenceUnits']==709 and aggregate['mossErrors']==124 and aggregate['qwenErrors']==141
 advance=aggregate['errors']<=protocol['advanceGate']['maximumEnglishErrors'] and all(r['errors']<=r['mossErrors'] for r in meetings)
 result={'state':'PASS_ENGLISH_SPECIALIST_CLIP_ADVANCE_GATE_WHOLE_MEETING_REQUIRED' if advance else 'REJECT_ENGLISH_SPECIALIST_CLIP_CONTRAST_NO_PARAMETER_GRID',
  'at':__import__('datetime').datetime.now().astimezone().isoformat(),'aggregate':aggregate,'meetings':meetings,'cases':rows,
  'advanceGate':protocol['advanceGate'],'advanceToWholeEnglish':advance,'scorerSha256':sha(__file__),'scoringBindingSha256':sha(a.control/'scoring-binding.json'),
  'runSha256':sha(a.run/'run.json'),'neuralRun':run,'modelSha256':state['modelSha256'],'rawTextProductGatePass':aggregate['errorRate']<.05,
  'allFillersPartialWordsNumbersKept':True,'gatesChanged':False,'speakerAttributionEvaluated':False,'DERMeasuredByThisContrast':False,
  'wholeMeetingAcceptance':False,'blindFinalHoldoutOpened':False,'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False,
  'next':'Run frozen complete original English sources before product decisions.' if advance else 'Stop candidate. Retain exact outputs and no parameter/quantization grid.',
  'limits':limits.query()}
 atomic_json(a.control/'score.json',result);print(json.dumps({k:result[k] for k in ['state','aggregate','meetings','advanceToWholeEnglish','qualityQualified']},ensure_ascii=False))
if __name__=='__main__':main()
