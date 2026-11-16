from pathlib import Path
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
assert read(E/'cpu-native8-r2/run.json')['state']=='COMPLETE_CPU_ONLY_NATIVE8_FULL4_NOT_QUALIFIED'
assert read(B/'english-asr-specialist-r1/score.json')['state']=='REJECT_ENGLISH_SPECIALIST_CLIP_CONTRAST_NO_PARAMETER_GRID'
assert read(E/'cpu-pcm-dualroute-r2/result.json')['state']=='PASS_BILINGUAL_ACTUAL_CPU_INCREMENTAL_OFFLINE_INTEGRATION_NOT_QUALITY_QUALIFIED'
files=[]
for folder in ['cpu-native8-r2','all-cpu-full4-composition-r1','english-asr-specialist-r1','cpu-pcm-candidate-r2','cpu-pcm-candidate-r3']:
 for p in (B/folder).rglob('*'):
  if p.is_file() and p.suffix in ['.json','.py','.log','.txt']:files.append({'source':str(p),'name':folder+'/control/'+p.relative_to(B/folder).as_posix()})
for folder in ['cpu-native8-r2','all-cpu-full4-composition-r1','english-asr-specialist-run-r1','cpu-pcm-dualroute-r1','cpu-pcm-dualroute-r2','cpu-pcm-reader-collision-r1','cpu-pcm-reader-collision-fix-r1','cpu-pcm-short-temp-proof-r1','cpu-app-schema-test-r1']:
 for p in (E/folder).rglob('*'):
  if p.is_file() and p.suffix in ['.json','.log','.py'] and not any('native.log'==n for n in p.parts):files.append({'source':str(p),'name':folder+'/run/'+p.relative_to(E/folder).as_posix()})
for name in ['prepare_english_specialist_20261116.py','freeze_english_specialist_runtime_20261116.py','run_fixed_english_after_speaker_20261116.py','audit_english_farfield_errors_20261116.py',
 'prepare_all_cpu_full4_composition_20261116.py','score_all_cpu_full4_20261116.py','run_cpu_pcm_dualroute_20261116.py','reproduce_pcm_windows_reader_collision_20261116.py',
 'check_pcm_windows_commit_fix_20261116.py','prepare_cpu_pcm_dualroute_fix_20261116.py','prepare_cpu_pcm_short_temporary_fix_20261116.py','prepare_cpu_internal_app_fixture_20261116.py',
 'prepare_cpu_internal_app_fixture_frozen_20261116.py','prepare_cpu_internal_app_fixture_frozen_r2_20261116.py','run_cpu_application_schema_20261116.py','prepare_cpu_checkpoint40_20261116.py']:
 p=Path('work')/name;assert p.is_file();files.append({'source':str(p),'name':'preparation/'+name})
sources=['src/english_specialist_cpu_worker_20261116.py','src/run_english_specialist_cpu_20261116.py','src/score_english_specialist_cpu_20261116.py',
 'src/compose_cpu_native8_full4_20261116.py','src/score_all_cpu_full4_summary_20261116.py','src/companion_local_pcm_session_20261114.py',
 'src/companion_cpu_guarded_stage_20261116.py','src/companion_local_moss_cpu_pipeline_20261116.py']
config={'revision':40,'evidenceDirectory':'evidence/20261116-all-cpu-meeting-proofs-and-windows-intake-fixes','commitMessage':'Verify full CPU speaker journals and live/offline decoding; fix Windows state commits and bounded intake ownership',
 'sources':sources,'closedDirectories':[],'files':files,'claims':{'state':'FULL4_CPU_SPEAKER_AND_BILINGUAL_LIVE_OFFLINE_PASS_QUALITY_FAILED_APPLICATION_ENTRY_IN_PROGRESS',
 'fullCpuSpeakerRecordings':4,'allCpuAsrSpeakerQualityScoresRetained':True,'whisperFixedEnglishContrastRejected195Of709':True,'newParameterGrid':False,
 'actualCpuIncrementalAndOfflineFinalTextExact':True,'windowsReaderCollisionReproducedAndFixed':True,'windowsLongTempPathFailureReproducedAndFixed':True,
 'actualAppSchemaIntegrationComplete':False,'liveAppSchemaTestOutputsExcluded':True,'newWeightTraining':False,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,'installedPackageChanged':False}}
Path('work/cpu-checkpoint40.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(len(files))
