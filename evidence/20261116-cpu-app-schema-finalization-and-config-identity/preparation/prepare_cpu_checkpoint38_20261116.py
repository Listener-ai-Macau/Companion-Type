from pathlib import Path
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
B={'revision':38,'evidenceDirectory':'evidence/20261116-cpu-app-schema-finalization-and-config-identity','commitMessage':'Prepare CPU app stream and finalization entry with exact words and compatible cache identity',
 'sources':['src/'+n for n in ['companion_local_moss_cpu_worker_20261116.py','companion_moss_speaker_document_20261116.py','companion_local_moss_cpu_stream_20261116.py','companion_local_moss_cpu_pipeline_20261116.py']],
 'closedDirectories':[], 'files':[], 'claims':{'state':'CPU_APP_SCHEMA_STREAM_FINALIZATION_AND_PACKAGE_SOURCE_PREPARED_EXECUTION_PENDING',
  'cpuPercent':25,'nativeThreads':4,'familyPrivateBytes':2147483648,'actualWindowsLowMemoryStop':True,'cpuCandidateActualNeuralIntegrationExecuted':False,
  'fullBundleIdentityInFinalCacheKey':True,'existingMismatchedCacheRejectedBeforeModelInit':True,'wordsPreservedByFinalizationInvariant':True,
  'originalNativeArtifactWriteAuditPropagated':True,'optionalGpuPluginExcludedCpuBytesUnchanged':True,
  'activeFull4AsrAndSourceConversionOutputsExcluded':True,'newWeightTraining':False,'productDefaultChanged':False,'installedPackageChanged':False,'qualityQualified':False,'saleQualified':False}}
for p in (BASE/'cpu-pcm-candidate-r1').iterdir():
 if p.is_file():B['files'].append({'source':str(p),'name':'cpu-pcm-candidate-r1/'+p.name})
for n in ['freeze_cpu_pcm_cache_identity_20261116.py','make_cpu_runtime_identity_portable_20261116.py','prepare_cpu_model_package_20261116.py',
 'prepare_cpu_extended_validation_20261116.py',Path(__file__).name]:B['files'].append({'source':str(Path('work')/n),'name':'preparation/'+n})
Path('work/cpu-checkpoint38.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Prepared r38; source/config snapshot only, no active outputs/binaries/audio.')
