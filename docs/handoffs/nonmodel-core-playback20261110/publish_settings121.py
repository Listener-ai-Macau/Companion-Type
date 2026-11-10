from pathlib import Path
import ast,subprocess,os,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';C=Path(__file__).parent
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((R/'companion-device-closure055/docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
paths=['apps/mobile/src/App.tsx','apps/mobile/src/AiServiceSettings.tsx','apps/mobile/src/CommonSettings.tsx','apps/mobile/src/commonSettings.css','apps/mobile/src/appearance.ts','apps/android/app/src/main/java/com/denzic/companion/app/MainActivity.java','apps/android/app/src/main/AndroidManifest.xml','apps/android/app/build.gradle','tools/test_common_settings.tsx','tools/qa/core_acceptance20261109/ui_source.cjs']
commit=scope['ship'](A,paths,'Add everyday Android settings and preserve unsaved AI configuration')
(C/'android121').mkdir(exist_ok=True);(C/'android121/source.json').write_text(json.dumps({'sourceCommit':commit,'remoteReadbackConfirmed':True,'versionCode':121,'phoneQualified':False},indent=2)+'\n');print(commit)
