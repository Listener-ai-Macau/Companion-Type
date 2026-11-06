from pathlib import Path
import json,os,psutil,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share070'
C=Path('E:/CodexData/Companion/.build-cache/windows051');target=C/'target'
env={**os.environ,'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','CARGO_TARGET_DIR':str(target),'RAYON_NUM_THREADS':'2','TEMP':str(C),'TMP':str(C)}
psutil.Process().cpu_affinity([12,13]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
results=[]
commands=[('component',['C:/Program Files/nodejs/node.exe','tools/test_share070.mjs']),('windows-types',['C:/Program Files/nodejs/node.exe','node_modules/typescript/bin/tsc','-p','apps/windows/tsconfig.json','--noEmit']),('mobile-types',['C:/Program Files/nodejs/node.exe','node_modules/typescript/bin/tsc','-p','apps/mobile/tsconfig.json','--noEmit']),('native-check',['C:/Users/Billy/.cargo/bin/cargo.exe','check','--offline','--locked','--tests','--message-format=json'])]
for name,cmd in commands:
 start=time.perf_counter();log=O/(name+'-light.log');print('Checking '+name+' sequentially without UI.',flush=True)
 with log.open('wb') as stream:
  p=subprocess.run(cmd,cwd=S/'apps/windows/src-tauri' if name=='native-check' else S,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=600)
 row={'name':name,'exitCode':p.returncode,'seconds':round(time.perf_counter()-start,3)};results.append(row)
 (O/'light-check-result.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(json.dumps(row),flush=True)
 if p.returncode:
  print(log.read_text(encoding='utf8',errors='replace')[-6000:],flush=True)
  raise RuntimeError(name+' failed')
