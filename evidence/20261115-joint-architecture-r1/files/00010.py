"""Major-route checkpoint: official native joint ASR/diarization, no tuning grid.

Reuse the original0.9B tensors only if reconstructing the official native
checkpoint yields its published whole-file SHA. Never relabel old failed runs
as a new model, weaken RAM guards, or infer with validation labels.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,struct,sys,urllib.request
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1';C.mkdir()
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');E.mkdir()
old=Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104/model/model-00000-of-00001.safetensors')
old_sha='9a0ceb4ab7330357db3ff583dba8d83625d5b733b00e1d55d6970e11b07026c4'
repo='hf-audio/MOSS-Transcribe-Diarize-HF';revision='22dbe8f8849882d285aa5c668ea0e3b46418e827'
now=lambda:datetime.now().astimezone().isoformat()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def get_json(url):
 with urllib.request.urlopen(url,timeout=30) as r:return json.load(r)
def original_name(name):
 if name.startswith('model.audio_tower.'):return name.replace('model.audio_tower.','model.whisper_encoder.',1)
 for native,author in [('linear_1','layers.0'),('linear_2','layers.2'),('norm','layers.3')]:
  prefix='model.multi_modal_projector.'+native+'.'
  if name.startswith(prefix):return name.replace(prefix,'model.vq_adaptor.'+author+'.',1)
 return name
plan={'at':now(),'state':'FROZEN_ARCHITECTURE_CHANGE_BEFORE_COMPATIBILITY_OR_INFERENCE',
 'ownerDirection':'Stop local threshold/gap tweaking. Pursue a generally useful meeting engine verified across multiple complete meetings, not a single-recording solution.',
 'baseline':'Existing Qwen3-ASR1.7B + native Nemotron3 + forced alignment and speaker association, unchanged.',
 'onePrimaryAlternative':'Joint ASR/diarization/timestamps using official native Transformers MOSS-Transcribe-Diarize0.9B.',
 'priorRelatedFailure':'The same0.9B family was already tried via author custom runtime and did not produce a stable qualified complete long meeting on Windows AMD. This is not a newly discovered larger model. Only proceed if official native tensor/frontend/loader and bounded execution are verified; never repeat the old failed custom run unchanged.',
 'whyMateriallyDifferent':'Train/task architecture jointly predicts words and speaker IDs rather than assigning independent word onsets to a separate diarization journal. Native Transformers implementation differs from previously failed custom author runtime.',
 'dualPassProductDirection':'Keep local incremental draft during upload/recording; evaluate complete-session joint inference for final transcript and stable persons. Offline import uses the same final path. Existing live and offline contracts remain required.',
 'sourceModel':repo,'sourceRevision':revision,'officialAuthor':'https://github.com/OpenMOSS/MOSS-Transcribe-Diarize',
 'nativeDocs':'https://huggingface.co/docs/transformers/v5.21.0/en/model_doc/moss_transcribe_diarize',
 'scope':'Sequential multi-speaker first, overlap second, noise third. No language-specific conference hacks, gold hotwords, person counts, or manual word corrections.',
 'wholeMeetingDevelopmentCases':['S_R004S03C01','20200623_S_R001S07C01','ES2003b','EN2002a'],
 'sequentialDiagnostic':'Existing32 frozen stageA-r2 cases, with training/validation and languages separate.',
 'qualityContract':'Existing raw text and person-attributed error<5%, zero-collar DER<=10%, facts and critical gates unchanged. Native joint outputs do not imply any gate passed.',
 'modelSelectionMilestone':'Require substantial improvement across held-out meetings and languages, examine every meeting and worst cases, preserve Chinese and existing whole-meeting controls. One successful recording cannot select a model.',
 'trainingDirection':'First establish which whole architecture improves held-out meetings. Then supervised meeting-domain adaptation of that pretrained joint task using speaker/meeting-disjoint public training and validation, not training from scratch or another tiny sample fit.',
 'resourceContract':{'oneNeuralFamily':True,'workerCPUPercent':5,'workerPrivateMemoryGiB':2,'actualWindowsLowMemoryStop':True,'raiseLimits':False},
 'noProductDefaultChange':True,'noNewWeightTraining':True,'finalHoldoutOpened':False,'qualityQualified':False}
write(C/'direction.json',plan)
state={'state':'VERIFYING_OFFICIAL_NATIVE_CHECKPOINT_REUSE','startedAt':now(),'neuralInferencePerformed':False,'qualityQualified':False}
try:
 tree=get_json(f'https://huggingface.co/api/models/{repo}/tree/{revision}')
 metadata=next(x for x in tree if x['path']=='model.safetensors');write(C/'native-weight-metadata.json',metadata)
 assert metadata['size']<2*1024**3 and old.stat().st_size==1817113576 and sha(old)==old_sha
 with old.open('rb') as f:
  size=struct.unpack('<Q',f.read(8))[0];header=json.loads(f.read(size));base=8+size
 url=f'https://huggingface.co/{repo}/resolve/{revision}/model.safetensors'
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=0-131071'}),timeout=30) as response:
  prefix=response.read(8);n=struct.unpack('<Q',prefix)[0];assert n<131072;native_header=response.read(n);assert len(native_header)==n
 h=json.loads(native_header);(C/'native-weight-header.bin').write_bytes(prefix+native_header)
 entries=sorted(((k,v) for k,v in h.items() if k!='__metadata__'),key=lambda kv:kv[1]['data_offsets'][0])
 assert len(entries)==len(header) and len({original_name(k) for k,v in entries})==len(header)
 digest=hashlib.sha256(prefix+native_header);offset=0;mapping=[]
 with old.open('rb') as f:
  for name,meta in entries:
   author=original_name(name);source=header[author]
   assert source['shape']==meta['shape'] and source['dtype']==meta['dtype']
   start,end=meta['data_offsets'];assert start==offset and end-start==source['data_offsets'][1]-source['data_offsets'][0]
   f.seek(base+source['data_offsets'][0]);remaining=end-start
   while remaining:
    data=f.read(min(8*1024**2,remaining));assert data;digest.update(data);remaining-=len(data)
   mapping.append({'native':name,'author':author,'dtype':meta['dtype'],'shape':meta['shape']});offset=end
 assert offset+8+n==metadata['size']
 reconstructed=digest.hexdigest();assert reconstructed==metadata['lfs']['oid'],('Same tensor shapes do not prove same weights',reconstructed)
 write(C/'tensor-reuse-proof.json',{'state':'PASS_EXACT_PUBLISHED_NATIVE_CHECKPOINT_SHA_FROM_EXISTING_AUTHOR_TENSORS',
  'authorCheckpoint':str(old),'authorCheckpointSha256':old_sha,'nativeRepository':repo,'nativeRevision':revision,
  'nativeCheckpointSha256':reconstructed,'nativeBytes':metadata['size'],'tensorCount':len(mapping),'mapping':mapping,
  'weightsQuantizedOrAltered':False,'largeCheckpointDownloadedOrDuplicated':False})
 model=E/'native-model';model.mkdir()
 assets=[]
 for entry in tree:
  name=entry['path']
  if name not in ['config.json','generation_config.json','processor_config.json','tokenizer.json','tokenizer_config.json','chat_template.jinja']:continue
  assert entry['size']<32*1024**2
  with urllib.request.urlopen(f'https://huggingface.co/{repo}/resolve/{revision}/{name}',timeout=30) as response:data=response.read(32*1024**2+1)
  assert len(data)==entry['size']
  if 'lfs' in entry:assert hashlib.sha256(data).hexdigest()==entry['lfs']['oid']
  else:assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==entry['oid']
  (model/name).write_bytes(data);assets.append({'file':str(model/name),'sha256':sha(model/name),'bytes':len(data)})
 assert len(assets)==6
 config=json.loads((model/'config.json').read_text());assert config['text_config']['hidden_size']==1024 and config['text_config']['num_hidden_layers']==28
 (model/'config.json').rename(model/'upstream-config.json')
 # Direct native class configuration will use upstream-config; no remote code.
 native=S.parent/'pinned-model-config/config.json';assert native.exists()
 state.update(state='OFFICIAL_NATIVE_JOINT_ARCHITECTURE_ASSETS_EXACT_TENSORS_READY_NO_INFERENCE',
  candidate='MOSS-Transcribe-Diarize0.9B native Transformers5.22.1',nativeModelRoot=str(model),files=assets,
  tensorReuseProofSha256=sha(C/'tensor-reuse-proof.json'),checkpointAlreadyLocal=True)
except BaseException as error:state.update(state='JOINT_NATIVE_PREPARATION_FAILED_RETAINED',error=repr(error));raise
finally:
 state.update(finishedAt=now(),resourceLimits=limits.query());write(C/'preparation.json',state)
print(json.dumps({k:v for k,v in state.items() if k not in ['files','resourceLimits']},ensure_ascii=False))
