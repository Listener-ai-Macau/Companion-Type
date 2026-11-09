from pathlib import Path
import collections,hashlib,json,math,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109'
sys.path.insert(0,str(M/'src'))
from reference_textgrid_20261104 import read_reference_intervals
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
result=read(C/'encoder-result.json');assert result['state']=='COMPLETE'
plan=read(C/'selection-scoring-only.json');review=read(plan['profileReviewForScoringOnly'])
mapping={k:v['referenceIdentitiesForScoringOnly'][0] for k,v in review['perPerson'].items()}
refpath=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/L_R003S01C02.TextGrid');assert hashlib.sha256(refpath.read_bytes()).hexdigest()=='a7e060c87f76f6ad51ca1bcd6ae7243942757f25bdcbfc9a628c552d03dcbc4c'
reference=[r for r in read_reference_intervals(refpath) if r['text'].strip()]
def coverage(a,b):
 rows=[r for r in reference if r['start']<b and r['end']>a]
 edges=sorted({a,b}|{max(a,r['start']) for r in rows}|{min(b,r['end']) for r in rows});exclusive=collections.defaultdict(float);speech=collections.defaultdict(float)
 for x,y in zip(edges,edges[1:]):
  active={r['speaker'] for r in rows if r['start']<(x+y)/2<r['end']}
  for person in active:speech[person]+=y-x
  if len(active)==1:exclusive[next(iter(active))]+=y-x
 dominant=max(speech,key=speech.get) if speech else None
 return dominant,exclusive.get(dominant,0)/(b-a),dict(speech)
byid={r['id']:r for r in result['vectors']};rows=[]
for q in plan['queries']:
 r=byid[q['id']];dominant,purity,speech=coverage(q['start'],q['end']);expected=q['expectedNativePersonForScoringOnly'];actual=mapping[r['predictedNativePerson']]
 rows.append({'id':q['id'],'start':q['start'],'end':q['end'],'seconds':q['end']-q['start'],'automaticJournalPerson':expected,'encoderPerson':r['predictedNativePerson'],'agreesWithAutomaticJournal':expected==r['predictedNativePerson'],'predictedReferenceIdentityForScoringOnly':actual,'dominantReferenceIdentityForScoringOnly':dominant,'exclusiveDominantReferenceCoverage':purity,'referenceSpeechSeconds':speech,'matchesDominantReference':actual==dominant,'cosineByPerson':r['cosineByPerson'],'topTwoMargin':r['topTwoMargin']})
cal=next(r for r in result['vectors'] if r['kind']=='calibration');old=next(r for r in read(plan['calibrationVectorSource'])['vectors'] if r['audioSha256']==cal['audioSha256'])
x,y=cal['vector'],old['vector'];cos=sum(a*b for a,b in zip(x,y))/math.sqrt(sum(a*a for a in x)*sum(b*b for b in y));delta=max(abs(a-b) for a,b in zip(x,y))
groups={p:[r for r in rows if r['automaticJournalPerson']==p] for p in sorted(mapping)}
out={'state':'COMPLETE_AUTOMATIC_PROFILE_ENCODER_DIAGNOSTIC','queries':len(rows),'automaticJournalAgreementCount':sum(r['agreesWithAutomaticJournal'] for r in rows),'dominantReferenceMatchCount':sum(r['matchesDominantReference'] for r in rows),'referencePureQueryCountAt95Percent':sum(r['exclusiveDominantReferenceCoverage']>=.95 for r in rows),'perAutomaticPerson':{p:{'queries':len(g),'journalAgreements':sum(r['agreesWithAutomaticJournal'] for r in g),'dominantReferenceMatches':sum(r['matchesDominantReference'] for r in g)} for p,g in groups.items()},'calibration':{'sameAudioSha256':cal['audioSha256'],'cpuVsPreviousGpuCosine':cos,'maximumAbsoluteVectorDifference':delta,'bitExactClaimed':False},'rows':rows,'elapsedSeconds':result['elapsedSeconds'],'limits':result['limits'],'weightsChanged':False,'referencePassedToInference':False,'scope':'22automatic-solo clips, everyselected retained, no reference selection. Actual identity scoring is posthoc using profiles dominant mapping. Same exposed meeting and author pretraining overlap unknown. Not DER, overlap word accuracy or independent heldout.','overlapContentRecoveredMeasured':False,'saleQualified':False}
write(C/'encoder-review.json',out)
print(json.dumps({k:out[k] for k in ('queries','automaticJournalAgreementCount','dominantReferenceMatchCount','referencePureQueryCountAt95Percent','perAutomaticPerson','calibration')},ensure_ascii=False))
