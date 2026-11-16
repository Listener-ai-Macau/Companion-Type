from pathlib import Path
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-fixed-whole-r1')
B={'revision':36,'evidenceDirectory':'evidence/20261116-full-cpu-resource-stop-resume-and-speaker-preparation','commitMessage':'Preserve CPU resource-stop39 inputs and add exact resume plus CPU-only native8 control',
 'sources':['src/'+n for n in ['cpu_fixed_chunks_worker_20261116.py','run_cpu_fixed_chunks_20261116.py','compose_cpu_fixed_whole_20261116.py','score_cpu_fixed_whole_summary_20261116.py','cpu25_nemotron_wrapper_20261116.py','run_cpu25_nemotron_20261116.py']],
 'closedDirectories':[{'directory':str(E),'stateFile':'run.json','requiredState':'INCOMPLETE_CPU_FIXED_CHUNKS_RETAINED','label':'closed-full-r1-resource-stop'}],
 'files':[], 'claims':{'state':'CPU_FULL39_RETAINED_RESOURCE_RECOVERED_EXACT_RESUME_SOURCE_AND_CPU_SPEAKER_CONTROL_FROZEN',
  'cpuPercent':25,'computeThreadsMaximum':4,'privateLimitBytes':2147483648,'originalActualLowMemoryGuardUnchanged':True,
  'retainedFullInputWindows':39,'retainedSourceSeconds':1170,'privateGuardNotReached':True,'actualWindowsLowMemoryStop':True,
  'activeFullAsrOutputsExcluded':True,'wholeMeetingResults':0,'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False,
  'cpuSpeakerNeuralExecutionDuringPreparation':False,'cpuSpeakerBinaryOnly':True}}
for folder in [BASE/'cpu-fixed-whole-r1',BASE/'cpu-fixed-whole-r2',BASE/'cpu-native8-r1']:
 for p in folder.iterdir():
  if p.is_file():B['files'].append({'source':str(p),'name':folder.name+'/'+p.name})
for n in ['freeze_full_cpu_speaker_bindings_20261116.py','freeze_full_cpu_composition_source_20261116.py','fix_full_cpu_scoring_rttm_fidelity_20261116.py','prepare_cpu_fixed_resume_20261116.py','prepare_cpu25_nemotron_20261116.py','refresh_cpu_day_20261116.py',Path(__file__).name]:B['files'].append({'source':str(Path('work')/n),'name':'preparation/'+n})
for p in Path('work/upstream-nemo-cpu-v030').iterdir():
 if p.is_file():B['files'].append({'source':str(p),'name':'upstream-thread-proof/'+p.name})
Path('work/cpu-checkpoint36.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Prepared r36; active full-r2 neural outputs excluded.')
