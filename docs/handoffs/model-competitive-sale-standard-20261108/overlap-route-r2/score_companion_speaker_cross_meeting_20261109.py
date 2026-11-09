"""Post-inference coverage-aware diagnostics; references never select input clips."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import collections,json,hashlib,sys,re
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109/automatic-cross-meeting-r2'
sys.path.insert(0,str(M/'src'))
from reference_textgrid_20261104 import read_reference_intervals
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
reference_cases=read(R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5/full/scoring-only.json')
cases=[]
for case in read(C/'predeclared-selection.json')['cases']:
 folder=Path(case['control']);I=read(folder/'selection-scoring-only.json');E=read(folder/'encoder-result.json');assert E['state']=='COMPLETE';native=read(Path(I['journal']).with_name('review.json'));entry=next(e for e in reference_cases if e['meeting']==case['meeting']);assert sha(entry['reference'])==entry['referenceSha256']
 mapping={row['matchedAnonymousGroup'].removeprefix('speaker_'):key for key,row in native['perReferenceSpeakerForEvaluationOnly'].items()};ref=[r for r in read_reference_intervals(entry['reference']) if re.sub(r'<[^>]*>','',r['text']).strip()]
 def truth(a,b):
  relevant=[r for r in ref if r['start']<b and r['end']>a];edges=sorted({a,b}|{max(a,r['start']) for r in relevant}|{min(b,r['end']) for r in relevant});speech=collections.Counter();exclusive=collections.Counter()
  for x,y in zip(edges,edges[1:]):
   active={r['speaker'] for r in relevant if r['start']<(x+y)/2<r['end']}
   for person in active:speech[person]+=y-x
   if len(active)==1:exclusive[next(iter(active))]+=y-x
  person=max(speech,key=speech.get) if speech else None
  return {'dominantReferenceForScoringOnly':person,'exclusiveDominantFraction':exclusive.get(person,0)/(b-a),'speechSeconds':dict(speech)}
 profiles=[]
 for row in I['profiles']:
  t=truth(row['start'],row['end']);profiles.append({'id':row['id'],'nativePerson':row['nativePerson'],'matchesExistingNativeMapping':mapping[row['nativePerson']]==t['dominantReferenceForScoringOnly'],**t})
 byid={r['id']:r for r in E['vectors'] if r['kind']=='queries'};rows=[]
 for q in I['queries']:
  result=byid[q['id']];expected=q['nativePerson'];prediction=result['predictedNativePerson'];t=truth(q['start'],q['end']);actual=t['dominantReferenceForScoringOnly'];agree=prediction==expected
  rows.append({'id':q['id'],'start':q['start'],'end':q['end'],'nativeJournalPerson':expected,'encoderPerson':prediction,'nativeJournalMatchesDominant':mapping[expected]==actual,'encoderMatchesDominant':mapping[prediction]==actual,'agreementOnlyPerson':expected if agree else None,'agreementIsNotVerifiedIdentity':True,'topTwoMargin':result['topTwoMargin'],**t})
 def counts(rows):
  n=len(rows);accepted=[r for r in rows if r['agreementOnlyPerson'] is not None]
  return {'queries':n,'nativeJournalMatchesDominant':sum(r['nativeJournalMatchesDominant'] for r in rows),'encoderMatchesDominant':sum(r['encoderMatchesDominant'] for r in rows),'agreementOnly':{'accepted':len(accepted),'unconfirmed':n-len(accepted),'acceptedDominantMatch':sum(r['nativeJournalMatchesDominant'] for r in accepted),'acceptedDominantMismatch':sum(not r['nativeJournalMatchesDominant'] for r in accepted),'dominantMatchingJournalLabelsWithheld':sum(r['nativeJournalMatchesDominant'] for r in rows if r['agreementOnlyPerson'] is None),'coverage':len(accepted)/n if n else None}}
 all_people=sorted({r['nativePerson'] for r in I['profiles']});perperson={p:counts([r for r in rows if r['nativeJournalPerson']==p]) for p in all_people};pure=[r for r in rows if r['exclusiveDominantFraction']>=.95]
 result={'meeting':case['meeting'],'audioSha256':I['source']['audioSha256'],'referenceSha256':entry['referenceSha256'],'nativeMappingSourceForEvaluationOnly':str(Path(I['journal']).with_name('review.json')),'profiles':len(profiles),'profileMatchesExistingNativeMapping':sum(r['matchesExistingNativeMapping'] for r in profiles),'profilePureAt95Percent':sum(r['exclusiveDominantFraction']>=.95 for r in profiles),'profileRows':profiles,'allSelectedQueries':counts(rows),'pureReferenceSubsetForDiagnosticOnly':counts(pure),'perAutomaticPerson':perperson,'peopleWithoutEligibleNewQueries':[p for p,v in perperson.items() if not v['queries']],'rows':rows,'elapsedSeconds':E['elapsedSeconds'],'limits':E['limits'],'scope':'Clip-level diagnostics only. Dominant identity is ambiguous in mixtures; allselected clips retained, pure subset is posthoc and not used to filter. Fullmeeting DER is separately retained, not recalculated from these clips. Existing fullnative assignment used only for scoring. Source meetings exposed earlier; pretraining overlap unknown.','thresholdOrWeightsChanged':False,'productDefaultChanged':False,'qualified':False}
 write(folder/'review.json',result);cases.append(result)
overall={'queries':sum(r['allSelectedQueries']['queries'] for r in cases),'nativeJournalMatchesDominant':sum(r['allSelectedQueries']['nativeJournalMatchesDominant'] for r in cases),'encoderMatchesDominant':sum(r['allSelectedQueries']['encoderMatchesDominant'] for r in cases),'agreementAccepted':sum(r['allSelectedQueries']['agreementOnly']['accepted'] for r in cases),'agreementDominantMismatch':sum(r['allSelectedQueries']['agreementOnly']['acceptedDominantMismatch'] for r in cases),'dominantMatchingJournalLabelsWithheld':sum(r['allSelectedQueries']['agreementOnly']['dominantMatchingJournalLabelsWithheld'] for r in cases),'elapsedSeconds':sum(r['elapsedSeconds'] for r in cases),'peakWorkerPrivateBytes':max(r['limits']['jobPeakPrivateCommitBytes'] for r in cases)}
write(C/'result.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'COMPLETE_FIXED_CROSS_MEETING_AUTOMATIC_IDENTITY_DIAGNOSTIC','overall':overall,'cases':[{k:r[k] for k in ['meeting','profiles','profilePureAt95Percent','profileMatchesExistingNativeMapping','allSelectedQueries','pureReferenceSubsetForDiagnosticOnly','peopleWithoutEligibleNewQueries','elapsedSeconds','limits']} for r in cases],'noNewDerOrAsrAccuracyClaim':True,'finalHoldoutOpened':False,'newTrainingOrModelDownloads':False,'productInstalledOrDefaultChanged':False,'saleQualified':False})
print(json.dumps({'overall':overall,'cases':[{k:r[k] for k in ['meeting','profiles','profilePureAt95Percent','allSelectedQueries','peopleWithoutEligibleNewQueries']} for r in cases]},ensure_ascii=False))
