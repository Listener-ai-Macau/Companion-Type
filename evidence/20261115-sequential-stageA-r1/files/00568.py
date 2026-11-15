"""One hypothesis, two independent public training meetings, no validation tuning."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,urllib.request,wave,zipfile
import xml.etree.ElementTree as ET
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from ami_reference_coverage_20261115 import official_speakers
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r2/activity-cal-r1';C.mkdir()
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2/activity-cal-r1');E.mkdir()
Z=E.parents[1]/'ami-manual/ami_public_manual_1.6.2.zip'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
with zipfile.ZipFile(Z) as z:
 root=ET.fromstring(z.read('corpusResources/meetings.xml'))
 def metadata(name):return next(m for m in root if m.attrib.get('observation')==name)
 dev_people={s.attrib['global_name'] for name in ['ES2003b','EN2001a'] for s in metadata(name) if s.tag=='speaker'}
 train_people=[{s.attrib['global_name'] for s in metadata(name) if s.tag=='speaker'} for name in ['IS1000a','TS3005a']]
 assert not train_people[0]&train_people[1] and not set.union(*train_people)&dev_people
 sources=[]
 for name in ['IS1000a','TS3005a']:
  m=metadata(name);assert m.attrib['visibility']=='seen' and m.attrib['seen_type']=='training'
  sources.append({'meeting':name,'officialSpeakers':official_speakers(z,name),'globalPeople':sorted(s.attrib['global_name'] for s in m if s.tag=='speaker'),
   'url':f'https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{name}/audio/{name}.Array1-01.wav',
   'role':'calibration-training','license':'CC-BY-4.0','annotationArchive':str(Z),'annotationSha256':sha(Z)})
write(C/'selection-before-download.json',{'at':datetime.now().astimezone().isoformat(),'hypothesis':'English missed speech dominates speaker DER. Calibrate one constant activity threshold on independent public training meetings; weights/cache/slots/frontends unchanged. Do not train on validation or consult its alternative-threshold scores.',
 'sources':sources,'officialSplitSource':'https://groups.inf.ed.ac.uk/ami/corpus/datasets.shtml','licenseSource':'https://groups.inf.ed.ac.uk/ami/download/',
 'thresholds':[i/100 for i in range(10,91,5)],'referenceSelection':'All complete annotation-only greedy10–29.84s nonoverlap multi-speaker windows from both training meetings, using all official speakers, not model scores.',
 'objective':'Minimize maximum of the two training-meeting zero-collar DERs. Tie choose value closest to0.5, then higher. Fixed whole-meeting identity mapping from original0.5 for every threshold.',
 'adoptionRule':'Both training meetings must have DER<=10%, and mean DER must improve>=1 percentage point vs0.5. Otherwise reject without running alternative validation thresholds. If supported, evaluate only the chosen one on frozen development12 English windows, retain Chinese original0.5. No product adoption without original full-meeting bilingual controls.',
 'qualityGatesUnchanged':True,'newModelDownloads':False,'newWeightTraining':False,'finalHoldoutOpened':False})
for source in sources:
 name=source['meeting'];target=E/(name+'.Array1-01.wav');partial=target.with_suffix('.wav.partial');assert not partial.exists() and not target.exists()
 with urllib.request.urlopen(source['url'],timeout=60) as response,partial.open('xb') as out:
  size=0
  while True:
   block=response.read(1024*1024)
   if not block:break
   size+=len(block);assert size<100*1024**2;out.write(block)
  out.flush();os.fsync(out.fileno())
 with wave.open(str(partial),'rb') as wav:assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000)
 partial.rename(target);source.update(audio=str(target),audioSha256=sha(target))
 print(json.dumps({'downloaded':name,'bytes':size},ensure_ascii=False),flush=True)
write(C/'sources.json',sources)
audio=[{k:s[k] for k in ['meeting','audio','audioSha256']} for s in sources];write(C/'audio-only.json',audio)
P=read(D/'sequential-meeting-stageA-r1/speaker-r1/protocol.json');P['audioOnlySha256']=sha(C/'audio-only.json');P['purpose']='Two independent official training meetings for one English activity-threshold calibration, original model only.';write(C/'protocol.json',P)
b=read(D/'sequential-meeting-stageA-r1/speaker-r1/worker-binding.json');b['protocolSha256']=sha(C/'protocol.json');assert b['workerSha256']==sha(S/'sequential_meeting_speaker_worker_20261115.py');write(C/'worker-binding.json',b)
print('FROZEN_TWO_INDEPENDENT_ENGLISH_TRAIN_MEETINGS_NO_VALIDATION_TUNING',flush=True)
