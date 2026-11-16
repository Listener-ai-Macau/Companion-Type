"""Broad public training-data preparation only; no weights/training or holdout access."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,sys,urllib.request,xml.etree.ElementTree as X,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'joint-architecture-r1/meeting-domain-data-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
assert not C.exists() and not E.exists();C.mkdir();E.mkdir()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
revision='aada72727856313b19d4a030383c426364931dbf';url='https://huggingface.co/api/datasets/AISHELL/AISHELL-4/revision/'+revision+'?blobs=true'
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-meeting-corpus/1.0'}),timeout=30) as response:
 raw=response.read(4*1024**2);assert response.read(1)==b''
metadata=json.loads(raw);assert metadata['sha']==revision;(C/'aishell-publisher-metadata.json').write_bytes(raw)
inventory=json.loads((D/'sequential-meeting-stageA-r2/source-inventory.json').read_text(encoding='utf-8'))['sources']
excluded={r['meeting'] for r in inventory if r['role']!='train'}|{'ES2003b','EN2002a','S_R004S03C01','20200623_S_R001S07C01'}
files=metadata['siblings'];chinese=[];salt='Companion-wide-farfield-data-20261116'
for subset in ['train_L','train_M','train_S']:
 rows=[r for r in files if r['rfilename'].startswith(subset+'/wav/') and r['rfilename'].endswith('.flac')]
 rows=[r for r in rows if Path(r['rfilename']).stem not in excluded and 'L_R003' not in r['rfilename']]
 rows.sort(key=lambda r:hashlib.sha256((salt+r['rfilename']).encode()).hexdigest())
 selected=[]
 for row in rows:
  meeting=Path(row['rfilename']).stem;references=[r for r in files if Path(r['rfilename']).name==meeting+'.TextGrid']
  if len(references)!=1:continue
  selected.append({'meeting':meeting,'language':'Chinese','corpus':'AISHELL-4','role':'candidate-training-only','audioSource':row,'referenceSource':references[0],
   'subset':subset,'revision':revision,'license':'CC-BY-SA-4.0','licenseSource':'https://www.openslr.org/111/',
   'mirrorLicenseTagIsNotAuthoritative':'HF mirror metadata says Apache-2.0; preserve official OpenSLR CC-BY-SA-4.0 source instead.',
   'participantDisjointness':'Meeting-disjoint from all existing validation/development sources; cross-meeting participant overlap not established from local numeric speaker IDs.'})
  if len(selected)==4:break
 assert len(selected)==4,(subset,len(rows),len(selected));chinese.extend(selected)
archive=Path('E:/CodexData/Companion/product-d1d2-20261114/ami-manual/ami_public_manual_1.6.2.zip')
with zipfile.ZipFile(archive) as z:xml=z.read('corpusResources/meetings.xml')
root=X.fromstring(xml);entries={r.attrib['observation']:r for r in root.findall('meeting')}
seen_people={s.attrib['global_name'] for key in ['ES2003b','EN2001a','EN2002a'] for s in entries[key].findall('speaker')}
english=[]
for prefix in ['ES','IS','TS']:
 rows=[r for key,r in sorted(entries.items()) if key.startswith(prefix) and key.endswith('b') and r.attrib.get('seen_type')=='training' and r.attrib.get('type')=='scenario']
 selected=[]
 for row in rows:
  meeting=row.attrib['observation'];people={s.attrib['global_name'] for s in row.findall('speaker')}
  if people&seen_people or meeting in excluded:continue
  selected.append({'meeting':meeting,'language':'English','corpus':'AMI','role':'candidate-training-only',
   'url':'https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/'+meeting+'/audio/'+meeting+'.Array1-01.wav',
   'license':'CC-BY-4.0','licenseSource':'https://groups.inf.ed.ac.uk/ami/download/','annotationArchive':str(archive),'annotationArchiveSha256':sha(archive),
   'officialMetadata':row.attrib,'participants':[s.attrib for s in row.findall('speaker')],
   'disjointFromSeenValidationGlobalParticipants':True,'knownValidationGlobalParticipants':sorted(seen_people)})
  if len(selected)==4:break
 assert len(selected)==4,(prefix,len(selected));english.extend(selected)
plan={'state':'FROZEN_BROAD_PUBLIC_FARFIELD_TRAINING_SOURCE_PLAN_NO_TRAINING','at':datetime.now().astimezone().isoformat(),
 'sources':english+chinese,'existingDevelopmentSourcesExcluded':sorted(excluded),'reservedFinalPrefixNeverOpened':'L_R003',
 'selection':'12 AMI training meetings,4 per recording site;12 AISHELL training meetings,4 per room size. Selection uses only publisher split/participant metadata and fixed hash order, no candidate outputs.',
 'scope':'Collect original one-mic full meetings and source annotations, then export training-only audio/text supervision. No new model trial, no validation labels in training, no quality/sale/default change.',
 'trainingStarted':False,'newNeuralCalls':0,'parameterUpdates':0,'newModelSelectedByThisDataPlan':False,
 'cpuPercent':.5,'privateBytes':256*1024**2,'maximumNewDataBytes':12*1024**3,'minimumDiskFreeBytes':50*1024**3,
 'preparationDeadline':'2026-11-16T15:20:00+08:00','trainingLaunchDependency':'A usable training GPU/runtime and a separate proven train/dev participant split. No training launch under the present CPU-only2GiB inference budget.',
 'chineseGlobalSpeakerDisjointnessVerified':False,'modelTrainingReady':False,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,
 'referenceSources':{'AMI':'https://groups.inf.ed.ac.uk/ami/corpus/datasets.shtml','AISHELL':'https://www.openslr.org/111/',
  'QwenOfficialTraining':'https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning','MossOfficialJointFormat':'https://github.com/OpenMOSS/MOSS-Transcribe-Diarize/blob/main/FINETUNING.md'},
 'metadataSha256':hashlib.sha256(raw).hexdigest(),'amiMeetingsMetadataSha256':hashlib.sha256(xml).hexdigest()}
(C/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sources':len(plan['sources']),'english':[r['meeting'] for r in english],'chinese':[r['meeting'] for r in chinese],'trainingStarted':False}))
