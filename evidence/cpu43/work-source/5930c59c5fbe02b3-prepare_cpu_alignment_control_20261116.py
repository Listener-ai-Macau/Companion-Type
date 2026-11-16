from pathlib import Path
from datetime import datetime
import hashlib,json,py_compile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):
 assert not p.exists();p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for n in ['companion_cpu_aligner_loader_20261116.py','cpu_forced_alignment_worker_20261116.py','run_cpu_forced_alignment_20261116.py','score_qwen_cpu_chinese_whole_20261116.py']:py_compile.compile(str(S/n),doraise=True)
c=B/'qwen-cpu-chinese-characterization-r2';old=read(c/'whole-scoring-only.json')
files=[c/'binding.json',c/'scope-decision.json',c/'whole-scoring-only.json',S/'score_joint_whole_meetings_20261115.py']+[Path(p) for p in old['helpers']]
for row in old['cases']:
 for key in ['lexicalReference','baselineTextFile','activityReference']:
  path=Path(row[key]);digest_key='baselineTextSha256' if key=='baselineTextFile' else key+'Sha256';assert sha(path)==row[digest_key];files.append(path)
write(c/'scoring-binding.json',{'at':datetime.now().astimezone().isoformat(),'scorerSha256':sha(S/'score_qwen_cpu_chinese_whole_20261116.py'),'files':{str(p):sha(p) for p in files},'originalGatesUnchanged':True,'characterizationOnly':True})
C=B/'cpu-forced-alignment-control-r1';C.mkdir(exist_ok=False)
source=read(B/'qwen-cpu-port-r1/binding.json');done={r['id']:r for r in read(E/'qwen-cpu-port-run-r1/inference-state.json')['completed']};cases=[]
for language in ['English','Chinese']:
 row=next(r for r in source['cases'] if r['language']==language);raw=done[row['id']];assert sha(raw['file'])==raw['sha256'];packet=read(raw['file']);assert packet['naturalEos'] and not packet['wasTruncated']
 cases.append({**row,'text':packet['hypothesis'],'rawAsrFile':raw['file'],'rawAsrSha256':raw['sha256']})
helpers=['companion_cpu_aligner_loader_20261116.py','companion_windows_working_set_20261116.py','moss_windows_resource_limits_20261104.py','practical_alignment_text_20261107.py','practical_io_20261107.py']
installation=read(B/'cpu-forced-alignment-r2/runtime-installation.json')
binding={'at':datetime.now().astimezone().isoformat(),'workerPython':installation['source']['basePython'],'workerSha256':sha(S/'cpu_forced_alignment_worker_20261116.py'),
 'runnerSha256':sha(S/'run_cpu_forced_alignment_20261116.py'),'cpuTorchSite':str(E/'cpu-forced-alignment-r2/torch-cpu-site'),
 'modelRoot':'E:/CodexData/Companion/.model-cache/qwen-native-aligner-20261107/model','modelSha256':'00568245ceca5af1991d28562a75fe1ddc9bfeb041c27fda66947ea05c47fb86',
 'helpers':{str(S/n):sha(S/n) for n in helpers},'cases':cases,'neuralDeadline':'2026-11-16T15:40:00+08:00','cpuPercent':25,'computeThreads':4,'privateBytes':2*1024**3,'workingSetCeilingBytes':1879048192,
 'scope':'Port the existing fixed native timestamp classifier to CPU, after a synthetic standard-versus-mmap exact-logit control. Use recognized text only. No model selection or training.',
 'keepRule':['Synthetic CPU standard and mapped logits/argmax exactly equal.','Original recognized ASR characters preserved exactly.','No frame truncation, no GPU kernels, original resource guards retained.'],
 'qualityQualified':False,'timestampTruthMeasured':False,'newWeightTraining':False,'blindFinalHoldoutOpened':False}
write(C/'binding.json',binding);print(json.dumps({'control':str(C),'cases':[r['id'] for r in cases],'scoringBindingFrozenBeforeWholeScores':True}))
