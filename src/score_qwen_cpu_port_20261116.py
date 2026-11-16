"""Strict regression comparison for the preferred Qwen family's fixed CPU port."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import argparse,hashlib,json
from score_sequential_meetings_20261115 import measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args();limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2)
 binding=read(a.control/'scoring-binding.json');assert sha(__file__)==binding['scorerSha256']
 for file,digest in binding['files'].items():assert sha(file)==digest
 protocol=read(a.control/'protocol.json');state=read(a.run/'inference-state.json');run=read(a.run/'run.json')
 assert state['state']==run['state']=='COMPLETE_QWEN_CPU_PORT_CLIPS_SCORING_PENDING'
 reference={r['id']:r for r in read(binding['reference'])};old={r['id']:r for r in read(binding['original32Score'])['cases']}
 assert {r['id'] for r in state['completed']}=={r['id'] for r in protocol['cases']}
 cases=[];languages=defaultdict(list);meetings=defaultdict(list)
 for item in state['completed']:
  assert sha(item['file'])==item['sha256'];packet=read(item['file']);ref=reference[item['id']];baseline=old[item['id']]
  assert ref['role']=='validation' and packet['naturalEos'] and not packet['wasTruncated'] and packet['case']['pcmSha256']==ref['pcmSha256']
  score=measure(ref['rawReferenceText'],packet['hypothesis'],ref['language']);assert score['referenceUnits']==baseline['baselineRaw']['referenceUnits']
  row={'id':ref['id'],'meeting':ref['meeting'],'language':ref['language'],'role':ref['role'],'reference':ref['rawReferenceText'],'hypothesis':packet['hypothesis'],**score,
   'nativeQwenBaselineErrors':baseline['baselineRaw']['errors'],'mossErrorsDiagnosticOnly':baseline['raw']['errors'],'seconds':packet['seconds'],'audioSeconds':ref['audioSeconds']}
  cases.append(row);languages[ref['language']].append(row);meetings[(ref['meeting'],ref['language'])].append(row)
 def total(rows):
  n=sum(r['referenceUnits'] for r in rows);e=sum(r['errors'] for r in rows);base=sum(r['nativeQwenBaselineErrors'] for r in rows)
  return {'cases':len(rows),'referenceUnits':n,'errors':e,'errorRate':e/n,'nativeBaselineErrors':base,'nativeBaselineErrorRate':base/n,
   'mossErrorsDiagnosticOnly':sum(r['mossErrorsDiagnosticOnly'] for r in rows),'noMoreErrorsThanNativeBaseline':e<=base,
   'inferenceSeconds':sum(r['seconds'] for r in rows),'audioSeconds':sum(r['audioSeconds'] for r in rows),
   **{k:sum(r[k] for r in rows) for k in ['substitutions','deletions','insertions']}}
 groups=[dict(language=k,**total(v)) for k,v in languages.items()];by_meeting=[dict(meeting=k[0],language=k[1],**total(v)) for k,v in meetings.items()]
 expected={'English':(709,141),'Chinese':(1258,73)}
 for row in groups:assert (row['referenceUnits'],row['nativeBaselineErrors'])==expected[row['language']]
 advance=all(r['noMoreErrorsThanNativeBaseline'] for r in groups+by_meeting)
 result={'state':'PASS_QWEN_CPU_DEPLOYMENT_CLIP_REGRESSION_GATE_WHOLE_VALIDATION_REQUIRED' if advance else 'REJECT_QWEN_CPU_PORT_DEPLOYMENT_REGRESSION_NO_QUANTIZATION_GRID',
  'at':datetime.now().astimezone().isoformat(),'groups':groups,'meetings':by_meeting,'cases':cases,'advanceToCompleteChinese':advance,
  'deploymentGate':protocol['deploymentAdvanceGate'],'scorerSha256':sha(__file__),'runSha256':sha(a.run/'run.json'),'execution':run,
  'naturalEosInputs':len(cases),'allOriginalGatesUnchanged':True,'speakerAttributionEvaluated':False,'timestampsUnsupportedByPort':True,
  'newWeightTraining':False,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,'holdoutOpened':False,'limits':limits.query()}
 atomic_json(a.control/'score.json',result);print(json.dumps({k:result[k] for k in ['state','groups','meetings','advanceToCompleteChinese']},ensure_ascii=False))
if __name__=='__main__':main()
