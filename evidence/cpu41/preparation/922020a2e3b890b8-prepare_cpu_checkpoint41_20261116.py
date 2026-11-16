from pathlib import Path
import hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src';sys.path.insert(0,str(S))
from companion_local_paths_20261116 import local_path
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
assert read(E/'cpu-app-schema-test-r3/result.json')['state']=='PASS_ACTUAL_CPU_BACKEND_APP_SCHEMAS_STREAM_OFFLINE_FINALIZATION_AND_CACHE_NOT_QUALITY_QUALIFIED'
files=[]
def take(p,label):
 name=label+'/'+hashlib.sha256(str(p).encode()).hexdigest()[:16]+'-'+p.name
 assert len(str(M/'evidence/cpu41'/name))<240
 files.append({'source':str(p),'name':name})
for folder in ['cpu-app-schema-test-r2','cpu-app-schema-test-r3','cpu-long-path-scheme-r1']:
 for p in local_path(E/folder).rglob('*'):
  if p.is_file() and p.suffix in ['.json','.log']:take(p,folder)
for folder in ['cpu-pcm-candidate-r4','qwen-cpu-port-r1','meeting-domain-data-r1']:
 for p in (B/folder).glob('*'):
  if p.is_file() and p.suffix=='.json' and p.name not in ['data-preparation.json','score.json']:take(p,folder)
fixture=E/'cpu-internal-app-fixture-r3'
for p in fixture.rglob('*'):
 if p.is_file() and p.suffix in ['.json','.py'] and not p.name.endswith('.pyc'):take(p,'frozen-internal-fixture')
for name in ['prepare_cpu_internal_app_fixture_20261116.py','prepare_cpu_internal_app_fixture_frozen_r3_20261116.py','run_cpu_application_schema_20261116.py',
 'record_cpu_application_result_20261116.py','prepare_meeting_domain_data_plan_20261116.py','fetch_meeting_domain_data_20261116.py',
 'prepare_qwen_cpu_port_20261116.py','freeze_qwen_cpu_runtime_20261116.py','prepare_cpu_checkpoint41_20261116.py']:
 p=Path('work')/name;assert p.is_file();take(p,'preparation')
config={'revision':41,'evidenceDirectory':'evidence/cpu41','commitMessage':'Verify actual CPU app stream/offline/cache schemas with continuous speakers; preserve deep Windows cache fixes',
 'sources':['src/qwen_cpu_port_worker_20261116.py','src/run_qwen_cpu_port_20261116.py','src/score_qwen_cpu_port_20261116.py'],
 'closedDirectories':[],'files':files,'claims':{'state':'ACTUAL_CPU_BACKEND_APP_SCHEMAS_PASS_QUALITY_UNQUALIFIED_QWEN_PORT_AND_TRAINING_DATA_PREPARATION_PENDING',
 'actualBackendSchemaCases':2,'freshOfflineAndIncrementalFinalTextExactlyEqual':True,'acceptedAsrCachePreservedAndReused':True,
 'completedReloadAddsNoNeuralStage':True,'actualCpuSpeakerJournalApplied':True,'nativeUiAndCardTested':False,
 'qwenCpuPortNeuralOutputsExcludedWhileRunning':True,'trainingDataLiveOutputsExcluded':True,'newWeightTraining':False,
 'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,'installedPackageChanged':False}}
Path('work/cpu-checkpoint41.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(len(files))
