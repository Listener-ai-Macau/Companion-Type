"""Annotation-only selection of natural, non-overlapping multi-speaker audio.

Never consult model outputs. Keep complete Chinese intervals / English words,
original pauses, microphone bytes, references, and exclusions separately.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,os,re,sys,urllib.request,wave,zipfile
import xml.etree.ElementTree as ET
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
sys.path.insert(0,str(S))
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from reference_textgrid_20261104 import read_reference_intervals
from ami_reference_coverage_20261115 import official_speakers
import soundfile as sf
R=S.parent.parent
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r1')
Z=Path('E:/CodexData/Companion/product-d1d2-20261114/ami-manual/ami_public_manual_1.6.2.zip')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def now():return datetime.now().astimezone().isoformat()

def plans(rows):
 # A cross-speaker connected overlap component is an excluded barrier. Nothing
 # is cut out, stitched, or silenced within an exported contiguous window.
 components=[]
 for row in rows:
  if components and row['start']<components[-1]['end']-1e-9:
   c=components[-1];c['rows'].append(row);c['end']=max(c['end'],row['end'])
  else:components.append({'start':row['start'],'end':row['end'],'rows':[row]})
 runs=[];current=[]
 for c in components:
  if len({r['speaker'] for r in c['rows']})>1:
   if current:runs.append(current);current=[]
  else:current.extend(c['rows'])
 if current:runs.append(current)
 eligible=[]
 for run in runs:
  i=0
  while i<len(run):
   j=i
   while j+1<len(run) and run[j+1]['end']-run[i]['start']<=29.84+1e-9:j+=1
   part=run[i:j+1];speakers=list(dict.fromkeys(r['speaker'] for r in part if r['text'].strip()))
   if 10<=max(r['end'] for r in part)-part[0]['start']<=29.84+1e-9 and len(speakers)>=2 and all(not r.get('unscorable') for r in part):
    turns=[r['speaker'] for k,r in enumerate(part) if not k or r['speaker']!=part[k-1]['speaker']]
    eligible.append({'start':part[0]['start'],'end':max(r['end'] for r in part),'rows':part,
     'speakers':speakers,'turns':turns,'speakerReturn':len(turns)>len(set(turns))})
    i=j+1
   else:i+=1
 return eligible,{'referenceEvents':len(rows),'overlapComponents':sum(len({r['speaker'] for r in c['rows']})>1 for c in components),
  'nonoverlapRuns':len(runs),'eligibleDisjointPlans':len(eligible)}

def ami_rows(z,meeting):
 result=[]
 speakers=official_speakers(z,meeting)
 for speaker in speakers:
  name=f'words/{meeting}.{speaker}.words.xml'
  if name not in z.namelist():return []
  for index,n in enumerate(ET.fromstring(z.read(name))):
   if 'starttime' not in n.attrib or 'endtime' not in n.attrib:continue
   start,end=float(n.attrib['starttime']),float(n.attrib['endtime'])
   if end<=start or n.attrib.get('punc')=='true':continue
   text=''.join(n.itertext()).strip() if n.tag=='w' else ''
   result.append({'start':start,'end':end,'speaker':speaker,'text':text,'index':index,
    'unscorable':n.tag=='w' and (not text or '<' in text or '>' in text),
    'annotationElement':n.tag,'annotationFile':name})
 return sorted(result,key=lambda r:(r['start'],r['end'],r['speaker'],r['index']))

def main():
 assert not (C/'protocol.json').exists(),'Frozen cohort is immutable'
 C.mkdir(parents=True,exist_ok=True);E.mkdir(parents=True,exist_ok=True)
 inventory=[];sources=[];selected=[]
 for s in read(R/'docs/handoffs/20261108-tse-source-supervision/sources.json'):
  assert sha(s['reference'])==s['referenceSha256'] and sha(s['localFlac'])==s['expectedWholeFileLfsSha256']
  rows=sorted([r for r in read_reference_intervals(s['reference']) if r['text'].strip()],key=lambda r:(r['start'],r['end'],r['speaker']))
  for r in rows:r['unscorable']='<' in r['text'] or '>' in r['text']
  eligible,audit=plans(rows);count=4 if s['role']=='train' else 6
  assert len(eligible)>=count,(s['meeting'],audit)
  source={**s,'language':'Chinese','corpus':'AISHELL-4','audio':s['localFlac'],
   'audioSha256':s['expectedWholeFileLfsSha256'],'license':'CC-BY-SA-4.0',
   'licenseSource':'https://www.openslr.org/111/','referenceGranularity':'complete TextGrid intervals'}
  sources.append(source);inventory.append({'meeting':s['meeting'],'role':s['role'],**audit})
  indices=[i*(len(eligible)-1)//(count-1) for i in range(count)]
  selected.extend((source,rows,k,eligible[k]) for k in indices)
 with zipfile.ZipFile(Z) as z:
  all_meetings=sorted({n.split('/')[-1].split('.')[0] for n in z.namelist() if n.startswith('words/') and n.endswith('.A.words.xml')})
  # Known dev source plus first unused annotation-eligible meeting, chosen
  # lexicographically without recognition/error/confidence information.
  chosen=['ES2003b'];candidates=[]
  for meeting in all_meetings:
   if meeting in ('ES2003b','EN2002a'):continue
   rows=ami_rows(z,meeting)
   if not rows:continue
   eligible,audit=plans(rows)
   if len(eligible)<6:continue
   url=f'https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{meeting}/audio/{meeting}.Array1-01.wav'
   try:
    with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:
     assert response.status==200
    candidates.append({'meeting':meeting,**audit,'audioAvailability':'HTTP200'});chosen.append(meeting);break
   except Exception as error:candidates.append({'meeting':meeting,**audit,'audioAvailability':repr(error)})
  assert len(chosen)==2,'No public unused eligible AMI mono meeting available'
  for meeting in chosen:
   rows=ami_rows(z,meeting);eligible,audit=plans(rows)
   url=f'https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{meeting}/audio/{meeting}.Array1-01.wav'
   audio=Path('E:/CodexData/Companion/product-d1d2-20261114/ordinary-english-r1')/(meeting+'.Array1-01.wav') if meeting=='ES2003b' else E/'sources'/(meeting+'.Array1-01.wav')
   if not audio.exists():
    audio.parent.mkdir(parents=True,exist_ok=True);partial=audio.with_suffix('.wav.partial')
    assert not partial.exists(),'Preserve partial download; do not silently retry'
    with urllib.request.urlopen(url,timeout=60) as response,partial.open('xb') as out:
     while True:
      block=response.read(1024*1024)
      if not block:break
      out.write(block)
     out.flush();os.fsync(out.fileno())
    with wave.open(str(partial),'rb') as wav:
     assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000)
     assert wav.getnframes()/16000>=max(r['end'] for r in rows)
    partial.rename(audio)
   source={'meeting':meeting,'role':'validation','language':'English','corpus':'AMI','audio':str(audio),
    'audioSha256':sha(audio),'url':url,'annotationArchive':str(Z),'annotationSha256':sha(Z),
    'annotationUrl':'https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip',
    'license':'CC-BY-4.0','licenseSource':'https://groups.inf.ed.ac.uk/ami/download/',
    'referenceGranularity':'complete manually transcribed words, official forced-aligned word times; nonverbal activity also retained'}
   sources.append(source);inventory.append({'meeting':meeting,'role':'validation',**audit})
   selected.extend((source,rows,k,eligible[k]) for k in [i*(len(eligible)-1)//5 for i in range(6)])
 write(C/'source-inventory.json',{'at':now(),'sources':sources,'sceneCounts':inventory,'newAmiSelection':candidates})
 audio_only=[];scoring=[]
 for source,rows,index,plan in selected:
  info=sf.info(source['audio']);assert info.samplerate==16000 and info.subtype=='PCM_16' and info.channels in (1,8)
  start,end=plan['start'],plan['end'];part=plan['rows']
  prior=max((r['end'] for r in rows if r['end']<=start+1e-9),default=0.)
  following=min((r['start'] for r in rows if r['start']>=end-1e-9),default=info.frames/16000)
  low=max(0,math.ceil(start*16000)-1280,math.ceil((prior+start)*8000))
  high=min(info.frames,math.ceil(end*16000)+1280,math.ceil((end+following)*8000))
  assert 0<high-low<=480000
  assert not [r for r in rows if r not in part and math.ceil(r['start']*16000)<high and math.ceil(r['end']*16000)>low],(source['meeting'],start,end)
  assert not any(a['speaker']!=b['speaker'] and a['start']<b['end']-1e-9 and b['start']<a['end']-1e-9 for i,a in enumerate(part) for b in part[i+1:])
  with sf.SoundFile(source['audio']) as original:
   original.seek(low);pcm=original.read(high-low,dtype='int16',always_2d=True)[:,0].astype('<i2',copy=False).tobytes()
  case_id=source['meeting']+'-seq-'+str(index).zfill(3);target=E/'audio'/(case_id+'.wav');target.parent.mkdir(exist_ok=True)
  assert not target.exists()
  with wave.open(str(target),'wb') as out:
   out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
  with wave.open(str(target),'rb') as check:assert check.readframes(high-low)==pcm
  item={'id':case_id,'condition':'sequential-original-room','meeting':source['meeting'],'wav':str(target),
   'wavSha256':sha(target),'pcmSha256':hashlib.sha256(pcm).hexdigest(),'frames':high-low,
   'audioSeconds':(high-low)/16000,'language':source['language']}
  audio_only.append(item)
  text=(' ' if source['language']=='English' else '').join(r['text'] for r in part if r['text'])
  scoring.append({**item,'role':source['role'],'corpus':source['corpus'],'sourceStartFrame':low,'sourceEndFrame':high,
   'sourceAudioSha256':source['audioSha256'],'referenceEvents':part,'rawReferenceText':text,
   'speakers':plan['speakers'],'turns':plan['turns'],'speakerReturn':plan['speakerReturn'],
   'overlapPresentByReference':False,'eligiblePlanIndex':index,'addedNoise':False})
 assert len(audio_only)==32 and len({r['id'] for r in audio_only})==32
 write(C/'audio-only.json',audio_only);write(C/'scoring-only.json',scoring)
 native=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json')
 write(C/'protocol.json',{'state':'FROZEN_STAGE_A_BEFORE_MODEL_OUTPUTS','at':now(),'cases':len(audio_only),
  'audioOnlyManifestSha256':sha(C/'audio-only.json'),'scoringOnlyManifestSha256':sha(C/'scoring-only.json'),
  'sourceInventorySha256':sha(C/'source-inventory.json'),'nativeProtocol':str(native),'nativeProtocolSha256':sha(native),
  'selection':'Annotation-only cross-speaker overlap components excluded as barriers. Greedy disjoint complete-reference runs, 10–29.84s, >=2 speakers. Four uniformly spaced plans per training meeting, six per validation meeting. Natural padding<=80ms capped at annotation midpoint. Original source first microphone bytes only.',
  'curriculum':['A: sequential multi-speaker original room','B: overlap','C: noise robustness'],
  'newTraining':False,'qualityQualified':False,'fullMeetingGatesChanged':False,'finalHoldoutOpened':False,
  'inference':'Existing native Qwen1.7B BF16 greedy512 unchanged, one resident model, explicit corpus language, no references/counts/activity input. No separation, denoising, gain, resampling or stitching.',
  'targets':{'ChineseCER':0.05,'EnglishWER':0.05,'perSpeakerError':0.05,'DERZeroCollar':0.10},
  'limitations':['Annotation-assisted scene diagnostic, not final whole-recording acceptance.','AMI word times are forced-aligned estimates; boundaries and overlap absence have annotation uncertainty.','Chinese sources already used by prior diagnostic separator experiments, not a new blind holdout.','Original room acoustics retained; no added noise does not mean acoustically clean.','Speaker return is scored with a fixed meeting-level mapping, never optimal per-clip relabelling.'],
  'totalSeconds':sum(r['audioSeconds'] for r in audio_only),'speakerReturnCases':sum(r['speakerReturn'] for r in scoring),
  'resourceLimits':limits.query()})
 print(json.dumps({'control':str(C),'cases':len(audio_only),'seconds':sum(r['audioSeconds'] for r in audio_only),
  'speakerReturnCases':sum(r['speakerReturn'] for r in scoring),'inventory':inventory,'newEnglish':chosen[-1]},ensure_ascii=False))
if __name__=='__main__':main()
