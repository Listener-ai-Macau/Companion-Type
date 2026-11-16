from pathlib import Path
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
B={'revision':37,'evidenceDirectory':'evidence/20261116-cpu-only-durable-pcm-candidate-preparation','commitMessage':'Prepare CPU-only durable incremental and offline MOSS consumer with preserved source and final-priority drafts',
 'sources':['src/'+n for n in ['companion_moss_raw_output_20261116.py','companion_local_moss_cpu_worker_20261116.py','run_local_moss_cpu_decoder_20261116.py']],
 'closedDirectories':[], 'files':[], 'claims':{'state':'CPU_ONLY_DURABLE_PCM_CANDIDATE_PREPARED_ACTUAL_NEURAL_INTEGRATION_PENDING',
  'cpuPercent':25,'nativeThreads':4,'privateBytes':2147483648,'originalActualLowMemoryGuardUnchanged':True,
  'sourceRuntimeBytesUnchangedCpuOptionalGpuPluginExcluded':True,'actualCpuPcmNeuralCalls':0,'parserExactOn32ActualOutputs':True,
  'realPcmSchedulerControlUsedNoNeuralModelAndOnlyAnExplicitRejectedEmptyTechnicalResult':True,
  'activeFull4AsrOutputsExcluded':True,'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False}}
for p in (BASE/'cpu-pcm-candidate-r1').iterdir():
 if p.is_file():B['files'].append({'source':str(p),'name':'cpu-pcm-candidate-r1/'+p.name})
for n in ['lexical-error-audit.json']:
 p=BASE/'stagea-cpu-composition-r2'/n;B['files'].append({'source':str(p),'name':'closed-cpu32-diagnostic/'+n})
for n in ['audit_cpu32_lexical_errors_20261116.py','prepare_cpu_pcm_candidate_20261116.py','check_cpu_pcm_parser_20261116.py','check_cpu_pcm_scheduling_20261116.py',
 'prepare_cpu_pcm_dualroute_20261116.py','run_cpu_pcm_dualroute_20261116.py','freeze_cpu_pcm_actual_test_20261116.py','record_cpu_product_preparation_20261116.py','refresh_cpu_day_20261116.py',Path(__file__).name]:
 B['files'].append({'source':str(Path('work')/n),'name':'preparation/'+n})
Path('work/cpu-checkpoint37.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Prepared r37, excluding binaries/audio/active neural outputs.')
