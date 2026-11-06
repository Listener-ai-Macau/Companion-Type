from pathlib import Path
import subprocess,os,time,json,sys
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'recovered-software050';out=r/'docs/handoffs/20261106-material-exports052';cache=Path('E:/CodexData/Companion/.build-cache/windows051')
kind=sys.argv[1] if len(sys.argv)>1 else 'check'
argv={'check':['check','--lib'],'tests':['test','--lib','content05','--','--test-threads=1'],'release':['build','--release']}[kind]
env=os.environ.copy();env.update(CARGO_BUILD_JOBS='1',CARGO_INCREMENTAL='0',CARGO_TARGET_DIR=str(cache/'target'),RAYON_NUM_THREADS='2',TEMP=str(cache),TMP=str(cache))
if kind=='tests':env['COMPANION_CONTENT_EXPORT_FIXTURE_DIR']=str(out/('native-files-'+str(time.time_ns())))
pre=subprocess.run([sys.executable,str(r/'tools/check_type_build_target.py'),'--target-dir',str(cache/'target'),'--project',str(s/'apps/windows/src-tauri'),'--source-dir',str(s)],capture_output=True,text=True,encoding='utf8',errors='replace')
(out/(kind+'-preflight.json')).write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
started=time.perf_counter();logpath=out/('cargo-'+kind+'-'+str(time.time_ns())+'.log')
cmd=['cargo',*argv[:1],'--offline','--locked',*argv[1:]]
with logpath.open('xb') as log:
    p=subprocess.run(cmd,cwd=s/'apps/windows/src-tauri',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
result={'kind':kind,'exitCode':p.returncode,'wallSeconds':round(time.perf_counter()-started,2),'jobs':1,'modelsRun':False,'log':str(logpath),'command':cmd}
(out/('cargo-'+kind+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result));print(logpath.read_text(encoding='utf8',errors='replace')[-9000:]);raise SystemExit(p.returncode)
