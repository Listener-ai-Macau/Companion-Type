"""Training-only natural sequential multi-person examples from complete public sources."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
import ctypes,hashlib,json,math,re,sys,time,unicodedata,wave,xml.etree.ElementTree as X,zipfile,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from ami_reference_coverage_20261115 import official_speakers
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'joint-architecture-r1/meeting-domain-data-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
plan=read(C/'plan.json');sourceplan={r['meeting']:r for r in plan['sources']};data=read(E/'run.json')
assert data.get('finishedAt') and len(data['completed'])>=20
assert psutil.disk_usage('E:/').free>plan['minimumDiskFreeBytes']
OUT=E/'acoustic-nonoverlap';assert not OUT.exists();OUT.mkdir()
protocol={'state':'FROZEN_TRAINING_ONLY_BROAD_ACOUSTIC_NONOVERLAP_EXPORT','at':datetime.now().astimezone().isoformat(),
 'planSha256':sha(C/'plan.json'),'dataRunSha256':sha(E/'run.json'),'sourceSha256':sha(__file__),
 'selection':'Greedy adjacent complete lexical event clusters,2-30s,at least1 speaker; includes ordinary single-person acoustic training as well as the separately retained strict multi-person StageA cohort,no reference overlap; flush at overlap/unclear event or gaps>3s. Annotation boundaries are training supervision only; existing validation/final inputs and scoring remain unchanged.',
 'contextPaddingSeconds':.1,'references':'Original complete AMI word XML and frozen count-validated AISHELL TextGrid reader. Empty/nonlexical/unclear labels are retained in source metadata; unclear intervals exclude a training window instead of inventing words.',
 'wordHandling':'All selected original words, fillers, repetitions, partial words and numbers kept. English words separated by spaces; Chinese labels concatenated without lexical normalization.',
 'trainingFormat':'Official Qwen audio/text JSONL,language prefix. No model trained by export; raw full source events retained for later overlap/person supervision.',
 'originalValidationAndFinalHoldoutsUsed':False,'chineseGlobalParticipantDisjointnessVerified':False,'modelTrainingReady':False,'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False}
atomic_json(C/'acoustic-export-protocol.json',protocol);examples=[];meetings=[];failures=[];state={'state':'EXPORTING_TRAINING_ONLY_STAGE_A_NO_NEURAL_RUNTIME','startedAt':datetime.now().astimezone().isoformat(),'completed':[],'failures':failures,'qualityQualified':False,'newNeuralCalls':0,'parameterUpdates':0}
def lexical(text):return any(not(c.isspace() or unicodedata.category(c).startswith(('P','S'))) for c in re.sub(r'<[^>]*>','',text))
def references(item):
 p=sourceplan[item['meeting']]
 if item['language']=='Chinese':
  file=item['reference']['file'];assert sha(file)==item['reference']['sha256'];rows=read_reference_intervals(file)
 else:
  rows=[]
  with zipfile.ZipFile(p['annotationArchive']) as z:
   for speaker in official_speakers(z,item['meeting']):
    name='words/'+item['meeting']+'.'+speaker+'.words.xml'
    for index,node in enumerate(X.fromstring(z.read(name)).iter('w')):
     text=''.join(node.itertext());rows.append({'start':float(node.attrib['starttime']),'end':float(node.attrib['endtime']),'speaker':speaker,'text':text,'index':index,'annotationFile':name})
 return sorted(rows,key=lambda r:(r['start'],r['end'],r['speaker']))
try:
 for item in data['completed']:
  meeting=item['meeting'];assert meeting not in plan['existingDevelopmentSourcesExcluded'] and 'L_R003' not in meeting
  try:
   assert sha(item['audio'])==item['audioSha256'];rows=references(item);folder=OUT/meeting;folder.mkdir();atomic_json(folder/'original-reference-events.json',{'events':rows,'modified':False,'trainingOnly':True})
   usable=[];unclear=[];skip=Counter()
   for index,row in enumerate(rows):
    assert 0<=row['start']<=row['end']<=item['audioSeconds']+.1
    if not row['text'].strip():skip['emptyIntervals']+=1;continue
    if '<' in row['text'] and '>' in row['text']:
     unclear.append(row);skip['taggedOrUnclearIntervals']+=1;continue
    if not lexical(row['text']):skip['nonlexicalLabels']+=1;continue
    if row['end']>item['audioSeconds'] or row['start']==row['end']:
     unclear.append(row);skip['outOfAudioOrZeroDurationLabels']+=1;continue
    usable.append(dict(row,sourceIndices=[index]))
   # Only consecutive same-person words/utterances are joined. No word is
   # changed and merging never jumps over another speaker in the timeline.
   merged=[];join=' ' if item['language']=='English' else ''
   for row in usable:
    if merged and row['speaker']==merged[-1]['speaker'] and row['start']-merged[-1]['end']<=.5:
     previous=merged[-1];previous['end']=max(previous['end'],row['end']);previous['text']+=join+row['text'];previous['sourceIndices']+=row['sourceIndices']
    else:merged.append(dict(row))
   clusters=[]
   for row in merged:
    if clusters and row['start']<clusters[-1]['end']-1e-9:
     clusters[-1]['end']=max(clusters[-1]['end'],row['end']);clusters[-1]['events'].append(row)
    else:clusters.append({'start':row['start'],'end':row['end'],'events':[row]})
   accepted=[];group=[]
   def flush():
    if not group:return
    first,last=group[0][0],group[-1][0];selected=[r for _,cluster in group for r in cluster['events']];start=group[0][1]['start'];end=group[-1][1]['end']
    people={r['speaker'] for r in selected}
    if not(2<=end-start<=30 and len(people)>=1):skip['shortLongOrSingleSpeakerGroups']+=1;group.clear();return
    if any(r['start']<end and r['end']>start for r in unclear):skip['groupsIntersectUnclearLabels']+=1;group.clear();return
    before=clusters[first-1]['end'] if first else 0.;after=clusters[last+1]['start'] if last+1<len(clusters) else item['audioSeconds']
    pad=min(.1,max(0,(30-(end-start))/2));left=max(start-pad,(before+start)/2);right=min(end+pad,(end+after)/2,item['audioSeconds'])
    first_frame=max(0,math.floor(left*16000));last_frame=min(item['frames'],math.ceil(right*16000));assert first_frame<last_frame
    if last_frame-first_frame>30*16000:skip['roundedGroupExceeds30s']+=1;group.clear();return
    assert psutil.disk_usage('E:/').free>plan['minimumDiskFreeBytes']
    if accepted:assert first_frame>=accepted[-1]['endFrame'],'No duplicated overlapping training windows'
    text=join.join(r['text'] for r in selected);assert text and all(len({r['speaker'] for r in cluster['events']})==1 for _,cluster in group)
    index=len(accepted);file=folder/('sequential-'+str(index).zfill(4)+'.wav');h=hashlib.sha256()
    with wave.open(item['audio'],'rb') as source,wave.open(str(file),'wb') as output:
     assert (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes())==(1,2,16000,item['frames'])
     output.setparams((1,2,16000,0,'NONE','not compressed'));source.setpos(first_frame);remaining=last_frame-first_frame
     while remaining:
      pcm=source.readframes(min(32000,remaining));assert pcm;remaining-=len(pcm)//2;output.writeframesraw(pcm);h.update(pcm)
    voices=[r['speaker'] for r in selected];collapsed=[v for i,v in enumerate(voices) if i==0 or v!=voices[i-1]]
    row={'id':meeting+'-sequential-'+str(index).zfill(4),'meeting':meeting,'language':item['language'],'corpus':item['corpus'],'role':'train-only',
     'audio':str(file),'audioSha256':sha(file),'pcmSha256':h.hexdigest(),'startFrame':first_frame,'endFrame':last_frame,'audioSeconds':(last_frame-first_frame)/16000,
     'text':text,'events':selected,'localSpeakerIds':sorted(people),'turns':collapsed,'speakerReturn':len(collapsed)!=len(set(collapsed)),
     'sourceAudio':item['audio'],'sourceAudioSha256':item['audioSha256'],'referenceOverlapPresent':False,'labelWordsEdited':False,'addedNoise':False,'resampled':False}
    accepted.append(row);group.clear()
   for index,cluster in enumerate(clusters):
    overlap=len({r['speaker'] for r in cluster['events']})>1
    if overlap or cluster['end']-cluster['start']>30:
     flush();skip['overlapOrLongClustersExcludedFromStageA']+=1;continue
    if group and (cluster['end']-group[0][1]['start']>30 or cluster['start']-group[-1][1]['end']>3):flush()
    group.append((index,cluster))
   flush();examples.extend(accepted)
   summary={'meeting':meeting,'language':item['language'],'originalAudioSeconds':item['audioSeconds'],'originalReferenceEvents':len(rows),'examples':len(accepted),
    'trainingAudioSeconds':sum(r['audioSeconds'] for r in accepted),'speakerReturnExamples':sum(r['speakerReturn'] for r in accepted),'selectionExclusions':dict(skip),
    'globalChinesePeopleCountNotInferredFromLocalIds':True,'referenceParser':PARSER_ID if item['language']=='Chinese' else 'Complete official AMI speakers/word XML'}
   atomic_json(folder/'examples.json',accepted);meetings.append(summary);state['completed'].append(summary);atomic_json(OUT/'run.json',state);print(json.dumps(summary,ensure_ascii=False),flush=True)
  except BaseException as error:
   failure={'meeting':meeting,'error':repr(error)};failures.append(failure);atomic_json(OUT/'run.json',state)
 order=sorted(examples,key=lambda r:hashlib.sha256(('fixed-multilingual-order20261116'+r['id']).encode()).hexdigest())
 with (OUT/'train.jsonl').open('x',encoding='utf-8') as output:
  for row in order:output.write(json.dumps({'audio':row['audio'],'text':'language '+row['language']+'<asr_text>'+row['text']},ensure_ascii=False)+'\n')
 atomic_json(OUT/'example-provenance.json',order)
 groups=[]
 for language in ['English','Chinese']:
  selected=[r for r in examples if r['language']==language];groups.append({'language':language,'meetings':len({r['meeting'] for r in selected}),'examples':len(selected),
   'audioSeconds':sum(r['audioSeconds'] for r in selected),'speakerReturnExamples':sum(r['speakerReturn'] for r in selected)})
 assert all(r['examples']>0 for r in groups),'Both languages need actual complete examples'
 state.update(state='COMPLETE_ACOUSTIC_TRAINING_INPUT_EXPORT_NOT_A_TRAINED_MODEL',groups=groups,trainJsonl=str(OUT/'train.jsonl'),trainJsonlSha256=sha(OUT/'train.jsonl'),examples=len(examples),
  originalPublicSourceHours=sum(r['audioSeconds'] for r in data['completed'])/3600,trainingStarted=False,modelTrainingReady=False,chineseGlobalParticipantDisjointnessVerified=False)
except BaseException as error:state.update(state='INCOMPLETE_TRAINING_DATA_EXPORT_RETAINED_NO_TRAINING',error=repr(error));raise
finally:
 state['finishedAt']=datetime.now().astimezone().isoformat();state['limits']=limits.query();atomic_json(OUT/'run.json',state);atomic_json(C/'acoustic-export.json',state)
print(json.dumps({k:state.get(k) for k in ['state','groups','examples','failures','trainingStarted','modelTrainingReady']},ensure_ascii=False))
