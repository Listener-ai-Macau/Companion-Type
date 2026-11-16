"""Original Chinese full raw/person and raw voice DER; no tolerance or label edits."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from score_joint_whole_meetings_20261115 import lexical_references,units,measure,person_score,activity_score,rttm
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args();limits=WorkerLimits(cpu_percent=1,memory_bytes=512*1024**2)
 frozen=read(a.control/'scoring-binding.json');assert sha(__file__)==frozen['scorerSha256']
 for file,digest in frozen['files'].items():assert sha(file)==digest
 composition=read(a.run/'composition-state.json');assert composition['state']=='COMPLETE_CPU_ALIGNMENT_CONTINUOUS_VOICES_ON_RETAINED_ASR_COMPOSITION_NOT_QUALIFIED';results=[]
 raw_scores=read(frozen['rawAsrWholeScore']);assert sha(frozen['rawAsrWholeScore'])==frozen['rawAsrWholeScoreSha256']
 for case in read(a.control/'whole-scoring-only.json')['cases']:
  item=next(x for x in composition['meetings'] if x['meeting']==case['meeting']);assert sha(item['document'])==item['documentSha256'] and sha(item['review'])==item['reviewSha256']
  document=read(item['document']);review=read(item['review']);reference=lexical_references(case);refunits=[u for x in reference for u in units(x['text'],'Chinese')]
  raw=measure(refunits,units(document['text'],'Chinese'));previous=next(x for x in raw_scores['meetings'] if x['meeting']==case['meeting']);assert raw==previous['rawText']
  hypothesis=[{'text':x['text'],'speaker':str(x['speaker']) if x['speaker'] is not None else None,'start':x['start'] if x['start'] is not None else float('inf'),'end':x['end'] if x['end'] is not None else float('inf')} for x in review['tokenEstimates']]
  person=person_score(reference,hypothesis,'Chinese');source=review['rawSpeakerJournal'];assert sha(source['sourceJournal'])==source['sourceJournalSha256']
  producer=read(source['producer']);assert sha(source['producer'])==source['producerSha256'];predicted_rttm=Path(source['sourceJournal']).with_name('predicted.rttm');assert sha(predicted_rttm)==producer['rttmSha256']
  activity=read(case['activityReference']);assert sha(case['activityReference'])==case['activityReferenceSha256'];der=activity_score(activity,rttm(predicted_rttm),case['audioSeconds'])
  refs=defaultdict(list);hyps=defaultdict(list);unknown=[];native_for_display={str(v):'speaker_'+str(k) for k,v in review['nativeToConsecutiveDisplaySpeakerIds'].items()}
  for row in reference:refs[row['speaker']].extend(units(row['text'],'Chinese'))
  for row in hypothesis:
   target=der['identityForScoringOnly'].get(native_for_display.get(row['speaker'])) if row['speaker'] is not None else None
   (unknown if target is None else hyps[target]).extend(units(row['text'],'Chinese'))
  people=[{'speaker':name,**measure(refs[name],hyps[name])} for name in sorted(set(refs)|set(hyps))]
  fixed_errors=sum(x['errors'] for x in people)+len(unknown);assert sum(len(x) for x in refs.values())==len(refunits)
  fixed={'errors':fixed_errors,'referenceUnits':len(refunits),'errorRate':fixed_errors/len(refunits),'unknownUnitsForcedUnmatched':len(unknown),'perPerson':people,
   'mappingScope':'One raw continuous CPU Nemotron activity identity for the whole original meeting; no lexical or per-window identity fitting.'}
  assert sum(len(x) for x in hyps.values())+len(unknown)==len(units(document['text'],'Chinese'))
  results.append({'meeting':case['meeting'],'rawText':raw,'personTextFixedOriginalActivityIdentity':fixed,'personTextOneWholeMeetingPermutationDiagnostic':person,'originalReferenceRawContinuousSpeakerDER':der,
   'rawTextGatePass':raw['errorRate']<.05,'personTextGatePass':fixed['errorRate']<.05 and all(x['errorRate'] is not None and x['errorRate']<.05 for x in people),'derGatePass':der['DER']<=.1,
   'originalBaselineRawText':previous['nativeBaselineRawText'],'originalBaselinePersonErrorRate':case['baselinePersonErrorRate'],
   'originalBaselineDER':case['baselineDER'],'invalidTimeUnits':item['invalidTimeUnits'],'unknownSpeakerUnits':item['unknownSpeakerUnits'],
   'document':item['document'],'documentSha256':item['documentSha256'],'qualityQualified':False})
 result={'state':'COMPLETE_CPU_ALIGNMENT_VOICES_ON_RETAINED_NATIVE_ASR_FULL_MEETING_SCORED_NOT_PRODUCT_QUALIFIED','at':datetime.now().astimezone().isoformat(),'meetings':results,
  'sourceAsrInferenceBackend':composition['sourceAsrInferenceBackend'],'wholeAsrAlignmentSpeakerCpuRerun':False,
  'rawAsrErrorsUnchangedThroughComposition':True,'allUnknownWordsForcedUnmatched':True,'originalGatesAndScorerHelpersUnchanged':True,
  'englishUniversalCpuPortRejectionRetained':True,'actualInstalledNativeAppTested':False,'newWeightTraining':False,'trueWordTimeAccuracyMeasured':False,
  'finalBlindHoldoutOpened':False,'factsMeasured':False,'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
 target=a.control/'full-score.json';assert not target.exists();atomic_json(target,result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
