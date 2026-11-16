"""Report all full-source regressions, fixed identities and both native activity views."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from score_joint_whole_meetings_20261115 import lexical_references,units,measure,activity_score,rttm,person_score,parse_native
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3);binding=read(a.control/'composition-source-binding.json');assert sha(__file__)==binding['summaryScorerSha256']
 assert sha(a.control/'whole-scoring-only.json')==binding['wholeScoringManifestSha256']
 manifest=read(a.control/'whole-scoring-only.json');state=read(a.run/'composition-state.json');assert len(state['meetings'])==4
 outputs=[];groups=defaultdict(list)
 for case in manifest['cases']:
  meeting=case['meeting'];directory=a.run/'composed';packet=read(directory/(meeting+'-raw.json'));doc=read(directory/(meeting+'-composition.json'))
  reference=lexical_references(case);lang=case['language'];refunits=[v for r in reference for v in units(r['text'],lang)]
  assert sha(case['baselineTextFile'])==case['baselineTextSha256'];old=read(case['baselineTextFile']);baseline=measure(refunits,units(old[case['baselineTextKey']],lang))
  assert baseline['errors']==case['expectedBaselineErrors'] and baseline['referenceUnits']==case['expectedReferenceUnits']
  assert sha(case['activityReference'])==case['activityReferenceSha256']
  activity=read(case['activityReference']) if case['activityKind']=='json' else rttm(case['activityReference'])
  source=doc['source'];assert sha(source['sourceJournal'])==source['sourceJournalSha256']
  # Historical DER was computed from its six-decimal RTTM. Reuse those exact
  # bytes, rather than changing precision by substituting the native JSON.
  assert sha(source['producer'])==source['producerSha256'];producer=read(source['producer'])
  original_rttm=Path(source['sourceJournal']).with_name('predicted.rttm');assert sha(original_rttm)==producer['rttmSha256']
  original_rows=rttm(original_rttm)
  raw_der=activity_score(activity,original_rows,case['audioSeconds']);assert abs(raw_der['DER']-case['baselineDER'])<1e-8,(meeting,raw_der['DER'],case['baselineDER'])
  primary=read(directory/(meeting+'-primary-speaker-journal.json'));primary_rows=[dict(r,speaker='speaker_'+str(r['speaker'])) for r in primary['segments']]
  primary_der=activity_score(activity,primary_rows,case['audioSeconds'],identity=raw_der['identityForScoringOnly'])
  refs=defaultdict(list);hyps=defaultdict(list);unknown=[]
  for r in reference:refs[r['speaker']].extend(units(r['text'],lang))
  for r in doc['rows']:
   native=r['nativeGlobalSpeaker'];person=raw_der['identityForScoringOnly'].get('speaker_'+str(native)) if native is not None else None
   (unknown if person is None else hyps[person]).extend(units(r['text'],lang))
  persons=[{'speaker':s,**measure(refs[s],hyps[s])} for s in sorted(set(refs)|set(hyps))]
  fixed_errors=sum(r['errors'] for r in persons)+len(unknown);denominator=sum(len(v) for v in refs.values());assert denominator==len(refunits)
  parsed,all_rows,residual=parse_native(packet['rawDecoded']);hypunits=[v for r in all_rows for v in units(r['text'],lang)]
  raw=measure(refunits,hypunits);permuted=person_score(reference,all_rows,lang)
  assert len(hypunits)==sum(len(v) for v in hyps.values())+len(unknown)
  native_time=activity_score(activity,[r for r in parsed if r['start']<r['end']],case['audioSeconds'])
  pinned_file=a.control/('score-'+meeting+'.json')
  if packet['naturalEos']:
   pinned=read(pinned_file);assert pinned['rawText']==raw and pinned['personText']==permuted
  else:assert not pinned_file.exists(),'Incomplete output must not be presented as a complete original scorer pass'
  row={'meeting':meeting,'language':lang,'audioSeconds':case['audioSeconds'],'chunks':packet['chunkCount'],
   'allOriginalInputFramesCoveredExactlyOnce':packet['inputFramesCoveredExactlyOnce']==case['frames'],'allChunksNaturalEos':packet['naturalEos'],
   'incompleteOutputChunks':packet['incompleteOutputChunks'],'invalidNativeTimeSegments':packet['invalidOriginalTimeSegments'],
   'rawText':raw,'baselineRawText':baseline,'rawEditsReduced':baseline['errors']-raw['errors'],
   'personTextOneWholeMeetingPermutation':permuted,'baselinePersonErrorRate':case.get('baselinePersonErrorRate'),
   'personTextFixedOriginalActivityIdentity':{'errors':fixed_errors,'referenceUnits':denominator,'errorRate':fixed_errors/denominator,'unknownUnitsForcedUnmatched':len(unknown),'perPerson':persons,
    'mappingScope':'One original whole-source Nemotron activity mapping, unchanged across every fixed window. No per-window gold assignment.'},
   'originalNemotronRawDERReproduced':raw_der,'primaryNemotronExclusiveDER':primary_der,'secondaryMossNativeTimeDER':native_time,
   'baselineDER':case['baselineDER'],'cpuAsrInferenceSeconds':packet['cpuAsrInferenceSeconds'],
   'asrRealTimeFactor':packet['cpuAsrInferenceSeconds']/case['audioSeconds'],
   'rawGatePass':packet['naturalEos'] and raw['errorRate']<.05,
   'fixedPersonGatePass':packet['naturalEos'] and fixed_errors/denominator<.05 and all(r['errorRate'] is not None and r['errorRate']<.05 for r in persons),
   'primaryDERGatePass':primary_der['DER']<=.1,'factsGateMeasured':False,'qualityQualified':False}
  outputs.append(row);groups[lang].append(row)
 aggregate=[]
 for lang,rows in groups.items():
  n=sum(r['rawText']['referenceUnits'] for r in rows);errors=sum(r['rawText']['errors'] for r in rows);old=sum(r['baselineRawText']['errors'] for r in rows)
  attributed=sum(r['personTextFixedOriginalActivityIdentity']['errors'] for r in rows);audio=sum(r['audioSeconds'] for r in rows);seconds=sum(r['cpuAsrInferenceSeconds'] for r in rows)
  aggregate.append({'language':lang,'completeOriginalMeetings':len(rows),'audioSeconds':audio,'referenceUnits':n,'rawErrors':errors,'rawErrorRate':errors/n,
   'baselineRawErrors':old,'baselineRawErrorRate':old/n,'fixedSpeakerAttributedErrors':attributed,'fixedSpeakerAttributedErrorRate':attributed/n,
   'cpuAsrInferenceSeconds':seconds,'asrRealTimeFactor':seconds/audio,'allChunksNaturalEos':all(r['allChunksNaturalEos'] for r in rows),
   'everyMeetingImprovesRawText':all(r['rawEditsReduced']>0 for r in rows),'everyMeetingPassesRawGate':all(r['rawGatePass'] for r in rows),'qualityQualified':False})
 result={'at':datetime.now().astimezone().isoformat(),'state':'FULL4_FIXED_CPU_COMPOSITION_SCORED_NOT_PRODUCT_QUALIFIED','meetings':outputs,'groups':aggregate,
  'summaryScorerSha256':sha(__file__),'wholeScoringManifestSha256':sha(a.control/'whole-scoring-only.json'),'compositionStateSha256':sha(a.run/'composition-state.json'),
  'execution':read(a.run/'run.json'),'noReferenceInputToNeuralModels':True,'originalGatesChanged':False,'wholeMeetingAcceptance':False,'qualityQualified':False,'saleQualified':False,
  'blindFinalHoldoutOpened':False,'newWeightTraining':False,'productDefaultChanged':False,'fullCpuSpeakerModelRuntimeMeasured':False,
  'limitations':['All4 recordings are previously seen development/regression cases, not a blind final cohort.','Fixed30s nonoverlap chunks keep all input audio; native output may omit boundary speech and all such errors remain counted.','The primary whole-source Nemotron journal reuses original GPU predictions; CPU speaker execution remains a separate required check.','MOSS native-time DER is a secondary diagnostic; it does not replace the primary activity journal or recover simultaneous voices.','Any incomplete EOS window remains visible and cannot pass complete-output gates.','Unknown words and all original numbers/fillers remain counted; no post-editing or reference corrections.','Facts and critical facts have not been accepted.'],
  'limits':limits.query()}
 atomic_json(a.control/'full-score.json',result);print(json.dumps({'state':result['state'],'groups':aggregate,'meetings':[{k:r[k] for k in ['meeting','rawText','rawEditsReduced','personTextFixedOriginalActivityIdentity','primaryNemotronExclusiveDER','secondaryMossNativeTimeDER']} for r in outputs]},ensure_ascii=False))
if __name__=='__main__':main()
