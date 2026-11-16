"""One source/PCM/label integrity pass. This does not run or evaluate a model."""
from pathlib import Path
from datetime import datetime
import collections,hashlib,json,sys,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/meeting-domain-data-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
results=[]
for directory,count,multi in [('stageA',190,True),('acoustic-nonoverlap-r2',944,False)]:
 root=E/directory;state=read(root/'run.json');rows=read(root/'example-provenance.json');train=[json.loads(x) for x in (root/'train.jsonl').read_text(encoding='utf-8').splitlines()]
 assert state['finishedAt'] and not state['failures'] and len(rows)==len(train)==count and sha(root/'train.jsonl')==state['trainJsonlSha256']
 by_source=collections.defaultdict(list);languages=collections.Counter();seconds=collections.Counter();event_ids=set()
 for row,line in zip(rows,train):
  assert row['role']=='train-only' and not row['referenceOverlapPresent'] and not row['labelWordsEdited'] and not row['addedNoise'] and not row['resampled']
  assert row['meeting'] not in ['ES2003b','EN2001a','EN2002a','S_R004S03C01','20200623_S_R001S07C01','20200709_L_R002S01C01','20200805_S_R001S02C01'] and 'L_R003' not in row['meeting']
  assert line=={'audio':row['audio'],'text':'language '+row['language']+'<asr_text>'+row['text']}
  expected=(' ' if row['language']=='English' else '').join(x['text'] for x in row['events']);assert row['text']==expected
  if multi:assert len(row['localSpeakerIds'])>=2
  assert sha(row['audio'])==row['audioSha256'];frames=row['endFrame']-row['startFrame'];assert 0<frames<=30*16000
  with wave.open(row['audio'],'rb') as f:
   assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())==(1,2,16000,frames);pcm=f.readframes(frames)
  assert hashlib.sha256(pcm).hexdigest()==row['pcmSha256']
  with wave.open(row['sourceAudio'],'rb') as f:f.setpos(row['startFrame']);assert f.readframes(frames)==pcm
  for event in row['events']:
   assert row['startFrame']/16000<=event['start'] and event['end']<=row['endFrame']/16000
   event_ids.update((row['meeting'],event['speaker'],i) for i in event['sourceIndices'])
  by_source[row['sourceAudio']].append(row);languages[row['language']]+=1;seconds[row['language']]+=frames/16000
 for source,items in by_source.items():
  assert sha(source)==items[0]['sourceAudioSha256'];ordered=sorted(items,key=lambda x:x['startFrame'])
  assert all(a['endFrame']<=b['startFrame'] for a,b in zip(ordered,ordered[1:])),source
 result={'directory':directory,'examples':len(rows),'meetings':len(by_source),'languageExamples':dict(languages),'languageAudioSeconds':dict(seconds),'trainJsonlSha256':sha(root/'train.jsonl'),
  'exactOriginalPcmFrameSlicesVerified':True,'everySelectedLabelCharacterPreserved':True,'noWithinSourceDuplicateFrames':True,'sourceExclusionsVerified':True,'referenceEventCount':len(event_ids)}
 results.append((result,event_ids))
strict,broad=results[0][1],results[1][1]
output={'state':'PASS_PUBLIC_TRAINING_EXPORT_PCM_LABEL_AND_SOURCE_INTEGRITY_NOT_A_MODEL_RESULT','at':datetime.now().astimezone().isoformat(),'exports':[r[0] for r in results],
 'strictStageAEventsAlsoInBroadAcoustic':len(strict&broad),'strictStageAEventsMissingInBroadAcoustic':len(strict-broad),'distinctCoverageByExportRetained':True,
 'chineseGlobalParticipantDisjointnessVerified':False,'modelTrainingReady':False,'trainingStarted':False,'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
atomic_json(C/'export-integrity.json',output);print(json.dumps(output,ensure_ascii=False))
