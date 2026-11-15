"""Independent CPU scoring: original references/gates, all native lexical output."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
import argparse,hashlib,json,math,os,re,sys,unicodedata,zipfile
import xml.etree.ElementTree as ET
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
from reference_textgrid_20261104 import read_reference_intervals
from ami_reference_coverage_20261115 import official_speakers
from score_ami_bilingual_20261115 import words
from rapidfuzz.distance import Levenshtein
import numpy as np
from scipy.optimize import linear_sum_assignment
R=Path(__file__).resolve().parent.parent.parent
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def chars(text):
 return ''.join(c for c in re.sub(r'<[^>]*>','',text) if not c.isspace() and not unicodedata.category(c).startswith(('P','S'))).lower()
def units(text,language):return words(text) if language=='English' else list(chars(text))
def measure(reference,hypothesis):
 ops=Levenshtein.editops(reference,hypothesis);counts=Counter(o.tag for o in ops)
 return {'referenceUnits':len(reference),'hypothesisUnits':len(hypothesis),'errors':len(ops),
  'errorRate':len(ops)/len(reference) if reference else None,
  'counts':{t:counts[t] for t in ['replace','delete','insert']}}
def rttm(path):
 rows=[]
 for line in Path(path).read_text(encoding='utf-8').splitlines():
  f=line.split()
  if not f:continue
  assert len(f)==10 and f[0]=='SPEAKER';start=float(f[3]);end=start+float(f[4])
  assert math.isfinite(start) and math.isfinite(end) and end>start
  rows.append({'start':start,'end':end,'speaker':f[7]})
 return rows
def union(rows):
 out=[]
 for row in sorted(rows,key=lambda r:(r['start'],r['end'])):
  if out and row['start']<=out[-1]['end']:out[-1]['end']=max(out[-1]['end'],row['end'])
  else:out.append(dict(row))
 return out
def intersect(a,b):
 total=0.;i=j=0
 while i<len(a) and j<len(b):
  total+=max(0.,min(a[i]['end'],b[j]['end'])-max(a[i]['start'],b[j]['start']))
  if a[i]['end']<b[j]['end']:i+=1
  else:j+=1
 return total
def activity_score(reference,hypothesis,duration,identity=None):
 # Same complete continuous-time zero-collar/overlap policy as retained scores.
 ref=sorted({r['speaker'] for r in reference});hyp=sorted({r['speaker'] for r in hypothesis})
 if identity is None:
  matrix=np.zeros((len(hyp),len(ref)))
  for i,h in enumerate(hyp):
   for j,r in enumerate(ref):matrix[i,j]=intersect(union([v for v in hypothesis if v['speaker']==h]),union([v for v in reference if v['speaker']==r]))
  a,b=linear_sum_assignment(-matrix);identity={hyp[i]:ref[j] for i,j in zip(a,b)}
 events=defaultdict(list)
 for side,rows in [('r',reference),('h',hypothesis)]:
  for row in rows:
   low,high=max(0.,row['start']),min(duration,row['end'])
   if high<=low:continue
   person=row['speaker'] if side=='r' else identity.get(row['speaker'],'UNMAPPED-'+row['speaker'])
   events[low].append((side,person,1));events[high].append((side,person,-1))
 events[0.];events[duration];active={'r':Counter(),'h':Counter()};times=sorted(events)
 out={'referenceSpeakerSeconds':0.,'missSeconds':0.,'falseAlarmSeconds':0.,'confusionSeconds':0.}
 for start,end in zip(times,times[1:]):
  for side,person,delta in events[start]:active[side][person]+=delta
  refset={s for s,n in active['r'].items() if n>0};hypset={s for s,n in active['h'].items() if n>0};dt=end-start
  out['referenceSpeakerSeconds']+=len(refset)*dt
  out['missSeconds']+=max(0,len(refset)-len(hypset))*dt;out['falseAlarmSeconds']+=max(0,len(hypset)-len(refset))*dt
  out['confusionSeconds']+=(min(len(refset),len(hypset))-len(refset&hypset))*dt
 out['errorSeconds']=sum(out[k] for k in ['missSeconds','falseAlarmSeconds','confusionSeconds'])
 out['DER']=out['errorSeconds']/out['referenceSpeakerSeconds'];out['identityForScoringOnly']=identity
 return out
def lexical_references(case):
 if case['language']=='Chinese':
  assert sha(case['lexicalReference'])==case['lexicalReferenceSha256']
  return sorted(read_reference_intervals(case['lexicalReference']),key=lambda r:(r['start'],r['end'],r['speaker']))
 rows=[]
 with zipfile.ZipFile(case['manualArchive']) as z:
  speakers=official_speakers(z,case['meeting'])
  for speaker in speakers:
   name='words/'+case['meeting']+'.'+speaker+'.words.xml';body=z.read(name)
   assert hashlib.sha256(body).hexdigest()==case['wordFileSha256'][speaker]
   for index,node in enumerate(ET.fromstring(body).iter('w')):
    text=''.join(node.itertext())
    if not words(text):continue
    start,end=float(node.attrib['starttime']),float(node.attrib['endtime'])
    assert 0<=start<=end<=case['audioSeconds']+.1
    rows.append({'start':start,'end':end,'speaker':speaker,'index':index,'text':text})
 return sorted(rows,key=lambda r:(r['start'],r['end'],r['speaker'],r['index']))
def parse_native(raw):
 pattern=re.compile(r'\[(\d+(?:\.\d+)?)\]\[S(\d+)\](.*?)\[(\d+(?:\.\d+)?)\]',re.S)
 rows=[];residual=[];last=0
 for m in pattern.finditer(raw):
  leftover=raw[last:m.start()]
  if leftover.strip():residual.append({'beforeSegment':len(rows),'text':leftover})
  rows.append({'start':float(m[1]),'end':float(m[4]),'speaker':'S'+m[2],'text':m[3]});last=m.end()
 tail=raw[last:]
 if tail.endswith('<|im_end|>'):tail=tail[:-len('<|im_end|>')]
 if tail.strip():residual.append({'beforeSegment':len(rows),'text':tail})
 # Residual lexical content is retained and forced unknown, never discarded.
 all_rows=[]
 for i in range(len(rows)+1):
  all_rows.extend({'speaker':None,'text':r['text'],'start':float('inf'),'end':float('inf')} for r in residual if r['beforeSegment']==i)
  if i<len(rows):all_rows.append(rows[i])
 return rows,all_rows,residual
def person_score(reference,hypothesis,language):
 refs=defaultdict(list);hyps=defaultdict(list);unknown=[]
 for row in reference:refs[row['speaker']].extend(units(row['text'],language))
 for row in sorted(hypothesis,key=lambda r:(r['start'],r['end'])):
  (unknown if row['speaker'] is None else hyps[row['speaker']]).extend(units(row['text'],language))
 rn,hn=sorted(refs),sorted(hyps);n=max(len(rn),len(hn));cost=np.zeros((n,n),dtype=np.int64)
 for i in range(n):
  for j in range(n):cost[i,j]=Levenshtein.distance(refs[rn[i]] if i<len(rn) else [],hyps[hn[j]] if j<len(hn) else [])
 rr,cc=linear_sum_assignment(cost);people=[];total=sum(map(len,refs.values()));errors=int(cost[rr,cc].sum())+len(unknown)
 for i,j in zip(rr,cc):
  left=refs[rn[i]] if i<len(rn) else [];right=hyps[hn[j]] if j<len(hn) else []
  people.append({'referenceSpeaker':rn[i] if i<len(rn) else None,'anonymousSpeaker':hn[j] if j<len(hn) else None,**measure(left,right)})
 return {'referenceUnits':total,'errors':errors,'errorRate':errors/total,'unknownUnitsForcedUnmatched':len(unknown),
  'perPerson':people,'mappingForScoringOnly':True,'oneWholeMeetingPermutation':True}
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
 p.add_argument('--meeting',required=True);p.add_argument('--baseline-only',action='store_true');a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
 manifest=read(a.control/'whole-scoring-only.json');case=next(r for r in manifest['cases'] if r['meeting']==a.meeting)
 assert sha(__file__)==manifest['scorerSha256']
 for file,digest in manifest['helpers'].items():assert sha(file)==digest
 reference=lexical_references(case);language=case['language']
 refunits=[v for row in reference for v in units(row['text'],language)]
 baseline=read(case['baselineTextFile']);assert sha(case['baselineTextFile'])==case['baselineTextSha256']
 baseline_text=baseline[case['baselineTextKey']]
 base=measure(refunits,units(baseline_text,language));assert base['errors']==case['expectedBaselineErrors'],(case['meeting'],base)
 assert base['referenceUnits']==case['expectedReferenceUnits']
 result={'at':datetime.now().astimezone().isoformat(),'meeting':a.meeting,'language':language,
  'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],'baselineRawText':base,
  'baselinePersonErrorRate':case.get('baselinePersonErrorRate'),'baselineDER':case['baselineDER'],
  'baselineEvidence':case['baselineEvidence'],'scoringManifestSha256':sha(a.control/'whole-scoring-only.json'),
  'scorerSha256':sha(__file__),'qualityQualified':False,'saleQualified':False,'originalGatesChanged':False,
  'recordingsArePreviouslySeenDevelopmentCasesNotBlindHoldout':True,'newNeuralCalls':0}
 if not a.baseline_only:
  file=a.run/(a.meeting+'-raw.json');packet=read(file)
  assert packet['naturalEos'] and packet['completeOriginalRecordingInput']
  assert packet['audioSha256']==case['audioSha256'] and packet['audioSeconds']==case['audioSeconds']
  rows,all_rows,residual=parse_native(packet['rawDecoded'])
  hypunits=[v for row in all_rows for v in units(row['text'],language)]
  raw=measure(refunits,hypunits);person=person_score(reference,all_rows,language)
  bad=[i for i,r in enumerate(rows) if not 0<=r['start']<r['end']<=case['audioSeconds']]
  positive=[r for r in rows if r['start']<r['end']]
  activity=read(case['activityReference']) if case['activityKind']=='json' else rttm(case['activityReference'])
  assert sha(case['activityReference'])==case['activityReferenceSha256']
  der=activity_score(activity,positive,case['audioSeconds'])
  result.update(state='COMPLETE_JOINT_WHOLE_MEETING_SCORED_NOT_PRODUCT_QUALIFIED',candidateOutputSha256=sha(file),
   rawText=raw,personText=person,originalReferenceDER=der,invalidTimeSegmentIndices=bad,
   residualUnparsed= residual,allNativeLexicalContentCounted=True,parsedSegments=len(rows),
   rawTextGate=raw['errorRate']<.05,personTextGate=person['errorRate']<.05,
   derGate=der['DER']<=.1 and not bad,rawEditsReduced=base['errors']-raw['errors'],
   rawRelativeErrorReduction=(base['errors']-raw['errors'])/base['errors'])
  if case.get('mfaReference'):
   assert sha(case['mfaReference'])==case['mfaReferenceSha256'];alternate=rttm(case['mfaReference'])
   names=case.get('mfaToOriginalNames',{})
   for row in alternate:row['speaker']=names.get(row['speaker'],row['speaker'])
   result['externalMfaTimingDiagnostic']=activity_score(alternate,positive,case['audioSeconds'],identity=der['identityForScoringOnly'])
   result['externalMfaTimingDiagnostic']['notHumanVerifiedAndDoesNotReplaceOriginalGate']=True
 else:result['state']='PASS_ORIGINAL_BASELINE_FULL_TEXT_REPRODUCED_ZERO_NEW_INFERENCE'
 result['limits']=limits.query()
 target=a.control/('baseline-control-' if a.baseline_only else 'score-')
 target=a.control/(('baseline-control-' if a.baseline_only else 'score-')+a.meeting+'.json')
 assert not target.exists();atomic_json(target,result)
 print(json.dumps({k:result[k] for k in ['state','meeting','baselineRawText','rawText','personText','originalReferenceDER'] if k in result},ensure_ascii=False))
if __name__=='__main__':main()
