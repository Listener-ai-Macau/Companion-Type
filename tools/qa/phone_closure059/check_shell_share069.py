from pathlib import Path
import json,os,subprocess,psutil
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share069';C=Path('E:/CodexData/Companion/.build-cache/windows-share069');C.mkdir(exist_ok=True)
vc=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC/14.44.35207');sdk=Path('C:/Program Files (x86)/Windows Kits/10');v='10.0.26100.0'
env={**os.environ,'INCLUDE':';'.join(map(str,[vc/'include',sdk/'Include'/v/'ucrt',sdk/'Include'/v/'shared',sdk/'Include'/v/'um',sdk/'Include'/v/'winrt'])),'LIB':';'.join(map(str,[vc/'lib/x64',sdk/'Lib'/v/'um/x64',sdk/'Lib'/v/'ucrt/x64'])),'PATH':str(vc/'bin/Hostx64/x64')+';'+os.environ['PATH']}
psutil.Process().cpu_affinity([12,13,14,15]);exe=C/'ShellShareVerbs.exe'
run=subprocess.run([str(vc/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++20','/EHsc','/O1','/MT','/utf-8','/Fo'+str(C/'ShellShareVerbs.obj'),'/Fe'+str(exe),str(W/'windows_shareqa068/ShellShareVerbs.cpp'),'/link','shell32.lib','ole32.lib','user32.lib','uuid.lib'],cwd=C,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
(O/'shell-verbs-build.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,run.stdout+run.stderr
public=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff/saved/Windows067-public-transcript.pdf'
run=subprocess.run([str(exe),str(public)],env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
(O/'shell-verbs-readonly.log').write_text(run.stdout+run.stderr,encoding='utf8');print(run.stdout+run.stderr);assert run.returncode==0,run.returncode
