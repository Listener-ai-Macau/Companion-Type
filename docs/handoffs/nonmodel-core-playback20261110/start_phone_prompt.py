from pathlib import Path
from datetime import datetime
import json,subprocess,psutil
C=Path(__file__).parent;log=C/'phone-debug-prompt.log';output=C/'phone-debug-prompt-result.json'
assert not (C/'phone-debug-prompt-process.json').exists(),'Do not repeat the same request'
args=['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-STA','-ExecutionPolicy','Bypass','-File',str(C/'phone_debug_prompt.ps1')]
with output.open('wb') as out,log.open('wb') as error:p=subprocess.Popen(args,stdout=out,stderr=error,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'pid':p.pid,'createdAt':psutil.Process(p.pid).create_time(),'sharedPromptUsed':True,'noActivate':True,'purpose':'USB MTP is present without ADB interface; one physical debugging-toggle action, not agent filesystem approval','testStartsOnlyAfterActualAdbReady':True}
(C/'phone-debug-prompt-process.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
