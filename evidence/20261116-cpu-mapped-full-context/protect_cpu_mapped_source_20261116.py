"""Protect new CPU memory mapping plus the actual GPU unplug exit; exclude active outputs."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prior=read(D/'protection-r31.json');assert prior['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
dest=M/'evidence/20261116-cpu-mapped-full-context';assert not dest.exists();dest.mkdir(parents=True)
sources=['src/moss_native_greedy_20261115.py','src/moss_cpu_mapped_runtime_20261116.py','src/moss_cpu_mapped_meeting_worker_20261116.py','src/run_moss_cpu_mapped_meetings_20261116.py']
items=[]
def take(p,name):
 assert p.stat().st_size<32*1024**2
 q=dest/name;shutil.copyfile(p,q);digest=sha(p);assert sha(q)==digest
 items.append({'source':str(p),'file':name,'bytes':p.stat().st_size,'sha256':digest})
assert read(E/'staged-r6/run.json')['finishedAt']
for p in (E/'staged-r6').iterdir():
 if p.is_file():take(p,'closed-r6-'+p.name)
take(C/'staged-r6/device-disconnection.json','windows-device-disconnection.json')
take(E/'cpp-vulkan-commit-probe-r1/result.json','vulkan-probe-no6800-no-allocation.json')
take(C/'cpu-mapped-r1/staged-binding.json','cpu-mapped-frozen-binding.json')
for name in ['prepare_cpu_mapped_sources_20261116.py','prepare_cpu_mapped_binding_20261116.py',Path(__file__).name,'bilingual_progress.json']:
 take(Path('work')/name,name)
manifest={'at':datetime.now().astimezone().isoformat(),'parent':prior['modelCommit'],'entries':items,
 'sources':{n:sha(M/n) for n in sources},'state':'GPU_UNPLUG_CONFIRMED_CPU_MAPPED_NATIVE_SOURCE_CHECKPOINT',
 'ownerGpuReply':'已经拔下或断电','retainedGeneratedTokens':6501,'fullPromptTokens':27924,
 'weightsChanged':False,'quantizationUsed':False,'newWeightTraining':False,'wholeMeetingResults':0,
 'qualityQualified':False,'saleQualified':False,'activeCpuRunOutputsExcluded':str(E/'cpu-mapped-r1'),
 'readOnlyWeightsMapping':'ACCESS_READ; tensor storage pointers checked after materialization',
 'sharedWritableKvMapping':'ACCESS_WRITE on real files; private memory and real working RAM monitored separately',
 'earlierSystemBugcheckCauseStillUnknown':True}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=M/'.gitattributes';b=p.read_bytes()
for rule in [dest.relative_to(M).as_posix()+'/** -text -whitespace']+[n+' -text -whitespace' for n in sources]:
 if rule.encode() not in b:b+=b'\n'+rule.encode()+b'\n'
p.write_bytes(b)
paths=['.gitattributes']+sources+[p.relative_to(M).as_posix() for p in dest.iterdir() if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(n.encode() for n in paths)+b'\0',check=True)
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected,n
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0');assert set(staged)==set(paths)
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Continue exact native BF16 CPU inference using read-only weights and file-backed full KV'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'modelCommit':head,'parentCommit':prior['modelCommit'],'remoteVerified':False,'state':manifest['state'],'exactByteFiles':len(paths),'evidenceFiles':len(items),'wholeMeetingResults':0}
target=D/'protection-r32.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=180);(D/'push-r32-model.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=45);assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
