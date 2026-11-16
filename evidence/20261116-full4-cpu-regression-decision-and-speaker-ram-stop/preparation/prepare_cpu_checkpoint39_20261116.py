from pathlib import Path
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
files=[]
for folder in ['cpu-fixed-whole-r2','cpu-native8-r1']:
 for p in (B/folder).rglob('*'):
  if p.is_file() and p.suffix in ['.json','.py','.txt']:files.append({'source':str(p),'name':folder+'/control/'+p.relative_to(B/folder).as_posix()})
for folder in ['cpu-native8-r1']:
 for name in ['run.json','inference-state.json','worker.log','control.json']:
  p=E/folder/name
  if p.is_file():files.append({'source':str(p),'name':folder+'/'+name})
for name in ['cpu-runtime-abi-control.json']:
 p=B/'cpu-pcm-candidate-r1'/name
 if p.exists():files.append({'source':str(p),'name':'cpu-pcm-candidate-r1/'+name})
for name in ['publisher-metadata.json','source.json','protocol.json']:
 p=B/'english-asr-specialist-r1'/name
 if p.exists():files.append({'source':str(p),'name':'english-asr-specialist-r1/'+name})
for name in ['run_cpu_full4_scoring_20261116.py','fix_full_cpu_reference_alias_20261116.py','record_cpu_full4_decision_20261116.py','prepare_cpu_native8_recovery_20261116.py','probe_cpu_only_runtime_abi_20261116.py','fetch_english_specialist_metadata_20261116.py','prepare_english_specialist_20261116.py','prepare_cpu_checkpoint39_20261116.py']:
 p=Path('work')/name;assert p.is_file();files.append({'source':str(p),'name':'preparation/'+name})
config={'revision':39,'evidenceDirectory':'evidence/20261116-full4-cpu-regression-decision-and-speaker-ram-stop',
 'commitMessage':'Retain complete four-meeting CPU ASR and reject universal regression; correct reference aliases without changing gates',
 'sources':['src/score_cpu_fixed_whole_summary_20261116.py','src/run_cpu25_nemotron_20261116.py'],
 'closedDirectories':[{'directory':str(E/'cpu-fixed-whole-r2'),'stateFile':'run.json','requiredState':'COMPLETE_CPU_FIXED_CHUNKS_COMPOSITION_AND_SCORING_PENDING','label':'cpu-fixed-whole-r2/run'}],
 'files':files,'claims':{'state':'FULL4_CPU_ASR_COMPLETE_UNIVERSAL_CANDIDATE_REJECTED_CHINESE_BASELINE_PROTECTED',
  'originalFullInputs':4,'completeNaturalEosChunks':290,'referenceAliasSummaryErrorRetainedAndCorrected':True,'rawMultiVoiceDERRemainsAuthoritative':True,
  'cpuSpeaker61SecondsCabiAndCliPassed':True,'cpuSpeakerFullInputsComplete':False,'cpuSpeakerWholeStoppedByActualWindowsLowMemory':True,
  'newWeightTraining':False,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,'installedPackageChanged':False}}
Path('work/cpu-checkpoint39.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(len(files))
