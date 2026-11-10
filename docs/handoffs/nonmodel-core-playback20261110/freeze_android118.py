from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110')
for name in ['checkpoint-compile.log','checkpoint-behavior.log','mobile-typecheck.log']:shutil.copyfile(P/name,C/name)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID118_GROUPED_SOURCE_FROZEN_REMOTE_CHECKS_AND_BUILD_PENDING','version':'0.1.118','checkpointBehaviorPassed':True,'localTypecheck':'Checker stopped at its explicit256MiB Node heap cap; retained log, no product diagnosis; full mobile typecheck runs on dedicated CI.','backendAarUnchanged':True,'modelsRun':False,'installed':False,'actualNativePlaybackQualified':False,'saleQualified':False,'androidApiSource':'https://developer.android.com/reference/android/media/MediaPlayer','apiDecision':'Set rate in initialized state before prepare, preserving paused cross-part seeks. Defer paused rate application until resume. Serialize seek and wait for native onSeekComplete before persisting.'}
(C/'source-freeze.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
dest=S/'docs/handoffs/nonmodel-core-playback20261110';dest.mkdir(parents=True,exist_ok=True)
for p in C.iterdir():
 if p.is_file() and p.suffix in ['.py','.json']:shutil.copyfile(p,dest/p.name)
 if p.is_file() and p.suffix=='.log':
  raw=p.read_bytes();target=dest/(p.name+'.json');target.write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'utf8':raw.decode('utf8',errors='replace')},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  old=dest/p.name
  if old.exists():assert old.parent==dest;old.unlink() # Generated duplicate only; original raw failure remains in C and P.
tree=ast.parse((R/'companion-device-closure055/docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'};scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
paths=['apps/android/app/src/main/java/com/denzic/companion/app/PlaybackProgress.java','apps/android/app/src/main/java/com/denzic/companion/app/MainActivity.java','apps/android/app/src/test/java/com/denzic/companion/app/PlaybackProgressTest.java','apps/android/app/build.gradle','apps/mobile/src/App.tsx','apps/mobile/src/PlaybackTools.tsx','apps/mobile/src/playbackTools.css','tools/test_playback_tools.tsx','tools/qa/core_acceptance20261109/ui_source.cjs','docs/handoffs/nonmodel-core-playback20261110']
head=scope['ship'](S,paths,'Complete Android118 durable per-record playback, speed and original-time jumps')
record.update(sourceCommit=head,remoteReadbackVerified=True);(C/'source-freeze.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
