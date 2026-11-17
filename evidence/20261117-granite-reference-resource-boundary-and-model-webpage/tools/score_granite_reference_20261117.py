"""Independent scoring of the unchanged12 English inputs and original references."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone,timedelta
import argparse, hashlib, json, sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from score_sequential_meetings_20261115 import measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
ap=argparse.ArgumentParser();ap.add_argument('--protocol',type=Path,required=True);a=ap.parse_args()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(a.protocol);C=a.protocol.parent;run=Path(P['run']);state=read(run/'completed.json')
assert state['state']=='COMPLETE_NATIVE_GRANITE_12_CLIPS_PENDING_INDEPENDENT_SCORE'
assert len(state['completed'])==12 and not state['referenceRead'] and state['newTrainingUpdates']==0
assert not state['gpuInitialized'] and state['protocolSha256']==sha(a.protocol)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
B=read(J/'english-transducer-r1/scoring-control.json')
for f in B['files']:assert sha(f['file'])==f['sha256']
refs={x['id']:x for x in read(B['references'])}
tdt=read(J/'english-transducer-r1/score.json')
baseline={x['id']:x for x in read(B['mossBaseline'])['cases']}
audio={x['id']:x for x in P['cases']};rows=[];groups=defaultdict(list)
for entry in state['completed']:
 assert sha(entry['file'])==entry['sha256'];v=read(entry['file']);c=refs[v['id']];original=audio[v['id']]
 assert c['role']=='validation' and c['language']=='English'
 assert v['naturalTermination'] and not v['referenceUsed'] and not v['wordsPostEdited']
 assert v['protocolSha256']==sha(a.protocol) and v['audioSha256']==original['audioSha256']
 assert v['pcmSha256']==c['pcmSha256']==original['pcmSha256'] and v['frames']==c['frames']==original['frames']
 score=measure(c['rawReferenceText'],v['text'],'English')
 assert score['referenceUnits']==baseline[v['id']]['raw']['referenceUnits']
 row={'id':v['id'],'meeting':c['meeting'],**score,'seconds':v['seconds']}
 rows.append(row);groups[c['meeting']].append(row)
def total(xs):
 n=sum(x['referenceUnits'] for x in xs);e=sum(x['errors'] for x in xs)
 return {'cases':len(xs),'referenceUnits':n,'errors':e,'errorRate':e/n,
  **{k:sum(x[k] for x in xs) for k in ['substitutions','deletions','insertions','seconds']}}
meetings=[]
for name,items in groups.items():
 moss=sum(x['raw']['errors'] for x in baseline.values() if x['id'] in audio and x['meeting']==name)
 parakeet=next(x['errors'] for x in tdt['meetings'] if x['meeting']==name)
 meetings.append({'meeting':name,**total(items),'bestPriorMeetingErrors':min(moss,parakeet)})
aggregate=total(rows);assert aggregate['referenceUnits']==709
advance=aggregate['errors']<=P['gate']['maximumEnglishErrors'] and all(x['errors']<=x['bestPriorMeetingErrors'] for x in meetings)
result={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
 'state':'PASS_FIXED_NATIVE_GRANITE_ADMISSION_WHOLE_MEETINGS_PENDING' if advance else 'REJECT_FIXED_NATIVE_GRANITE_ADMISSION_NO_GRID',
 'aggregate':aggregate,'meetings':meetings,'cases':rows,'advanceToWholeEnglish':advance,
 'gate':P['gate'],'bestPriorErrors':123,'relativeReductionVsBestPrior':(123-aggregate['errors'])/123,
 'originalReferencesAndAudioUnchanged':True,'originalScorerSha256':sha(S/'score_sequential_meetings_20261115.py'),
 'scorerSha256':sha(__file__),'protocolSha256':sha(a.protocol),'completedInferenceSha256':sha(run/'completed.json'),
 'newInferenceByScorer':0,'newTrainingUpdates':0,'finalHoldoutOpened':False,
 'wholeMeetingAndPerPersonQualified':False,'qualityQualified':False,'saleQualified':False,
 'next':'Original whole English sources with exactly this profile; no training or product promotion yet.' if advance else 'Retain and end this fixed reference; no automatic decoder/precision/model grid.'}
assert not (C/'score.json').exists();atomic_json(C/'score.json',result)
print(json.dumps({k:result[k] for k in ['state','aggregate','meetings','advanceToWholeEnglish','relativeReductionVsBestPrior']},ensure_ascii=False))
