from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, wave, psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'model-research/src'
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
cache=Path('E:/CodexData/Companion/.model-cache/english-granite-official20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
ap=argparse.ArgumentParser();mode=ap.add_mutually_exclusive_group();mode.add_argument('--readonly-views',action='store_true');mode.add_argument('--prepare-native-inputs',action='store_true');mode.add_argument('--freeze-gpu',action='store_true');args=ap.parse_args()
if args.prepare_native_inputs or args.freeze_gpu:
 P=read(C/'execution-protocol-r6.json')
 for f in P['files']:
  if Path(f['file']).resolve()==(S/'granite_reference_worker_20261117.py').resolve():f['sha256']=sha(f['file'])
  else:assert sha(f['file'])==f['sha256'],f['file']
 P.update(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),admissionSeconds=0)
 if args.prepare_native_inputs:
  P.update(state='FROZEN_NATIVE_INPUT_PREPARATION_ONLY_NO_PRETRAINED_FORWARD',prepareNativeInputsOnly=True,
   workerSha256=sha(S/'granite_reference_worker_20261117.py'),run=str(C/'prepared-native-inputs-r1'),maximumSeconds=300)
  target=C/'prepare-native-inputs-protocol-r1.json'
 else:
  native=C/'prepared-native-inputs-r1'
  assert read(native/'completed.json')['state']=='COMPLETE_NATIVE_INPUTS_NO_PRETRAINED_INFERENCE'
  assert read(native/'native-frontend-control.json')['state']=='PASS_ALL12_NATIVE_PROCESSOR_GEOMETRY_AND_PINNED_TEMPLATE'
  old=read(J/'english-transducer-r1/protocol.json')
  sources=['granite_reference_gpu_worker_20261117.py','moss_streamed_weights_20261104.py',
   'meeting_acoustic_contract_20261116.py','meeting_acoustic_worker_20261116.py','companion_community1_adapter_20261115.py']
  for name in sources:P['files'].append({'file':str(S/name),'sha256':sha(S/name)})
  P['files'].append({'file':str(native/'native-frontend-control.json'),'sha256':sha(native/'native-frontend-control.json')})
  P.update(state='FROZEN_NATIVE_GPU_REFERENCE_PREPARED_INPUTS_DEVICE_UNVERIFIED',
   computeDevice='rx6800xt',gpuRuntime=old['runtime'],blas=old['blas'],
   workerSha256=sha(S/'granite_reference_gpu_worker_20261117.py'),run=str(C/'native-gpu-r1'),
   preparedNativeInputs=str(native/'native-frontend-control.json'),checkpointTensorBytes=4626414392,
   shardSha256={Path(f['file']).name:f['sha256'] for f in P['files'] if Path(f['file']).suffix=='.safetensors'},
   recipe='Same native officialBF16/greedy/originalPCM reference. Exact CPU-native inputs prepared once; original tensors streamed once into6800XT via existing byte-roundtrip-verified loader. No CPU frontend or CPU parameter offload during GPU generation.',
   gpuExecutionVerified=False)
  for key in ['dependencyRoot','requireOfficialCpuTorch','preparedOffloadDirectory','preparedOffloadReceipt']:P.pop(key,None)
  target=C/'execution-protocol-gpu-r1.json'
 assert not target.exists();target.write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'protocol':str(target),'state':P['state'],'sha256':sha(target),'cases':len(P['cases'])}));raise SystemExit(0)
if args.readonly_views:
 P=read(C/'execution-protocol-r6.json')
 assert read(C/'native-cpu-r6/completed.json')['state'].startswith('FAILED')
 assert read(C/'torch-install-payload-integrity.json')['state'].startswith('PASS_')
 assert read(C/'native-cpu-r6/native-frontend-control.json')['state']=='PASS_ALL12_NATIVE_PROCESSOR_GEOMETRY_AND_PINNED_TEMPLATE'
 original=P['workerSha256'];changed=[]
 for f in P['files']:
  if Path(f['file']).resolve()==(S/'granite_reference_worker_20261117.py').resolve():
   changed.append({'file':f['file'],'before':f['sha256'],'after':sha(f['file'])});f['sha256']=sha(f['file'])
  else:assert sha(f['file'])==f['sha256'],f['file']
 assert len(changed)==1
 for path in [S/'readonly_cpu_offload_20261117.py',C/'native-cpu-r6/ES2003b-seq-000.json']:
  P['files'].append({'file':str(path),'sha256':sha(path)})
 control=read(C/'native-cpu-r6/ES2003b-seq-000.json')
 P.update(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
  state='FROZEN_ONE_READONLY_LOADING_OPTIMIZATION_SAME_NATIVE_REFERENCE',
  workerSha256=sha(S/'granite_reference_worker_20261117.py'),
  run=str(C/'native-cpu-readonly-r1'),loadingMode='readonly_cpu_views',admissionSeconds=0,
  sameOriginalOutputControl=str(C/'native-cpu-r6/ES2003b-seq-000.json'),minimumFirstCaseSpeedup=2,
  maximumFirstCaseSeconds=control['seconds']/2,
  recipe='Same original official model/processor/BF16/CPU/greedy recipe. Only eliminate per-layer private tensor copies via read-only memory views and the same standard Accelerate alignment hooks. No caching, weight arithmetic, runtime patch or GPU use.',
  decisionBasis={'oldResult':'Original12.05s input took300.183s; second case exceeded600s. No complete quality result.',
   'sourceFinding':'Installed Accelerate load_offloaded_weight calls torch.tensor(np.memmap), copying every layer on every forward.',
   'controlledChange':'CPU-only read-only zero-copy views, released by unchanged alignment post hooks; original2GiB/25percent/realRAM floor retained.',
   'retainOnlyIf':'Tiny BF16 outputs and first original generated IDs identical; first original must finish at least2x faster, then complete original12case quality cohort.',
   'stop':'First-case speed/equality failure, original memory pressure or frozen deadlines; no second loading variant.'})
 required=P['minimumAvailableBytes']+P['privateLimitBytes']+411045888
 available=psutil.virtual_memory().available
 assert available>=required,{'available':available,'required':required}
 target=C/'execution-protocol-readonly-r1.json';assert not target.exists()
 target.write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 pre=dict(state='PASS_INPUT_DEPENDENCY_BINDING_AND_ONE_LAYER_MEMORY_ENVELOPE',
  protocol=str(target),protocolSha256=sha(target),sourceChange=changed,
  availableRamBytes=available,conservativeStartRequirementBytes=required,
  originalPrivateLimitBytes=P['privateLimitBytes'],originalCpuPercent=P['cpuPercent'],
  firstCaseMustFinishWithinSeconds=P['maximumFirstCaseSeconds'],
  maximumCaseSeconds=P['maximumCaseSeconds'],minimumAvailableBytes=P['minimumAvailableBytes'],
  originalReferencesAndDecodingUnchanged=True,newNeuralCalls=0,newTrainingUpdates=0)
 (C/'preflight-readonly-r1.json').write_text(json.dumps(pre,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(pre));raise SystemExit(0)
assets=read(C/'asset-acquisition-r1/completed.json')
assert assets['state']=='COMPLETE_PINNED_GRANITE_REFERENCE_ASSETS_NO_MODEL_EXECUTION'
cases=[]
for c in read(J/'english-transducer-r1/audio-only.json'):
 with wave.open(c['audio'],'rb') as w:pcm=w.readframes(w.getnframes())
 cases.append({**c,'pcmSha256':hashlib.sha256(pcm).hexdigest()})
site=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
source_files=[S/'granite_reference_worker_20261117.py',S/'moss_windows_resource_limits_20261104.py',
 S/'durable_model_state_20261117.py',site/'accelerate/big_modeling.py',site/'accelerate/utils/offload.py',
 site/'accelerate/hooks.py',site/'transformers/conversion_mapping.py',site/'transformers/core_model_loading.py']
source_files+=list((site/'transformers/models/granite_speech').glob('*.py'))
files=[{'file':str(p),'sha256':sha(p)} for p in source_files]
files += [{'file':x['file'],'sha256':x['sha256']} for x in assets['completed']]
P={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
 'state':'FROZEN_ONE_NATIVE_BF16_GRANITE_ENGLISH_REFERENCE',
 'modelRoot':str(cache),'repository':assets['repository'],'revision':assets['revision'],
 'assets':str(C/'asset-acquisition-r1/completed.json'),'files':files,
 'workerSha256':sha(S/'granite_reference_worker_20261117.py'),'run':str(C/'native-cpu-r1'),
 'cases':cases,'neuralLock':'E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock',
 'privateLimitBytes':2147483648,'minimumAvailableBytes':3414499000,'cpuPercent':25,
 'nativeThreads':4,'blasThreads':1,'cpuTemperatureMode':'observe-only',
 'maximumSeconds':2700,'maximumCaseSeconds':600,'maxNewTokens':512,
 'prompt':'<|audio|>transcribe the speech with proper punctuation and capitalization.',
 'recipe':'Original official model/processor, eager CPU BF16, greedy decode; standard Accelerate disk_offload with byte-identical per-tensor files. Official four key renamings, no tensor arithmetic conversion, externalLM, hotword, VAD, denoise or word post-edit.',
 'gate':{'maximumEnglishErrors':70,'referenceWords':709,'eachMeetingNoWorseThanBestExistingBase':True,
         'stricterThanOriginal99ErrorGate':True,'saleQualification':False},
 'trainingUpdates':0,'referenceReadByInference':False,'qualityQualified':False,'saleQualified':False}
p=C/'execution-protocol-r1.json';assert not p.exists();p.write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'protocol':str(p),'clips':len(cases),'assetsBytes':sum(x['bytes'] for x in assets['completed'])}))
