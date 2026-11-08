"""Focused native request/cache check using the idle existing build cache."""
from pathlib import Path
from datetime import datetime
import json,os,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-competitive-sale-standard/async-speaker-contract-r2'
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
env=os.environ.copy();env.update(CARGO_BUILD_JOBS='1',CARGO_TARGET_DIR='E:/CodexData/Companion/.build-cache/windows051/target',CARGO_INCREMENTAL='0')
command=['C:/Users/Billy/.cargo/bin/cargo.exe','test','--offline','--lib','--jobs','1','backend::volcengine::tests::async_speaker_request_requires_second_pass_and_large_model_ssd','--','--exact','--nocapture']
started=time.perf_counter();state={'startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'RUNNING_FOCUSED_NATIVE_CHECK','pid':os.getpid(),'command':command,'target':env['CARGO_TARGET_DIR'],'source':str(S),'installed':False}
out=C/'native-test.json';out.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
with (C/'native-test.log').open('wb') as f:
 p=subprocess.run(command,cwd=S/'apps/windows/src-tauri',env=env,stdout=f,stderr=subprocess.STDOUT)
actual_test=(C/'native-test.log').read_text(encoding='utf8',errors='replace')
matched='1 passed; 0 failed' in actual_test
state.update(state='FOCUSED_NATIVE_CHECK_PASSED' if p.returncode==0 and matched else 'FOCUSED_NATIVE_CHECK_FAILED',exitCode=p.returncode,oneActualTestPassed=matched,finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wallSeconds=time.perf_counter()-started)
out.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(state,ensure_ascii=False),flush=True)
