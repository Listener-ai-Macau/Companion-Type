"""Scoring only; references never enter CPU/GPU inference manifests."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,re,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261109-sedicow-r1';sys.path.insert(0,str(M/'src'))
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
from rapidfuzz.distance import Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','score']);p.add_argument('--control');a=p.parse_args()
if a.phase=='prepare':
 cases=read(R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5/full/scoring-only.json');entry=next(x for x in cases if x['meeting']=='L_R003S01C02');assert sha(entry['reference'])==entry['referenceSha256']
 journal=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results/L_R003S01C02/review.json';mapping={row['matchedAnonymousGroup'].removeprefix('speaker_'):name for name,row in read(journal)['perReferenceSpeakerForEvaluationOnly'].items()}
 rows=[dict(row,lexical=re.sub(r'<[^>]*>','',row['text']).strip(),crossesAudioBoundary=row['start']<1560 or row['end']>1590) for row in read_reference_intervals(entry['reference']) if row['start']<1590 and row['end']>1560 and normalize(row['text'])]
 active={row['speaker'] for row in rows};scoring={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'reference':entry['reference'],'referenceSha256':entry['referenceSha256'],'nativeMapping':mapping,'mappingForScoringOnly':True,'mappingSourceSha256':sha(journal),'audioOnlyInputsAlreadyFrozenSha256':sha(C/'audio-only-inputs.json'),'sourceWindow':[1560,1590],'rows':rows,'trulyAbsentNativePeople':[int(i) for i,name in mapping.items() if name not in active],'correction':'Native0 alone has no lexical reference speech in this30s. Native4/5 eachactuallyspeak, so doNOT callthem negative/no-speech controls. Oldrapid-r3prepared description guessedabsent0/4/5; preservedasoldassumption, correctedbefore newqualityjudgment. No modelinput/targetselection changed.','crossingWordPolicy':'Do notcroporassignpartialutterancecharactersbyduration. Full30s targetCERonlyifallintersectingreferenceutterancesforthatpersonarefullyinside. Otherwise showraw+boundaryrowsbutnoformalCER. Allpersonsincludedinscore; nativeidentity mapfrozenfromexistingfulljournal evaluation, nooracleinput.'};write(C/'scoring-only.json',scoring);print(json.dumps({'state':'SCORING_ONLY_PREPARED','trulyAbsentNativePeople':scoring['trulyAbsentNativePeople'],'boundaryByNative':{i:sum(r['crossesAudioBoundary'] for r in rows if r['speaker']==name) for i,name in mapping.items()}},ensure_ascii=False))
else:
 folder=Path(a.control);job=read(folder/'audio-only.json');raw=read(folder/'raw.json');scoring=read(C/'scoring-only.json');assert sha(C/'audio-only-inputs.json')==scoring['audioOnlyInputsAlreadyFrozenSha256'];native=str(job['nativePerson']);reference=[r for r in scoring['rows'] if r['speaker']==scoring['nativeMapping'][native]];boundary=any(r['crossesAudioBoundary'] for r in reference);hyp=normalize(raw['text']);ref=''.join(normalize(r['text']) for r in sorted(reference,key=lambda r:(r['start'],r['end'])));counts={'replace':0,'delete':0,'insert':0};metric=None
 if not boundary:
  for edit in Levenshtein.editops(ref,hyp):counts[edit.tag]+=1
  metric={'metric':'StrictCER_fixed30s_one_native_target_not_whole_meeting','referenceCharacters':len(ref),'edits':counts,'totalEdits':sum(counts.values()),'characterErrorRate':sum(counts.values())/len(ref) if ref else None,'noSpeechFalseInsertionCharacters':len(hyp) if not ref else None,'noTraditionalSimplifiedOrSemanticRewrite':True}
 out={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'REAL_TARGET_DIAGNOSTIC_SCORED_NOT_QUALIFIED','nativePerson':int(native),'referenceSpeakerForEvaluationOnly':scoring['nativeMapping'][native],'sourceWindow':[1560,1590],'rawText':raw['text'],'naturalEos':raw['naturalEos'],'loop':raw['loop'],'referenceUtterances':reference,'strictTargetCer':metric,'strictCerOmittedForCrossingUtterance':boundary,'rawSha256':sha(folder/'raw.json'),'referenceSha256':scoring['referenceSha256'],'timeSeconds':raw['seconds'],'smallSampleNotWholeMeetingQualification':True,'referencePassedToInference':False,'saleQualified':False};write(folder/'review.json',out);print(json.dumps(out,ensure_ascii=False,indent=2))
