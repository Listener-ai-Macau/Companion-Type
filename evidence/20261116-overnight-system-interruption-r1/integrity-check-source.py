"""CPU/file-only checks of a reboot-interrupted original cache and generated prefix."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,sys
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
manifest=read(E/'staged-r2/cache/ES2003b/manifest.json');checked=[]
for x in manifest['files']:
 p=Path(x['file']);digest=sha(p);assert digest==x['sha256'],p
 checked.append({'file':str(p),'bytes':p.stat().st_size,'sha256':digest})
old=read(E/'staged-r2/ES2003b-partial-ids.json')['generatedIds']
new=read(E/'staged-r4/ES2003b-partial-ids.json')['generatedIds']
assert len(old)==2294 and len(new)==4064 and new[:len(old)]==old
run=read(E/'staged-r4/run.json')
assert not psutil.pid_exists(run['pid']) and not psutil.pid_exists(11636)
active=[]
for p in psutil.process_iter(['pid','name','cmdline']):
 try:
  command=' '.join(p.info['cmdline'] or [])
  if p.info['pid']!=psutil.Process().pid and any(n in command for n in ['moss_staged_meeting_worker_20261115.py','run_moss_staged_meetings_20261115.py','moss_overnight_worker_20261115.py','run_moss_overnight_20261115.py']) and (p.info['name'] or '').lower().startswith('python'):
   active.append({'pid':p.info['pid'],'name':p.info['name'],'cmdline':command})
 except (psutil.AccessDenied,psutil.NoSuchProcess):pass
assert not active,active
result={'at':datetime.now().astimezone().isoformat(),'state':'RETAINED_FILE_INTEGRITY_AND_EXACT_PREFIX_PASS_NO_INFERENCE',
 'checkedCacheFiles':checked,'checkedCacheBytes':sum(x['bytes'] for x in checked),
 'originalPrefixTokens':len(old),'newRetainedTokens':len(new),'priorGeneratedPrefixByteForBytePreserved':True,
 'runPidDead':True,'workerPidDead':True,'activeOwnNeuralProcesses':active,
 'qualityQualified':False,'neuralInferenceRun':False,'torchImported':'torch' in sys.modules,
 'notAStableGpuRuntimeCertificate':True}
assert not result['torchImported']
(C/'overnight-system-interruption-r1/retained-integrity-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checkedCacheFiles'}))
