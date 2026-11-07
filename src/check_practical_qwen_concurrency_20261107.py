"""Actual public command must refuse while the real full-ASR worker is live.

No dummy model, GPU work, reference or other application is started/stopped.
The only attempted command uses a pinned public test clip and an isolated
task directory; it must fail before any neural child is launched.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
B=R/'docs/handoffs/20261107-model-generation-recovery'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
C=Path(read(B/'practical-qwen-native-r1/active-execution.json')['control'])
assert C.resolve().parent==B.resolve() and C.name in ['practical-qwen-signal-r3','practical-qwen-bounded-r4']
live=read(C/'full/run.json');assert live['state'] in ['RUNNING_COMPLETE_OFFICIAL_NATIVE_ASR','RUNNING_BOUNDED_NATIVE_FULL']
process=psutil.Process(live['activePid'])
family=[process]+process.children(recursive=True)
assert any(any(Path(arg).name in ['practical_qwen_full_worker_20261107.py','practical_qwen_bounded_worker_20261107.py'] for arg in p.cmdline()) for p in family)
pack=B/'native8-command-r1/model-pack.json';audio=Path(read(B/'native8-f16-smoke-r1/audio-only.json')[0]['audio'])
root=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107')/('public-concurrency-control-'+C.name)
assert not root.exists() and not (C/'concurrency-proof.json').exists()
command=[sys.executable,str(Path(__file__).with_name('companion_local_meeting_20261107.py')),'--audio',str(audio),'--model-pack',str(pack),'--work-dir',str(root)]
r=subprocess.run(command,capture_output=True,text=True,encoding='utf8',creationflags=subprocess.CREATE_NO_WINDOW)
task=read(root/'task.json')
assert r.returncode!=0 and '已有模型正在处理' in task['error'],r.stdout+r.stderr
assert not task.get('activePid') and all(not attempt['stages'] for attempt in task['attempts'])
assert not list(root.rglob('*.raw.json')) and not list(root.rglob('*.log'))
assert psutil.pid_exists(live['activePid']) and process.is_running(),'Original real run exited during this control; inspect before claiming a passed live guard'
proof={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_REAL_COMMAND_REFUSES_CONCURRENT_NATIVE_ASR_BEFORE_NEURAL_LAUNCH',
  'publicAudio':str(audio),'modelPack':str(pack),'commandExitCode':r.returncode,'taskState':task['state'],'refusal':task['error'],
  'newNeuralStages':0,'originalFullRunNotStopped':True,'otherApplicationsTouched':False,'referencesProvided':False,
  'adapterSourceSha256':hashlib.sha256(Path(__file__).with_name('companion_local_meeting_20261107.py').read_bytes()).hexdigest(),'qualityQualified':False}
(C/'concurrency-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(proof,ensure_ascii=False))
