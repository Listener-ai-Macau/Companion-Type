from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'model-research/src'
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
cache=Path('E:/CodexData/Companion/.model-cache/english-granite-official20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
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
