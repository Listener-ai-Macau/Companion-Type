from pathlib import Path
import ast,json,os,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';S=R/'companion-device-closure055';C=Path(__file__).parent
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
paths=['apps/android/app/build.gradle','apps/android/app/libs/companion-android-backend.aar','apps/android/app/libs/companion-android-backend.provenance.json','apps/android/app/src/main/AndroidManifest.xml']
paths += ['apps/android/app/src/main/java/com/denzic/companion/app/'+name+'.java' for name in ['AudioImportService','PlatformMediaImport','SpeechPcmConverter','MainActivity','LocalRecordingLifecycle','RecordingBookmarkAccess']]
paths += ['apps/android/app/src/test/java/com/denzic/companion/app/'+name+'.java' for name in ['ImportedAudioIntegrationTest','SpeechPcmConverterTest']]
paths += ['apps/mobile/src/'+name for name in ['App.tsx','AudioImport.tsx','audioImport.css']]+['tools/test_mobile_audio_import.tsx','tools/qa/core_acceptance20261109/ui_source.cjs']
head=scope['ship'](A,paths,'Keep import progress available and hold the library transaction only for final publication');record={'sourceCommit':head,'versionCode':123,'backendSource':json.loads((C/'backend-package.json').read_text())['backendSourceCommit'],'remoteSourceReadbackVerified':True,'phoneQualified':False};(C/'candidate-source.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
