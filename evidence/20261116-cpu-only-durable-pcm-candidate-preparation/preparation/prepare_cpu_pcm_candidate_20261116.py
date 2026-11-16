from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';BASE=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=BASE/'cpu-pcm-candidate-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-pcm-candidate-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not E.exists();C.mkdir();E.mkdir();folder=E/'runtime-cpu-only';folder.mkdir()
old=read(BASE/'cpp-r1/runtime-ready.json');python=read(BASE/'cpp-r1/python-source.json');model=read(BASE/'cpp-r1/model-ready.json');files=[]
root=Path(next(r['file'] for r in old['files'] if Path(r['file']).name=='transcribe.dll')).parent
for row in old['files']:
 source=Path(row['file']);assert sha(source)==row['sha256']
 if 'vulkan' in source.name.lower() or source.name=='contract.json':continue
 target=folder/source.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==row['sha256']
 files.append({'file':str(target),'sha256':row['sha256'],'bytes':target.stat().st_size})
contract={'baseArchiveSha256':old['runtimeSha256'],'change':'Omit optional Vulkan plugin from this new isolated candidate directory; all retained CPU/native bytes identical. Preserve all original files and licenses.',
 'nativeVersion':'0.4.2','nativeCommit':'275cd50d2c4104c204009a197ac091b9687668e5','files':files,'originalRuntimeUnchanged':True}
(E/'runtime-contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
B={'at':datetime.now().astimezone().isoformat(),'workerSha256':sha(S/'companion_local_moss_cpu_worker_20261116.py'),'runnerSha256':sha(S/'run_local_moss_cpu_decoder_20261116.py'),
 'workerPython':'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe','ownerCpuBudgetPermission':read(BASE/'cpu-fixed-whole-r2/binding.json')['ownerCpuBudgetPermission'],
 'neuralDeadline':'2026-11-16T15:40:00+08:00','runtimeFiles':files,'runtimeContractSha256':sha(E/'runtime-contract.json'),'library':str(folder/'transcribe.dll'),
 'pythonFiles':python['files'],'pythonRoot':python['root'],'model':model,
 'helpers':{str(S/n):sha(S/n) for n in ['moss_windows_resource_limits_20261104.py','practical_io_20261107.py','companion_local_pcm_session_20261114.py','cpu_window_joint_worker_20261116.py','score_joint_whole_meetings_20261115.py']},
 'scheduler':'Complete30s block first; at most one first<=5s draft for each open block. Never decode every growing prefix; all original PCM and revisions retained.',
 'scope':'Candidate for the existing durable upload-incremental and sealed/offline intake. Transcript completion only; stable whole-source speaker journal remains a separate final stage.',
 'cpuPercent':25,'nativeThreads':4,'privateBytes':2147483648,'qualityQualified':False,'newWeightTraining':False,'productDefaultChanged':False,'installedPackageChanged':False}
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(C/'runtime-contract.json').write_bytes((E/'runtime-contract.json').read_bytes())
print(json.dumps({'control':str(C),'candidate':str(E),'runtimeFiles':len(files),'cpuRuntimeBytes':sum(r['bytes'] for r in files),'neuralCalls':0,'installedPackageChanged':False}))
