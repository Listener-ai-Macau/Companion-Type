from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
C=B/'cpu-pcm-candidate-r5';assert not C.exists();C.mkdir();previous=B/'cpu-pcm-candidate-r4';binding=read(previous/'binding.json')
old=subprocess.check_output(['git','-C',str(R/'model-research'),'show','f7c667cdb4c7cc79f1fc3c6631325926a8e983be:src/companion_local_moss_cpu_worker_20261116.py']).decode('utf-8');new=(S/'companion_local_moss_cpu_worker_20261116.py').read_text(encoding='utf-8')
core=lambda text:text.split('    job=jobs[0];pcm=',1)[1].split("    state['completed'].append",1)[0]
assert core(old)==core(new)
binding.update(workerSha256=sha(S/'companion_local_moss_cpu_worker_20261116.py'),modelIdleReleaseSeconds=15,
 idlePolicyScope='Unload this worker native model after15s without schedulable work; retain the worker, exact source PCM and immutable inference results. Reload only when work arrives and original3.18GiB start gate permits. No model math or native preset change.')
shutil.copyfile(previous/'runtime-contract.json',C/'runtime-contract.json');assert sha(C/'runtime-contract.json')==binding['runtimeContractSha256']
(C/'binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
proof={'state':'CPU_IDLE_MODEL_RELEASE_FIXED_BEFORE_ACTUAL_PAUSE_RESUME_INTEGRATION_TEST','at':datetime.now().astimezone().isoformat(),
 'oldProtectedSourceCommit':'f7c667cdb4c7cc79f1fc3c6631325926a8e983be','oldWorkerSha256':hashlib.sha256(old.encode()).hexdigest(),'newWorkerSha256':sha(S/'companion_local_moss_cpu_worker_20261116.py'),
 'sourcePcmNativeSessionGenerationAndSaveCoreUnchanged':True,'generationCoreSha256':hashlib.sha256(core(new).encode()).hexdigest(),'idleReleaseSeconds':15,
 'rootCause':'The existing follow loop can keep an already loaded model resident while source input is paused for the3h follow window. Existing model process ends on finalization, but no prior idle model release exists.',
 'keepRule':['Actual model closes during input pause and its resident weight mapping is released.','Worker RSS drops by at least512MiB during the pause, while no new neural call occurs.','Resume reloads this model, preserves accepted draft files and every original audio sample.','Final text equals the previous protected CPU app run, finalization reuses the new stream cache without ASR rerun.'],
 'existingFixtureR3Preserved':True,'noCrossVersionCacheMigrationClaim':True,'productDefaultChanged':False,'qualityQualified':False,'newNeuralCalls':0}
(C/'idle-policy-protocol.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':proof['state'],'workerSha256':binding['workerSha256']}))
