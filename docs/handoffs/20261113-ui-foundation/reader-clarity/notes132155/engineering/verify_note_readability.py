from pathlib import Path
from datetime import datetime
import argparse,json,os,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109'
parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=int,default=1);args=parser.parse_args();assert 1<=args.attempt<=5
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');Q=O/('note-readability-followup'+('' if args.attempt==1 else '-r'+str(args.attempt)));Q.mkdir(exist_ok=False)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,1536*1024**2)
code="""const {build}=require('esbuild'),{spawnSync}=require('child_process'),path=require('path'),{pathToFileURL}=require('url');
(async()=>{for(const name of NAMES){const output=path.resolve('.cache/software-contracts/'+name+'-note-readability.mjs');await build({entryPoints:['tools/'+name+'.tsx'],outfile:output,bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',tsconfig:'apps/mobile/tsconfig.json',loader:{'.css':'empty'}});const r=spawnSync(process.execPath,['--import',pathToFileURL(path.resolve('tools/component_test_environment.mjs')).href,output],{encoding:'utf8',windowsHide:true});process.stdout.write(r.stdout||'');process.stderr.write(r.stderr||'');if(r.status)process.exit(r.status);}})().catch(e=>{console.error(e);process.exitCode=1});"""
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='RUNNING',steps=[])
commands=[('windows-contracts',S,['node','-e',code.replace('NAMES',json.dumps(['test_note_readability','test_transcript_reading_20261103','test_long_minutes_reading','test_short_minutes_evidence']))]),('mobile-contracts',A,['node','-e',code.replace('NAMES',json.dumps(['test_mobile_minutes_reading']))]),('windows-types',S,['node','node_modules/typescript/bin/tsc','-p','apps/windows/tsconfig.json']),('mobile-types',A,['node','node_modules/typescript/bin/tsc','-p','apps/mobile/tsconfig.json'])]
for name,root,command in commands:
 with(Q/(name+'.log')).open('xb')as log:run=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW,env={**os.environ,'COMPANION_TEST_PUBLIC_SOURCE_MINUTES':str(O/'public-source-full30-127/minutes.json')})
 record['steps'].append(dict(name=name,exitCode=run.returncode));(Q/'result.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(name,run.returncode,flush=True)
 if run.returncode:raise RuntimeError((Q/(name+'.log')).read_text(errors='replace')[-3500:])
record.update(state='NOTE_HIERARCHY_AND_TRANSCRIPT_READING_CONTRACTS_PASSED',finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'));(Q/'result.json').write_text(json.dumps(record,indent=2),encoding='utf8')
