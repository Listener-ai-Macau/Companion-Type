"""Assemble one isolated app-compatible CPU candidate only after real native8 CPU proof."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114');N=E/'joint-architecture-r1/cpu-native8-r2';OUT=E/'joint-architecture-r1/cpu-internal-app-fixture-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert read(N/'run.json')['state']=='COMPLETE_CPU_ONLY_NATIVE8_FULL4_NOT_QUALIFIED' and read(N/'run.json')['cpu61ControlPassed']
assert not OUT.exists();OUT.mkdir();src=OUT/'src';src.mkdir();assets=OUT/'runtime';assets.mkdir();controls=OUT/'controls';controls.mkdir()
names=['companion_cpu_guarded_stage_20261116.py','companion_local_moss_cpu_pipeline_20261116.py','companion_local_moss_cpu_stream_20261116.py','companion_moss_speaker_document_20261116.py',
 'companion_local_moss_cpu_worker_20261116.py','run_local_moss_cpu_decoder_20261116.py','companion_moss_raw_output_20261116.py',
 'cpu_window_joint_worker_20261116.py','moss_windows_resource_limits_20261104.py','practical_io_20261107.py','companion_local_pcm_session_20261114.py',
 'companion_local_meeting_pipeline_20261115.py','companion_windows_power_request_20261115.py','run_moss_overnight_20261115.py',
 'cpu25_nemotron_wrapper_20261116.py','practical_nemotron_worker_20261107.py','practical_nemotron_cli_control_20261107.py',
 'companion_exclusive_journal_20261114.py','companion_local_cache_audit_20261115.py']
for name in names:shutil.copyfile(S/name,src/name);assert sha(src/name)==sha(S/name)
hook=src/'cache-audit-hook';hook.mkdir();original_hook=E/'local-package-r8/src/cache-audit-hook/sitecustomize.py';assert sha(original_hook)=='f4cd1afbfe0187edd77ae84e05c0a0cca2caca48a1d318cb0ae8e0716f061a21';shutil.copyfile(original_hook,hook/'sitecustomize.py')
pc=controls/'pcm';pc.mkdir();B=read(BASE/'cpu-pcm-candidate-r3/binding.json');runtime=assets/'moss-cpu';runtime.mkdir();oldroot=Path(B['library']).parent
for row in B['runtimeFiles']:
 target=runtime/Path(row['file']).relative_to(oldroot);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(row['file'],target);assert sha(target)==row['sha256'];row['file']=str(target)
B['library']=str(runtime/'transcribe.dll')
pyroot=assets/'moss-python';pyroot.mkdir();oldpy=Path(B['pythonRoot'])
for row in B['pythonFiles']:
 target=pyroot/Path(row['file']).relative_to(oldpy);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(row['file'],target);assert sha(target)==row['sha256'];row['file']=str(target)
B['pythonRoot']=str(pyroot);B['helpers']={str(src/Path(p).name):digest for p,digest in B['helpers'].items()};assert all(sha(p)==h for p,h in B['helpers'].items())
(pc/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');shutil.copyfile(BASE/'cpu-pcm-candidate-r3/runtime-contract.json',pc/'runtime-contract.json');assert sha(pc/'runtime-contract.json')==B['runtimeContractSha256']
nc=controls/'native8';nc.mkdir();P=read(N/'protocol.json');NB=read(N/'binding.json');assert NB['wrapperSha256']==sha(src/'cpu25_nemotron_wrapper_20261116.py')
nr=assets/'native8-cpu';nr.mkdir();oldnative=Path(P['nativeLibrary']).parent
for name,digest in P['nativeFiles'].items():shutil.copyfile(oldnative/name,nr/name);assert sha(nr/name)==digest
shutil.copyfile(P['nativeExe'],nr/Path(P['nativeExe']).name);assert sha(nr/Path(P['nativeExe']).name)==P['nativeExeSha256']
P['nativeLibrary']=str(nr/Path(P['nativeLibrary']).name);P['nativeExe']=str(nr/Path(P['nativeExe']).name);P['probabilityCacheRoot']='SET_INSIDE_EACH_OWNED_JOB'
NB['helperSha256']={str(src/Path(p).name):digest for p,digest in NB['helperSha256'].items()};assert all(sha(p)==h for p,h in NB['helperSha256'].items())
proofdir=nc/'thread-default-proof';proofdir.mkdir()
for row in NB['threadDefaultSourceProof']:
 target=proofdir/Path(row['file']).name;shutil.copyfile(row['file'],target);assert sha(target)==row['sha256'];row['file']=str(target)
for name,value in [('protocol.json',P),('binding.json',NB)]:
 (nc/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(N/'run.json',nc/'cpu-execution-proof.json')
# Preserve the native distribution's license tree, without copying any GPU library.
native_distribution=oldnative.parent
for folder in ['licenses','LICENSE','THIRD_PARTY_NOTICES.md']:
 path=native_distribution/folder
 if path.is_dir():shutil.copytree(path,nr/folder)
 elif path.is_file():shutil.copyfile(path,nr/folder)
bundle={'schema':'companion.local-moss-cpu-bundle.v1','neuralDeadline':'2026-11-16T15:40:00+08:00','internalQualityRejectedModelFixture':True,'createdAt':datetime.now().astimezone().isoformat(),'sourceFiles':{},
 'workRoot':str(OUT/'jobs'),'streamRoot':str(OUT/'streams'),'cpuPcmControl':str(pc),'cpuSpeakerProtocol':str(nc/'protocol.json'),
 'cpuSpeakerBinding':str(nc/'binding.json'),'cpuSpeakerExecutionProof':str(nc/'cpu-execution-proof.json'),
 'postprocessSitePackages':'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages',
 'qualityQualified':False,'productDefaultChanged':False,'installedPackageChanged':False,'sourceUploaded':False,'localOnly':True,
 'runtime':'One model stage at a time; CPU25%/4 native threads, family2GiB and actual Windows low-memory protection; live source persists independently of decoding.'}
for root in [src,controls]:
 for path in root.rglob('*'):
  if path.is_file() and path.suffix!='.pyc':bundle['sourceFiles'][str(path)]=sha(path)
(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'jobs').mkdir();(OUT/'streams').mkdir()
paths=[Path(B['model']['file']),Path(P['model'])]+[p for p in assets.rglob('*') if p.is_file()]
package={'schema':'companion.local-meeting-package.v1','program':sys.executable,'programSha256':sha(sys.executable),
 'entryScript':str(src/'companion_local_moss_cpu_pipeline_20261116.py'),'entryScriptSha256':sha(src/'companion_local_moss_cpu_pipeline_20261116.py'),
 'args':['-u','{entry}','--manifest','{manifest}','--bundle',str(OUT/'bundle.json')],'workRoot':str(OUT/'jobs'),
 'assets':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths],
 'qualityQualified':False,'saleQualified':False,'installedAsDefault':False,'cpuOnlyCandidate':True}
(OUT/'package.json').write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
receipt={'state':'INTERNAL_CPU_APP_SCHEMA_FIXTURE_FROZEN_NO_RELEASE_PROMOTION','package':str(OUT/'package.json'),'packageSha256':sha(OUT/'package.json'),
 'bundleSha256':sha(OUT/'bundle.json'),'sourceFiles':len(bundle['sourceFiles']),'sourceSnapshotExact':True,'oldPackageAndSettingsUnchanged':True,'qualityQualified':False,
 'sourceModelsSharedReadOnlyWithoutCopy':True,'cpuPcmNativeContractUnchanged':True,'newNeuralCallsDuringAssembly':0,'requiresActualEntryAndLiveCacheReuseChecks':True}
target=BASE/'cpu-pcm-candidate-r3/internal-app-fixture.json';target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
