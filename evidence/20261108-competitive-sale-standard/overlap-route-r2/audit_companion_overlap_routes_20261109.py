"""Locate real full-meeting routing errors without thresholds or new inference."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter,defaultdict
import hashlib,json,sys,re
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109/automatic-cross-meeting-r2'
sys.path.insert(0,str(M/'src'))
from reference_textgrid_20261104 import read_reference_intervals
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sourcecases=read(R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5/full/scoring-only.json');reviews=[]
for case in read(C/'predeclared-selection.json')['cases']:
 folder=Path(case['control']);plan=read(folder/'selection-scoring-only.json');source=next(c for c in sourcecases if c['meeting']==case['meeting']);assert sha(source['reference'])==source['referenceSha256'];ref=[r for r in read_reference_intervals(source['reference']) if re.sub(r'<[^>]*>','',r['text']).strip()];journal=read(plan['journal']);events=defaultdict(lambda:defaultdict(Counter));duration=source['audioSeconds'];events[0];events[duration]
 for side,rows in [('reference',ref),('predicted',journal['segments'])]:
  for row in rows:
   a,b=row['start'],row['end'];assert 0<=a<b<=duration+1e-6
   person=str(row['speaker']);events[a][side][person]+=1;events[b][side][person]-=1
 active={'reference':Counter(),'predicted':Counter()};totals=Counter();bytrue=defaultdict(Counter);spans=[];edges=sorted(events)
 for a,b in zip(edges,edges[1:]):
  for side in active:active[side].update(events[a].get(side,{}))
  nr=sum(v>0 for v in active['reference'].values());np=sum(v>0 for v in active['predicted'].values());seconds=b-a
  state='caught_overlap' if nr>=2 and np>=2 else 'missed_overlap' if nr>=2 else 'false_overlap_solo' if nr==1 and np>=2 else 'false_overlap_no_reference' if nr==0 and np>=2 else 'ordinary_or_no_reference'
  totals[state]+=seconds
  if nr>=2:bytrue[str(nr)]['totalSeconds']+=seconds;bytrue[str(nr)]['caughtSeconds' if np>=2 else 'missedSeconds']+=seconds
  if state=='missed_overlap':
   row={'start':a,'end':b,'referencePeopleForScoringOnly':sorted(k for k,v in active['reference'].items() if v>0),'predictedPeople':sorted(k for k,v in active['predicted'].items() if v>0)}
   if spans and spans[-1]['referencePeopleForScoringOnly']==row['referencePeopleForScoringOnly'] and spans[-1]['predictedPeople']==row['predictedPeople'] and spans[-1]['end']==a:spans[-1]['end']=b
   else:spans.append(row)
 assert abs(sum(totals.values())-duration)<1e-6
 true=totals['caught_overlap']+totals['missed_overlap'];pred=totals['caught_overlap']+totals['false_overlap_solo']+totals['false_overlap_no_reference']
 previous=read(Path(plan['journal']).with_name('overlap-breakdown.json'));assert abs(true-previous['regions']['twoOrMore']['audioRegionSeconds'])<1e-6,'Must reproduce original reference scope before adding routing metric'
 result={'meeting':case['meeting'],'audioSeconds':duration,'audioSha256':source['audioSha256'],'referenceSha256':source['referenceSha256'],'journalSha256':sha(plan['journal']),'countsAreUniqueActivePeopleNotDuplicateSegments':True,'timing':'Continuous exact source times, zero collar, includes overlaps, no dilation/gap repair or threshold tuning. Existing lexical policy: remove source angle tags and require nonempty remaining text, as canonical original overlap breakdown.','originalOverlapReferenceSecondsReproduced':True,'seconds':dict(totals),'trueOverlapSeconds':true,'predictedOverlapSeconds':pred,'overlapDetectionRecall':totals['caught_overlap']/true if true else None,'overlapDetectionPrecision':totals['caught_overlap']/pred if pred else None,'missedOverlapByReferencePeople':{k:dict(v) for k,v in bytrue.items()},'missedOverlapSpans':spans,'newModelInference':False,'newDerOrWordCer':False,'saleQualified':False};write(folder/'full-overlap-routing-review.json',result);reviews.append({k:result[k] for k in ['meeting','audioSeconds','trueOverlapSeconds','predictedOverlapSeconds','overlapDetectionRecall','overlapDetectionPrecision','seconds','missedOverlapByReferencePeople']})
write(C/'full-overlap-routing-review.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'meetings':reviews,'scope':'Routing activity diagnostic only, not word recovery or diarization DER. Original fullmeeting references and cached predictions; no new model/threshold/answer-based runtime change.','criticalConsequence':'A journal-solo region can be genuinely overlapping even if a separate encoder agrees on its loudest identity. Speaker agreement must not be treated as proof of no overlap.','saleQualified':False})
print(json.dumps(reviews,ensure_ascii=False))
