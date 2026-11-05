from pathlib import Path
import subprocess,os,time,json,sys
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=root/'recovered-software050'
out=root/'docs/handoffs/20261105-windows-content051';cache=Path('E:/CodexData/Companion/.build-cache/windows051');cache.mkdir(parents=True,exist_ok=True)
kind=sys.argv[1] if len(sys.argv)>1 else 'check'
args={'check':['check','--lib'],'tests':['test','--lib','content051','--','--test-threads=1'],'release':['build','--release','--bin','companion-type'],'release-all':['build','--release']}[kind]
env=os.environ.copy();env.update(CARGO_BUILD_JOBS='1',CARGO_INCREMENTAL='0',CARGO_TARGET_DIR=str(cache/'target'),RAYON_NUM_THREADS='2',TEMP=str(cache),TMP=str(cache))
if kind=='tests':
    env['COMPANION_CONTENT_EXPORT_FIXTURE_DIR']=str(out/('native-files-'+str(time.time_ns())))
pre=subprocess.run([sys.executable,str(root/'tools/check_type_build_target.py'),'--target-dir',str(cache/'target'),'--project',str(s/'apps/windows/src-tauri'),'--source-dir',str(s)],capture_output=True,text=True,encoding='utf8',errors='replace')
(out/(kind+'-preflight.json')).write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
start=time.perf_counter();logpath=out/('cargo-'+kind+'.log')
with logpath.open('wb') as log:r=subprocess.run(['cargo',*args,'--offline','--locked'] if kind!='tests' else ['cargo','test','--offline','--locked','--lib','content051','--','--test-threads=1'],cwd=s/'apps/windows/src-tauri',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
record={'kind':kind,'exitCode':r.returncode,'wallSeconds':round(time.perf_counter()-start,2),'jobs':1,'modelsRun':False,'cache':str(cache)}
(out/('cargo-'+kind+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record));print(logpath.read_text(encoding='utf8',errors='replace')[-10000:]);raise SystemExit(r.returncode)
