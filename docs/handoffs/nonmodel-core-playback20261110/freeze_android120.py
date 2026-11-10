from pathlib import Path
from datetime import datetime
import ast,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent
shutil.copyfile(C/'source-freeze.json',C/'source-freeze119.json')
check=json.loads((C/'owned-progress-check.json').read_text());assert check['state']=='OWNED_PLAYBACK_REOPEN_BACKUP_RESTORE_TRASH_AND_EXACT_PURGE_PASSED'
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID120_COMPLETE_NONMODEL_REVIEW_CANDIDATE_REMOTE_BUILD_PENDING','version':'0.1.120','prior119RunPassed':42736712959,'prior119Source':'a6876984d4d7ec9411d9dfa4d233b726a0391ba6','nativeMediaPlayerCodeUnchangedSince118':True,'finalStorageChange':'Use existing <record-digest>.* ownership for progress and crash temporaries. Existing exact-record deletion now includes both without changing or broadening the purge implementation.','ownedStorageProof':check,'backendAarUnchanged':True,'installed':False,'nativePhonePlaybackQualified':False,'modelsRun':False,'saleQualified':False}
(C/'source-freeze.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
dest=S/'docs/handoffs/nonmodel-core-playback20261110';dest.mkdir(parents=True,exist_ok=True)
for p in C.iterdir():
 if p.is_file() and p.suffix in ['.py','.json']:shutil.copyfile(p,dest/p.name)
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
t=ast.parse((R/'companion-device-closure055/docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'publisher','exec'),scope)
paths=['apps/android/app/build.gradle','apps/android/app/src/main/java/com/denzic/companion/app/PlaybackProgress.java','apps/android/app/src/test/java/com/denzic/companion/app/PlaybackProgressTest.java','apps/android/app/src/test/java/com/denzic/companion/app/PlaybackBackupCompatibilityTest.java','apps/android/app/src/test/java/com/denzic/companion/app/PlaybackLifecycleTest.java','docs/handoffs/nonmodel-core-playback20261110']
head=scope['ship'](S,paths,'Finish Android120 playback and correction candidate with complete data lifecycle')
record.update(sourceCommit=head,remoteReadbackVerified=True);(C/'source-freeze.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
