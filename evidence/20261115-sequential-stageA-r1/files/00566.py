"""Fix omitted fifth AMI speaker using official metadata, without relabelling.

Retain invalid r1 cohort/scores. Reuse26 exact unaffected audio results; select
six new English windows using corrected annotations only, not output scores.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,os,shutil,sys,wave,zipfile
import xml.etree.ElementTree as ET
from prepare_sequential_meetings_20261115 import plans,ami_rows
import soundfile as sf
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
R1=D/'sequential-meeting-stageA-r1';C=D/'sequential-meeting-stageA-r2'
ER1=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r1')
E=ER1.with_name('sequential-meeting-stageA-r2')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def now():return datetime.now().astimezone().isoformat()
assert not C.exists() and not E.exists();C.mkdir();E.mkdir()
inventory=read(R1/'source-inventory.json');source=next(s for s in inventory['sources'] if s['meeting']=='EN2001a')
assert sha(source['audio'])==source['audioSha256']
with zipfile.ZipFile(source['annotationArchive']) as z:
 rows=ami_rows(z,'EN2001a');eligible,counts=plans(rows)
 meta=next(m for m in ET.fromstring(z.read('corpusResources/meetings.xml')) if m.attrib.get('observation')=='EN2001a')
 speakers=sorted(s.attrib['nxt_agent'] for s in meta if s.tag=='speaker');assert speakers==list('ABCDE')
 fifth=[r for r in rows if r['speaker']=='E'];assert len(fifth)>0
 files=[n for n in z.namelist() if n.startswith('words/EN2001a.') and n.endswith('.words.xml')]
 audit=[]
 for old in read(R1/'scoring-only.json'):
  if old['meeting']!='EN2001a':continue
  lo,hi=old['sourceStartFrame']/16000,old['sourceEndFrame']/16000
  missing=[r for r in fifth if r['start']<hi and r['end']>lo]
  all_inside=[r for r in rows if r['start']<hi and r['end']>lo]
  overlap=any(a['speaker']!=b['speaker'] and a['start']<b['end']-1e-9 and b['start']<a['end']-1e-9 for i,a in enumerate(all_inside) for b in all_inside[i+1:])
  crossing=[r for r in all_inside if r['start']<lo-1e-9 or r['end']>hi+1e-9]
  audit.append({'id':old['id'],'omittedSpeakerReferenceEvents':len(missing),'actualOverlapByAllOfficialSpeakers':overlap,'referenceBoundaryCrossings':len(crossing)})
write(R1/'reference-coverage-failure.json',{'state':'R1_ENGLISH_AGGREGATE_INVALID_WITHDRAWN_NOT_A_MODEL_SCORE',
 'at':now(),'rootCause':'New AMI reader hardcoded A-D and omitted E of five-person EN2001a. Audio/model outputs unchanged. Full official metadata and all matching word files are now required.',
 'originalInvalidScoreSha256':sha(R1/'raw-text-baseline.json'),'omittedSpeaker':'E','omittedEvents':len(fifth),
 'officialSpeakers':speakers,'wordFiles':files,'cases':audit,'manualReferenceEdits':False,
 'preserveAllOriginalInputsOutputsAndScores':True,'affected':'EN2001a scenario classification/reference completeness and aggregated English score; Chinese and ES2003b exact outputs unaffected.',
 'preparationFailuresBeforeNeural':['Initial clean scoring environment lacked soundfile.','First guessed praatio path absent; corrected to existing pinned scoring packages.','ASR r1 decoder output subdirectory absent; fixed before any model load or neural inference.'],
 'repair':'Metadata-discovered all-speaker references, corrected annotation-only uniform selection in same recording; reuse26 exact unaffected cases, run only six replacement audio inputs plus original numeric controls.'})
assert len(eligible)>=6
audio_only=[r for r in read(R1/'audio-only.json') if r['meeting']!='EN2001a']
scoring=[r for r in read(R1/'scoring-only.json') if r['meeting']!='EN2001a']
new=[];info=sf.info(source['audio']);assert info.channels==1 and info.samplerate==16000
with sf.SoundFile(source['audio']) as original:
 for index in [i*(len(eligible)-1)//5 for i in range(6)]:
  plan=eligible[index];start,end=plan['start'],plan['end'];part=plan['rows']
  prior=max((r['end'] for r in rows if r['end']<=start+1e-9),default=0.)
  following=min((r['start'] for r in rows if r['start']>=end-1e-9),default=info.frames/16000)
  low=max(0,math.ceil(start*16000)-1280,math.ceil((prior+start)*8000))
  high=min(info.frames,math.ceil(end*16000)+1280,math.ceil((end+following)*8000))
  assert 0<high-low<=480000
  assert not [r for r in rows if r not in part and math.ceil(r['start']*16000)<high and math.ceil(r['end']*16000)>low]
  assert len({r['speaker'] for r in part if r['text']})>=2
  assert not any(a['speaker']!=b['speaker'] and a['start']<b['end']-1e-9 and b['start']<a['end']-1e-9 for i,a in enumerate(part) for b in part[i+1:])
  original.seek(low);pcm=original.read(high-low,dtype='int16',always_2d=True)[:,0].astype('<i2',copy=False).tobytes()
  case_id='EN2001a-a2-'+str(index).zfill(3);target=E/'audio'/(case_id+'.wav');target.parent.mkdir(exist_ok=True)
  with wave.open(str(target),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
  with wave.open(str(target),'rb') as check:assert check.readframes(high-low)==pcm
  item={'id':case_id,'condition':'sequential-original-room','meeting':'EN2001a','wav':str(target),
   'wavSha256':sha(target),'pcmSha256':hashlib.sha256(pcm).hexdigest(),'frames':high-low,
   'audioSeconds':(high-low)/16000,'language':'English'}
  audio_only.append(item);new.append(item)
  scoring.append({**item,'role':'validation','corpus':'AMI','sourceStartFrame':low,'sourceEndFrame':high,
   'sourceAudioSha256':source['audioSha256'],'referenceEvents':part,'rawReferenceText':' '.join(r['text'] for r in part if r['text']),
   'speakers':plan['speakers'],'turns':plan['turns'],'speakerReturn':plan['speakerReturn'],
   'overlapPresentByReference':False,'eligiblePlanIndex':index,'addedNoise':False})
inventory['newAmiSelection']=read(R1/'source-inventory.json')['newAmiSelection']
inventory['correctedSourceCoverage']={'meeting':'EN2001a','officialSpeakers':speakers,'wordFiles':files,**counts}
inventory['at']=now();write(C/'source-inventory.json',inventory)
write(C/'audio-only.json',audio_only);write(C/'scoring-only.json',scoring)
P=read(R1/'protocol.json');P.update(at=now(),audioOnlyManifestSha256=sha(C/'audio-only.json'),
 scoringOnlyManifestSha256=sha(C/'scoring-only.json'),sourceInventorySha256=sha(C/'source-inventory.json'),
 totalSeconds=sum(r['audioSeconds'] for r in audio_only),speakerReturnCases=sum(r['speakerReturn'] for r in scoring),
 correctedReferenceCoverage='All official AMI metadata speakers, matching complete set of word XML files. EN2001a A-E; r1 A-D selection retained as invalid, not used for Stage-A conclusions.',
 reuseRule='26 byte-identical Chinese/ES2003b inputs, unchanged language/model/runtime binding; only six EN2001a replacements inferred.',
 previousInvalidCohort=str(R1),previousFailureSha256=sha(R1/'reference-coverage-failure.json'))
write(C/'protocol.json',P)
A=C/'new-asr';A.mkdir();shutil.copy2(R1/'numeric-control.json',A/'numeric-control.json')
write(A/'audio-only.json',new)
Q={**P,'cases':len(new),'audioOnlyManifestSha256':sha(A/'audio-only.json'),'scoringOnlyManifestSha256':None,
 'fullCorrectedCohortProtocol':str(C/'protocol.json'),'fullCorrectedCohortProtocolSha256':sha(C/'protocol.json')}
write(A/'protocol.json',Q)
b=read(R1/'asr-attempt-r2/worker-binding.json');b.update(protocolSha256=sha(A/'protocol.json'))
assert b['workerSha256']==sha(S/'sequential_meeting_asr_worker_20261115.py');write(A/'worker-binding.json',b)
old_state=read(ER1/'asr-r2/baseline-state.json');reuse=[r for r in old_state['completed'] if r['id'] in {c['id'] for c in audio_only if c['meeting']!='EN2001a'}]
assert len(reuse)==26
write(C/'reuse-results.json',{'sourceState':str(ER1/'asr-r2/baseline-state.json'),'sourceStateSha256':sha(ER1/'asr-r2/baseline-state.json'),'completed':reuse})
write(C/'repair-state.json',{'state':'FROZEN_R2_OFFICIAL_ALL_SPEAKER_COVERAGE_BEFORE_REPLACEMENT_INFERENCE',
 'newCases':len(new),'reusedCases':len(reuse),'originalCasesRetained':32,'speakerReturnCases':P['speakerReturnCases'],
 'correctedEligiblePlans':len(eligible),'referenceCoverageFailure':str(R1/'reference-coverage-failure.json'),
 'referenceLabelsManuallyEdited':False,'outputsConsultedForSelection':False})
print(json.dumps(read(C/'repair-state.json'),ensure_ascii=False))
