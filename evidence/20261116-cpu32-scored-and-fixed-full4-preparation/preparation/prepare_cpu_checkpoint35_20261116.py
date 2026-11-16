from pathlib import Path
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/stagea-cpu-composition-r2')
B={'revision':35,'evidenceDirectory':'evidence/20261116-cpu32-scored-and-fixed-full4-preparation','commitMessage':'Record complete CPU32 ASR gains and freeze continuous full4 CPU composition',
 'sources':['src/cpu_fixed_chunks_worker_20261116.py','src/run_cpu_fixed_chunks_20261116.py'],
 'closedDirectories':[{'directory':str(E),'stateFile':'run.json','requiredState':'COMPLETE_CPU_WINDOW_COHORT_COMPOSITION_AND_SCORING_PENDING','label':'closed-stagea-cpu-composition-r2'}],
 'files':[], 'claims':{'state':'CPU32_COMPLETE_SCORED_IMPROVED_NOT_QUALIFIED_FULL4_SOURCE_FROZEN','cpuPercent':25,'computeThreadsMaximum':4,'privateLimitBytes':2147483648,
  'fullMeetingActiveOutputsExcluded':True,'wholeMeetingResults':0,'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False}}
for folder in [BASE/'stagea-cpu-composition-r2',BASE/'cpu-fixed-whole-r1']:
 for p in folder.iterdir():
  if p.is_file():B['files'].append({'source':str(p),'name':folder.name+'/'+p.name})
for n in ['record_cpu_window_result_20261116.py','prepare_cpu_fixed_whole_20261116.py',Path(__file__).name]:B['files'].append({'source':str(Path('work')/n),'name':'preparation/'+n})
Path('work/cpu-checkpoint35.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Prepared explicit r35 paths; active full4 outputs excluded.')
