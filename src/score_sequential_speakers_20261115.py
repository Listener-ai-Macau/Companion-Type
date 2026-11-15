"""Frozen meeting-level identities, exact-duration DER, raw recognized words.

Gold is available only to this CPU scorer. No per-window remapping, no missing
word deletion, and no unknown-speaker stream optimally reassigned to a person.
"""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,math,os,sys,zipfile
import xml.etree.ElementTree as ET
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
import numpy as np
from scipy.optimize import linear_sum_assignment
from score_sequential_meetings_20261115 import tokens,measure
from reference_textgrid_20261104 import read_reference_intervals
from companion_exclusive_journal_20261114 import exclusive_journal
from practical_transcript_20261107 import onset_attribution
from ami_reference_coverage_20261115 import official_speakers
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 def numeric(value):
  if isinstance(value,np.generic):return value.item()
  raise TypeError(type(value).__name__)
 payload=json.dumps(x,ensure_ascii=False,indent=2,default=numeric)+'\n'
 with p.open('x',encoding='utf-8') as f:f.write(payload);f.flush();os.fsync(f.fileno())
def intervals(active,seconds):
 result=[]
 for speaker in range(active.shape[1]):
  edges=np.diff(np.r_[0,active[:,speaker],0].astype(np.int8))
  for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
   if a/100<seconds:result.append({'start':a/100,'end':min(b/100,seconds),'speaker':speaker})
 return sorted(result,key=lambda r:(r['start'],r['end'],r['speaker']))
def overlap_seconds(a,b):
 # Both lists for one identity; intervals in each already disjoint.
 total=0.;i=j=0
 while i<len(a) and j<len(b):
  total+=max(0.,min(a[i]['end'],b[j]['end'])-max(a[i]['start'],b[j]['start']))
  if a[i]['end']<b[j]['end']:i+=1
  else:j+=1
 return total
def union(rows):
 out=[]
 for row in sorted(rows,key=lambda r:(r['start'],r['end'])):
  if out and row['start']<=out[-1]['end']:out[-1]['end']=max(out[-1]['end'],row['end'])
  else:out.append(dict(row))
 return out
def ami_words(archive,meeting):
 rows=[]
 with zipfile.ZipFile(archive) as z:
  speakers=official_speakers(z,meeting)
  for speaker in speakers:
   for n in ET.fromstring(z.read(f'words/{meeting}.{speaker}.words.xml')):
    if n.tag!='w' or n.attrib.get('punc')=='true' or 'starttime' not in n.attrib or 'endtime' not in n.attrib:continue
    start,end=float(n.attrib['starttime']),float(n.attrib['endtime']);text=''.join(n.itertext()).strip()
    if text and end>start:rows.append({'start':start,'end':end,'speaker':speaker,'text':text})
 return rows
def mapping(reference,hypothesis):
 speakers=sorted({r['speaker'] for r in reference});matrix=np.zeros((8,len(speakers)))
 for i in range(8):
  for j,s in enumerate(speakers):matrix[i,j]=overlap_seconds([r for r in hypothesis if r['speaker']==i],union([r for r in reference if r['speaker']==s]))
 a,b=linear_sum_assignment(-matrix)
 return {int(i):speakers[j] for i,j in zip(a,b)},matrix.tolist()
def der(reference,hypothesis,low,high,identity):
 events=defaultdict(list)
 for kind,rows in [('r',reference),('h',hypothesis)]:
  for row in rows:
   a,b=max(low,row['start']),min(high,row['end'])
   if a>=b:continue
   s=row['speaker'] if kind=='r' else identity.get(row['speaker'],'unmapped-'+str(row['speaker']))
   events[a].append((kind,s,1));events[b].append((kind,s,-1))
 events[low];events[high];active={'r':defaultdict(int),'h':defaultdict(int)}
 result={'referenceSpeakerSeconds':0.,'missSeconds':0.,'falseAlarmSeconds':0.,'confusionSeconds':0.}
 times=sorted(events)
 for a,b in zip(times,times[1:]):
  for kind,s,delta in events[a]:active[kind][s]+=delta
  r={s for s,n in active['r'].items() if n};h={s for s,n in active['h'].items() if n};dt=b-a
  result['referenceSpeakerSeconds']+=len(r)*dt
  result['missSeconds']+=max(0,len(r)-len(h))*dt;result['falseAlarmSeconds']+=max(0,len(h)-len(r))*dt
  result['confusionSeconds']+=(min(len(r),len(h))-len(r&h))*dt
 result['errorSeconds']=sum(result[k] for k in ['missSeconds','falseAlarmSeconds','confusionSeconds'])
 result['DER']=result['errorSeconds']/result['referenceSpeakerSeconds'] if result['referenceSpeakerSeconds'] else None
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
 S=Path(__file__).parent;D=a.control.parent
 inventory=read(a.control/'source-inventory.json');cases=read(a.control/'scoring-only.json')
 baseline=read(a.root/'asr-r2/baseline-state.json');assert baseline['state']=='COMPLETE_STAGE_A_RAW_ASR_UNQUALIFIED'
 alignment=a.root/'align-r1';assert read(alignment/'full-state.json')['state']=='COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED'
 aligned={r['meeting']:r for r in read(alignment/'audio-text-only.json')}
 original=read(D/'supervised-blind-separation-r1/single-source-activity-guard-r1/baseline-bindings.json')
 en=read(a.root/'speaker-r1/speaker-state.json');assert en['state']=='COMPLETE_STAGE_A_ORIGINAL_WHOLE_SPEAKER_UNQUALIFIED'
 for row in en['completed']:original[row['meeting']]={'file':row['probabilities'],'sha256':row['probabilitiesSha256']}
 train=read(a.root/'speaker-train-r1/speaker-state.json');assert train['state']=='COMPLETE_STAGE_A_ORIGINAL_WHOLE_SPEAKER_UNQUALIFIED'
 for row in train['completed']:original[row['meeting']]={'file':row['probabilities'],'sha256':row['probabilitiesSha256']}
 reports=[];identities=[];groups=defaultdict(list)
 for source in inventory['sources']:
  meeting=source['meeting'];bound=original[meeting];assert sha(bound['file'])==bound['sha256']
  data=np.load(bound['file'],allow_pickle=False);frames=len(data)
  active=np.zeros(data.shape,dtype=bool)
  for k in range(8):
   v=data[:,k];last=np.maximum.accumulate(np.where(v!=.5,np.arange(frames),-1));active[:,k]=(last>=0)&(v[np.maximum(last,0)]>.5)
  import soundfile as sf
  seconds=sf.info(source['audio']).frames/16000
  raw=intervals(active,seconds)
  journal={'segments':raw,'audioSeconds':seconds,'audioSha256':source['audioSha256']}
  exclusive,receipt=exclusive_journal(data,frames=frames,seconds_per_frame=.01,source_journal=journal)
  if source['language']=='Chinese':reference=[r for r in read_reference_intervals(source['reference']) if r['text'].strip()]
  else:reference=ami_words(source['annotationArchive'],meeting)
  reference=sorted(reference,key=lambda r:(r['start'],r['end'],r['speaker']))
  identity,matrix=mapping(reference,raw)
  identities.append({'meeting':meeting,'nativeToReference':identity,'fullMeetingOverlapMatrixSeconds':matrix,
   'probabilities':bound,'mappingScope':'One whole-meeting optimal activity mapping, fixed for all selected windows and both attribution views; scoring only.'})
  for case in [c for c in cases if c['meeting']==meeting]:
   plan=aligned[case['id']];doc=read(plan['sourceDocument']);low=case['sourceStartFrame']/16000;high=case['sourceEndFrame']/16000
   references=defaultdict(list)
   for r in case['referenceEvents']:
    if r['text']:references[r['speaker']].append(r['text'])
   ref_texts={k:(' ' if case['language']=='English' else '').join(v) for k,v in references.items()}
   row={'id':case['id'],'meeting':meeting,'language':case['language'],'role':case['role'],'speakerReturn':case['speakerReturn'],
    'rawDER':der(reference,raw,low,high,identity),'exclusiveDER':der(reference,exclusive['segments'],low,high,identity),'views':{}}
   for view,j in [('raw',journal),('exclusive',exclusive)]:
    pieces=defaultdict(list);trace=[];lexical=[]
    for leaf in plan['leaves']:
     payload=read(alignment/'aligned'/case['id']/(leaf['id']+'.json'))['payload']
     assert payload['originalText']==leaf['text'] and ''.join(u['text'] for u in payload['units'])==leaf['text']
     for unit in payload['units']:
      onset=low+leaf['startSample']/16000+unit['predictedStartSeconds']
      valid=0<=unit['predictedStartSeconds']<(leaf['endSample']-leaf['startSample'])/16000
      attribution=onset_attribution(onset,j['segments'],duration=seconds,margin=.06) if valid else {'speaker':None,'attribution':'invalid_original_onset'}
      native=attribution['speaker'];who=identity.get(native,'UNKNOWN') if native is not None else 'UNKNOWN'
      pieces[who].append(unit['text']);lexical.extend(tokens(unit['text'],case['language']))
      trace.append({'text':unit['text'],'estimatedWholeMeetingOnset':onset,'nativeSpeaker':native,'referenceMappedSpeaker':who,'attribution':attribution['attribution']})
    # Word splitting by the aligner must never change the lexical error units.
    expected=tokens(doc['text'],case['language']);assert lexical==expected,'Aligner split a lexical token; retain and fix CPU scorer before scoring'
    scores=[]
    for who in sorted(set(ref_texts)|set(pieces)):
     hyp=''.join(pieces[who]);ref=ref_texts.get(who,'');m=measure(ref,hyp,case['language'])
     scores.append({'speaker':who,'reference':ref,'hypothesis':hyp,**m})
    row['views'][view]={'errors':sum(r['errors'] for r in scores),'referenceUnits':sum(r['referenceUnits'] for r in scores),
     'unknownHypothesisUnits':len(tokens(''.join(pieces['UNKNOWN']),case['language'])),'perPerson':scores,'units':trace}
   reports.append(row);groups[(case['language'],case['role'])].append(row)
 totals=[]
 for (lang,role),rows in groups.items():
  group={'language':lang,'role':role,'cases':len(rows),'speakerReturnCases':sum(r['speakerReturn'] for r in rows),'views':{}}
  for view in ['raw','exclusive']:
   denom=sum(r['views'][view]['referenceUnits'] for r in rows);errors=sum(r['views'][view]['errors'] for r in rows)
   seconds=sum(r[view+'DER']['referenceSpeakerSeconds'] for r in rows);bad=sum(r[view+'DER']['errorSeconds'] for r in rows)
   group['views'][view]={'speakerAttributedErrors':errors,'referenceUnits':denom,'speakerAttributedErrorRate':errors/denom,
    'unknownHypothesisUnits':sum(r['views'][view]['unknownHypothesisUnits'] for r in rows),'DERZeroCollar':bad/seconds,
    'speakerAttributedGatePass':errors/denom<.05,'DERGatePass':bad/seconds<=.1}
  totals.append(group)
 write(a.control/'speaker-baseline.json',{'state':'STAGE_A_SPEAKER_BASELINE_SCORED_NOT_PRODUCT_QUALIFIED','scorerSourceSha256':sha(__file__),
  'protocolSha256':sha(a.control/'protocol.json'),'scoringManifestSha256':sha(a.control/'scoring-only.json'),
  'alignmentProtocolSha256':sha(alignment/'protocol.json'),'alignmentStateSha256':sha(alignment/'full-state.json'),'groups':totals,
  'meetingIdentities':identities,'cases':reports,'qualityQualified':False,'goldPassedToInference':False,
  'limitations':['ASR uses annotation-selected complete windows; speaker model uses full original recording.','AMI activity is based on forced-aligned manual word times.','Onset estimates and +/-60ms attribution are unchanged and not verified word durations.','Unknown and unmapped speaker words counted as errors, no per-window identity optimization.','Exclusive view is only for sequential attribution, not overlap DER acceptance.']})
 print(json.dumps({'groups':totals},ensure_ascii=False,default=lambda v:v.item()))
if __name__=='__main__':main()
