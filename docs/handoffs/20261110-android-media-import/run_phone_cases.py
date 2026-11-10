from pathlib import Path
import subprocess,json,time
C=Path(__file__).parent;results=[]
for name,expected in [('Companion-public-without-audio.mp4','failed'),('Companion-public-invalid.mp3','failed'),('Companion-public-meeting-long38m.mp3','cancelled')]:
 q=subprocess.run(['node',str(C/'import_case.cjs'),name,expected],capture_output=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW,timeout=100);results.append({'file':name,'expected':expected,'exit':q.returncode});print(q.stdout.strip() or q.stderr.strip(),flush=True)
 if q.returncode:break
(C/'android123/native-error-cases.json').write_text(json.dumps({'at':__import__('datetime').datetime.now().astimezone().isoformat(),'cases':results},indent=2)+'\n');assert len(results)==3 and all(r['exit']==0 for r in results)
