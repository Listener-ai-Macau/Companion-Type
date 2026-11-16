"""Freeze an internal application-schema fixture; no release/default promotion."""
from pathlib import Path
import argparse,hashlib
parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,default=1);parser.add_argument('--pcm-control',default='cpu-pcm-candidate-r2');args=parser.parse_args()
source=Path('work/prepare_cpu_model_package_20261116.py');text=source.read_text(encoding='utf-8')
changes={
 "N=E/'joint-architecture-r1/cpu-native8-r1';OUT=E/'local-moss-cpu-package-r1'":"N=E/'joint-architecture-r1/cpu-native8-r2';OUT=E/'joint-architecture-r1/cpu-internal-app-fixture-r"+str(args.revision)+"'",
 "BASE/'cpu-pcm-candidate-r1":"BASE/'"+args.pcm_control,
 "names=['companion_local_moss_cpu_pipeline_20261116.py'":"names=['companion_local_paths_20261116.py','companion_cpu_guarded_stage_20261116.py','companion_local_moss_cpu_pipeline_20261116.py'",
 "'schema':'companion.local-moss-cpu-bundle.v1','createdAt'":"'schema':'companion.local-moss-cpu-bundle.v1','neuralDeadline':'2026-11-16T15:40:00+08:00','internalQualityRejectedModelFixture':True,'createdAt'",
 "CPU_APP_SCHEMA_PACKAGE_ASSEMBLED_ACTUAL_APP_ENTRY_PENDING":"INTERNAL_CPU_APP_SCHEMA_FIXTURE_FROZEN_NO_RELEASE_PROMOTION",
 "'"+args.pcm_control+"/app-package-preparation.json'":"'"+args.pcm_control+"/internal-app-fixture.json'"}
for before,after in changes.items():
 assert text.count(before)>=1,before;text=text.replace(before,after)
target=Path('work/prepare_cpu_internal_app_fixture_frozen_r'+str(args.revision)+'_20261116.py');assert not target.exists();target.write_text(text,encoding='utf-8')
compile(text,str(target),'exec');exec(compile(text,str(target),'exec'),{'__name__':'__main__','__file__':str(target)})
