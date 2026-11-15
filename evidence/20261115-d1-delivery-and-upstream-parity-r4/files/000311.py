"""Export only the actually passed native control into an opt-in local pack."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
parser=argparse.ArgumentParser();parser.add_argument('--control');args=parser.parse_args();C=Path(args.control) if args.control else B/'practical-qwen-native17-r5'
assert C.resolve().parent==B.resolve() and C.name in ['practical-qwen-native17-r5','practical-qwen-author-boundaries-r6']
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
pilot=read(C/'pilot/state.json');assert pilot['state']=='PASS_BOUNDED_NATIVE_PILOT_FULL_QUALITY_UNMEASURED'
P=read(C/'protocol.json');assert pilot['binding']['protocolSha256']==sha(C/'protocol.json')
module='practical_qwen_boundaries_worker_20261107.py' if C.name.endswith('boundaries-r6') else 'practical_qwen_checkpoint_worker_20261107.py'
worker=Path(__file__).with_name(module);assert sha(worker)==P['workerSourceSha256']
assert read(C/'model-ready.json')['state']=='PINNED_NATIVE17_ALL_FILES_VERIFIED_NO_INFERENCE'
files=['protocol.json','native-protocol.json','seed-manifest.json','audio-only.json','pilot-extra-audio-only.json','pilot/state.json','model-ready.json','hip-inventory.json']
pack={'version':1,'backend':'qwen-native-bounded','createdAt':datetime.now().astimezone().isoformat(timespec='seconds'),
  'sourceControl':str(C),'pinnedFiles':{file:sha(C/file) for file in files},'workerSourceSha256':sha(worker),'workerModule':module,
  'pythonExecutable':'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',
  'recoverySourceSha256':P['recoverySourceSha256'],'modelId':'Qwen/Qwen3-ASR-1.7B-hf',
  'capabilities':{'localAsr':True,'wordTimestamps':False,'speakerAttribution':False,'overlapVoiceSeparation':False,'minutes':False},
  'qualityQualified':False,'installedAppDefaultChanged':False,'scope':'Explicit local research candidate pack. A passed short control is not full quality, phone/card or sale qualification. Private task contents never enter public evidence.'}
assert not (C/'model-pack.json').exists();atomic_json(C/'model-pack.json',pack)
print(json.dumps({'state':'EXPORTED_PASSED_SHORT_CONTROL_OPT_IN_PACK_NOT_QUALITY_PROMOTED','pack':str(C/'model-pack.json')}))
