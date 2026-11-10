from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent
prior=C/'source-freeze.json';archived=C/'source-freeze118.json';assert not archived.exists();shutil.copyfile(prior,archived)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID119_COMPLETE_REVIEW_SOURCE_FROZEN_REMOTE_BUILD_PENDING','version':'0.1.119','supersedesUninstalledCandidate':'0.1.118','priorNativeAndPlaybackUiBuildPassedRun':42735769810,'priorSource':'9697968da4aa9abc32cef5b85da3b95282990473','newNativeControlChangesSince118':False,'backendAarUnchanged':True,'additionalOutcome':'Literal find/replace and safe undo in the existing native transcript correction editor; existing revision/first-original preservation and dirty-exit guards retained.','installed':False,'nativeRuntimeQualified':False,'modelsRun':False,'saleQualified':False}
(C/'source-freeze.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
dest=S/'docs/handoffs/nonmodel-core-playback20261110';dest.mkdir(parents=True,exist_ok=True)
for p in C.iterdir():
 if p.is_file() and p.suffix in ['.py','.json']:shutil.copyfile(p,dest/p.name)
tree=ast.parse((R/'companion-device-closure055/docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'};scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
paths=['apps/android/app/build.gradle','apps/mobile/src/App.tsx','apps/mobile/src/TranscriptReplace.tsx','apps/mobile/src/transcriptReplace.css','tools/test_transcript_replace.tsx','tools/qa/core_acceptance20261109/ui_source.cjs','docs/handoffs/nonmodel-core-playback20261110']
for name in ['apps/mobile/src/TranscriptReplace.tsx','apps/mobile/src/transcriptReplace.css','tools/test_transcript_replace.tsx']:assert (S/name).is_file() and name in paths
head=scope['ship'](S,paths,'Complete Android119 continued playback and safe bulk transcript correction')
record.update(sourceCommit=head,remoteReadbackVerified=True);(C/'source-freeze.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
