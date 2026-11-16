"""Independent CPU scoring. The original full-source identity mapping stays fixed."""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from score_sequential_meetings_20261115 import tokens,measure
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
 B=read(a.control/'scoring-binding.json');source=Path(B['sourceControl'])
 for name,key in [('audio-only.json','audioManifestSha256'),('scoring-only.json','scoringManifestSha256'),('raw-text-baseline.json','rawBaselineSha256'),('speaker-baseline.json','speakerBaselineSha256')]:assert sha(source/name)==B[key]
 fixed=read(a.control/'composition-input.json');assert sha(__file__)==fixed['scorerSha256']
 reference={r['id']:r for r in read(source/'scoring-only.json')};rawbase={r['id']:r for r in read(source/'raw-text-baseline.json')['cases']}
 speakerbase=read(source/'speaker-baseline.json');base={r['id']:r for r in speakerbase['cases']}
 identity={r['meeting']:{int(k):v for k,v in r['nativeToReference'].items()} for r in speakerbase['meetingIdentities']}
 state=read(a.run/'composition-state.json');assert state['state']=='COMPLETE_CPU_WINDOW_COMPOSITION_NOT_QUALIFIED' and len(state['completed'])==32
 outputs=[];groups=defaultdict(list);meetings=defaultdict(list)
 for item in state['completed']:
  assert sha(item['file'])==item['sha256'];doc=read(item['file']);case=reference[item['id']];lang=case['language'];join=' ' if lang=='English' else ''
  assert sha(doc['rawFile'])==doc['rawSha256'];packet=read(doc['rawFile']);assert packet['naturalEos'] and not packet['wasTruncated']
  refs=defaultdict(list);hyps=defaultdict(list)
  for r in case['referenceEvents']:
   if r['text']:refs[r['speaker']].append(r['text'])
  for r in doc['rows']:hyps[identity[case['meeting']].get(r['nativeWholeMeetingSpeaker'],'UNKNOWN')].append(r['text'])
  persons=[]
  for who in sorted(set(refs)|set(hyps)):
   ref,hyp=join.join(refs[who]),join.join(hyps[who]);persons.append({'speaker':who,'reference':ref,'hypothesis':hyp,**measure(ref,hyp,lang)})
  raw_hyp=join.join(r['text'] for r in doc['rows']);raw=measure(case['rawReferenceText'],raw_hyp,lang)
  # Concatenation must preserve all recognized lexical units, including unknowns.
  assert sum(len(tokens(join.join(v),lang)) for v in hyps.values())==len(tokens(raw_hyp,lang))
  baseline=base[case['id']]['views']['exclusive'];denom=sum(x['referenceUnits'] for x in persons);assert denom==raw['referenceUnits']==baseline['referenceUnits']
  row={'id':case['id'],'meeting':case['meeting'],'role':case['role'],'language':lang,'speakerReturn':case['speakerReturn'],
   'raw':raw,'speakerAttributed':{'errors':sum(x['errors'] for x in persons),'referenceUnits':denom,'perPerson':persons,'unknownHypothesisUnits':len(tokens(join.join(hyps['UNKNOWN']),lang))},
   'baselineRaw':rawbase[case['id']], 'baselineSpeakerAttributed':{'errors':baseline['errors'],'referenceUnits':baseline['referenceUnits']},
   'DERReusedUnchanged':base[case['id']]['exclusiveDER'],'identityMappingFixedFromWholeSource':True,'seconds':packet['seconds'],'audioSeconds':packet['case']['audioSeconds']}
  outputs.append(row);groups[(lang,case['role'])].append(row);meetings[(case['meeting'],lang,case['role'])].append(row)
 def total(rows):
  denominator=sum(r['raw']['referenceUnits'] for r in rows);raw=sum(r['raw']['errors'] for r in rows);person=sum(r['speakerAttributed']['errors'] for r in rows)
  d=sum(r['DERReusedUnchanged']['referenceSpeakerSeconds'] for r in rows);bad=sum(r['DERReusedUnchanged']['errorSeconds'] for r in rows)
  baseline_raw=sum(r['baselineRaw']['errors'] for r in rows);baseline_person=sum(r['baselineSpeakerAttributed']['errors'] for r in rows)
  elapsed=sum(r['seconds'] for r in rows);audio=sum(r['audioSeconds'] for r in rows)
  return {'cases':len(rows),'speakerReturnCases':sum(r['speakerReturn'] for r in rows),'referenceUnits':denominator,
   'rawErrors':raw,'rawErrorRate':raw/denominator,'speakerAttributedErrors':person,'speakerAttributedErrorRate':person/denominator,
   'baselineRawErrors':baseline_raw,'baselineRawErrorRate':baseline_raw/denominator,'baselineSpeakerAttributedErrors':baseline_person,'baselineSpeakerAttributedErrorRate':baseline_person/denominator,
   'DERReusedUnchanged':bad/d,'DERImprovedByThisCandidate':False,'inferenceSeconds':elapsed,'audioSeconds':audio,'asrRealTimeFactor':elapsed/audio,
   'rawGatePass':raw/denominator<.05,'speakerAttributedGatePass':person/denominator<.05,'DERGatePass':bad/d<=.1,
   'everyPersonBelowFivePercent':all(p['rate'] is not None and p['rate']<.05 for r in rows for p in r['speakerAttributed']['perPerson']),
   'unknownHypothesisUnits':sum(r['speakerAttributed']['unknownHypothesisUnits'] for r in rows)}
 result={'state':'CPU_WINDOW_COMPOSITION_SCORED_NOT_PRODUCT_QUALIFIED','scorerSha256':sha(__file__),'compositionStateSha256':sha(a.run/'composition-state.json'),
  'groups':[dict(language=k[0],role=k[1],**total(rows)) for k,rows in groups.items()],
  'meetings':[dict(meeting=k[0],language=k[1],role=k[2],**total(rows)) for k,rows in meetings.items()],
  'speakerReturnOnly':[dict(language=k[0],role=k[1],**total([r for r in rows if r['speakerReturn']])) for k,rows in groups.items() if any(r['speakerReturn'] for r in rows)],
  'cases':outputs,'qualityQualified':False,'wholeMeetingAcceptance':False,'productDefaultChanged':False,'newWeightTraining':False,'factsGateMeasured':False,'blindFinalHoldoutOpened':False,
  'limitations':['32 preselected natural nonoverlap windows, not whole meetings or blind final acceptance.','Train-role diagnostics and validation are reported separately.','ASR ran strictly on CPU; original whole-source speaker predictions were reused, so complete CPU speaker runtime and end-to-end product latency remain unmeasured.','Predicted local-to-global speaker mapping uses no references; scoring reuses the frozen whole-source Nemotron-to-reference identity mapping.','DER reuses unchanged Nemotron exclusive activity and cannot show improvement from changing ASR.','All raw lexical content, fillers, numbers and unknown words retained.','BF16 GGUF/f16 KV port is separately versioned; no claim of bitwise parity with native HF BF16 runtime.'],
  'limits':limits.query()}
 atomic_json(a.control/'score.json',result);print(json.dumps({'state':result['state'],'groups':result['groups'],'meetings':result['meetings']},ensure_ascii=False))
if __name__=='__main__':main()
