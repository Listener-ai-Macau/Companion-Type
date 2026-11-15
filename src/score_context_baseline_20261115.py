"""Score the frozen diagnostic conditions separately, outside inference."""
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
import argparse,hashlib,json,os,re,unicodedata
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from rapidfuzz.distance import Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 protocol=read(a.control/'protocol.json');state=read(a.run/'baseline-state.json')
 assert state['state']=='COMPLETE_FROZEN_CONTEXT_BASELINE_UNQUALIFIED' and len(state['completed'])==32
 assert state['parameterUpdates']==0 and state['validationReferenceRead'] is False
 assert sha(a.control/'scoring-only.json')==protocol['scoringOnlyManifestSha256']
 scoring=read(a.control/'scoring-only.json');assert len(scoring)==32
 source=(Path(__file__).parent/'full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
 start=source.index('def normalize(');end=source.index('\ndef ',start+1)
 scope={'re':re,'unicodedata':unicodedata};exec(source[start:end],scope);normalize=scope['normalize']
 rows=[]
 for case in scoring:
  completed=next(c for c in state['completed'] if c['id']==case['id'])
  assert sha(completed['document'])==completed['documentSha256'] and completed['pcmSha256']==case['pcmSha256']
  assert sha(case['reference'])==case['referenceSha256']
  doc=read(completed['document']);assert doc['isFinal'] and doc['confirmedAudioFrames']==case['frames']
  ref,hyp=normalize(case['rawReferenceText']),normalize(doc['text']);assert ref
  ops=Levenshtein.editops(ref,hyp)
  rows.append({'id':case['id'],'meeting':case['meeting'],'condition':case['condition'],
   'overlapPresent':case['overlapPresent'],'audioSeconds':case['audioSeconds'],
   'referenceCharacters':len(ref),'recognizedCharacters':len(hyp),'totalEdits':len(ops),
   'edits':dict(Counter(op.tag for op in ops)),'cer':len(ops)/len(ref),
   'rawReferenceText':case['rawReferenceText'],'rawAsrText':doc['text'],
   'normalizedReference':ref,'normalizedHypothesis':hyp,'reviewRequired':doc['reviewRequired'],
   'unconfirmedAudioIntervals':[r for u in doc['utterances'] for r in u['unconfirmedAudioIntervals']],
   'documentSha256':completed['documentSha256']})
 def aggregate(items):
  counts=Counter()
  for r in items:counts.update(r['edits'])
  chars=sum(r['referenceCharacters'] for r in items);edits=sum(r['totalEdits'] for r in items)
  return {'cases':len(items),'audioSeconds':sum(r['audioSeconds'] for r in items),
   'referenceCharacters':chars,'recognizedCharacters':sum(r['recognizedCharacters'] for r in items),
   'totalEdits':edits,'edits':dict(counts),'cer':edits/chars,
   'reviewRequiredCases':sum(r['reviewRequired'] for r in items)}
 conditions=sorted({r['condition'] for r in rows})
 report={'state':'COMPLETE_FROZEN_BASE_ONLY_CONDITION_DIAGNOSTIC_NOT_QUALIFICATION',
  'at':datetime.now().astimezone().isoformat(),'protocolSha256':sha(a.control/'protocol.json'),
  'baselineStateSha256':sha(a.run/'baseline-state.json'),'normalizationSourceSha256':hashlib.sha256(source[start:end].encode()).hexdigest(),
  'byCondition':{c:aggregate([r for r in rows if r['condition']==c]) for c in conditions},
  'byMeetingAndCondition':{m:{c:aggregate([r for r in rows if r['meeting']==m and r['condition']==c]) for c in conditions} for m in sorted({r['meeting'] for r in rows})},
  'cases':rows,'neuralCalls':state['neuralCalls'],'newParameterUpdates':0,'validationReferencesUsedDuringInference':False,
  'rawAsrWordsPostEdited':False,'fullMeetingGatesChanged':False,'finalHoldoutOpened':False,'qualityQualified':False,
  'interpretationLimits':protocol['limitations'],
  'nextAction':'Review the two conditions before deciding whether a data-only intervention is justified. Do not automatically train, pool overlapping source coverage, select additional clips based on errors, or treat this as original D2 acceptance.',
  'limits':limits.query()}
 target=a.control/'baseline-score.json';assert not target.exists()
 target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:report[k] for k in ['state','byCondition','byMeetingAndCondition','neuralCalls']},ensure_ascii=False))

if __name__=='__main__':main()
