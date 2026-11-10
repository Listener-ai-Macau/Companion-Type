from pathlib import Path
from datetime import datetime
import json,subprocess,psutil
C=Path(__file__).parent;assert not (C/'phone-debug-prompt-process-r2.json').exists()
args=['C:/Users/Billy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe','-NoProfile','-NonInteractive','-STA','-ExecutionPolicy','Bypass','-File',str(C/'phone_debug_prompt7.ps1')]
with (C/'phone-debug-prompt-result-r2.json').open('wb') as out,(C/'phone-debug-prompt-r2.log').open('wb') as error:p=subprocess.Popen(args,stdout=out,stderr=error,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'pid':p.pid,'createdAt':psutil.Process(p.pid).create_time(),'sharedOriginalPromptUsed':True,'noActivate':True,'differenceFromFailedPreparation':'Original UI requires PowerShell7; import that host own built-in command DLLs without altering system settings. First host5 failed before a window appeared.'}
(C/'phone-debug-prompt-process-r2.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
