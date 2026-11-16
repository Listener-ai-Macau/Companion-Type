from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';C=B/'qwen-cpu-port-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
text=(S/'english_specialist_cpu_worker_20261116.py').read_text(encoding='utf-8')
changes={'One fixed upstream Whisper Q8 CPU contrast':'Existing preferred Qwen family CPU Q8 port','ENGLISH_SPECIALIST':'QWEN_CPU_PORT',"'whisper' in model.arch.lower()":"'qwen' in model.arch.lower()",
 'with model.session(n_threads=4) as session:':"with model.session(n_threads=4,kv_type='f16',n_ctx=2048) as session:",
 "language='en',task='transcribe',timestamps='segment'":"language={'English':'en','Chinese':'zh'}[case['language']],task='transcribe',timestamps='none'"}
for old,new in changes.items():assert old in text,old;text=text.replace(old,new)
worker=S/'qwen_cpu_port_worker_20261116.py';assert not worker.exists();worker.write_text(text,encoding='utf-8');compile(text,str(worker),'exec')
text=(S/'run_english_specialist_cpu_20261116.py').read_text(encoding='utf-8').replace('ENGLISH_SPECIALIST','QWEN_CPU_PORT').replace('english_specialist_cpu_worker_20261116.py','qwen_cpu_port_worker_20261116.py')
runner=S/'run_qwen_cpu_port_20261116.py';assert not runner.exists();runner.write_text(text,encoding='utf-8');compile(text,str(runner),'exec')
old=read(B/'cpu-pcm-candidate-r4/binding.json');protocol=read(C/'protocol.json')
binding={k:old[k] for k in ['workerPython','ownerCpuBudgetPermission','neuralDeadline','runtimeFiles','library','pythonFiles','pythonRoot','helpers','cpuPercent','privateBytes']}
binding.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(worker),runnerSha256=sha(runner),model=read(C/'model-ready.json'),cases=protocol['cases'],settings=protocol['settings'],protocolSha256=sha(C/'protocol.json'),qualityQualified=False,newWeightTraining=False,productDefaultChanged=False)
binding['helpers'][str(S/'cpu_window_joint_worker_20261116.py')]=sha(S/'cpu_window_joint_worker_20261116.py')
assert not (C/'binding.json').exists();(C/'binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
reference=D/'sequential-meeting-stageA-r2/scoring-only.json';original=B/'stagea-cpu-composition-r2/score.json'
scoring={'reference':str(reference),'original32Score':str(original),'files':{str(p):sha(p) for p in [C/'protocol.json',C/'binding.json',reference,original,S/'score_sequential_meetings_20261115.py']},'scorerSha256':sha(S/'score_qwen_cpu_port_20261116.py')}
(C/'scoring-binding.json').write_text(json.dumps(scoring,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':'FROZEN_QWEN_CPU_PORT24_BEFORE_INFERENCE','cases':len(protocol['cases']),'modelSha256':binding['model']['sha256']}))
