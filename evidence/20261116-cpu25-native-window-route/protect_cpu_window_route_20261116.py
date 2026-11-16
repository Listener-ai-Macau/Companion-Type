"""Protect frozen CPU window route and closed failures; exclude active outputs."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prior=read(D/'protection-r33.json');assert prior['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
dest=M/'evidence/20261116-cpu25-native-window-route';assert not dest.exists();dest.mkdir(parents=True)
sources=['src/'+n for n in ['moss_cpu_mapped_meeting_worker_20261116.py','moss_cpu_grouped_attention_20261116.py','cpu_window_joint_worker_20261116.py','run_cpu_window_joint_20261116.py','compose_cpu_window_speakers_20261116.py','score_cpu_window_composition_20261116.py']]
items=[]
def take(p,name):
 assert p.stat().st_size<32*1024**2
 q=dest/name;shutil.copyfile(p,q);digest=sha(p);assert sha(q)==digest
 items.append({'source':str(p),'file':name,'bytes':p.stat().st_size,'sha256':digest})
for name in ['cpu-mapped-r2','cpu-mapped-r3','cpu-mapped-r4','stagea-cpu-composition-r1']:
 root=E/name;assert read(root/'run.json')['finishedAt']
 for p in root.iterdir():
  if p.is_file():take(p,name+'-'+p.name)
for name in ['cpu-grouped-attention-probe-r2','available-780m-probe-r1','cpp-vulkan-780m-commit-probe-r1']:
 take(E/name/'result.json',name+'-result.json')
for name in ['cpu-mapped-r3','cpu-mapped-r4']:
 take(C/name/'staged-binding.json',name+'-binding.json')
for name in ['stagea-cpu-composition-r1','stagea-cpu-composition-r2']:
 for p in (C/name).iterdir():
  if p.is_file():take(p,name+'-'+p.name)
for name in ['prepare_cpu_window_composition_20261116.py','prepare_cpu_window_api_fix_20261116.py','freeze_cpu_window_composition_20261116.py','observe_cpu_window_20261116.py','probe_cpu_grouped_attention_20261116.py','probe_available_780m_20261116.py','probe_cpp_vulkan_780m_commit_20261116.py',Path(__file__).name]:
 take(Path('work')/name,name)
# Preserve the exact source that caused the retained wrapper failure.
current=(M/'src/cpu_window_joint_worker_20261116.py').read_bytes()
failed=current.replace(b'     # This pinned Python wrapper exposes truncation through exceptions and\n     # the registered C API, rather than a Session.was_truncated property.\n     truncated=bool(cpp._lib.transcribe_was_truncated(session._h))',b'     truncated=session.was_truncated')
assert hashlib.sha256(failed).hexdigest()==read(C/'stagea-cpu-composition-r1/binding.json')['workerSha256']
(dest/'failed-r1-worker-source.py').write_bytes(failed)
manifest={'at':datetime.now().astimezone().isoformat(),'parent':prior['modelCommit'],'entries':items,'sources':{n:sha(M/n) for n in sources},
 'state':'CPU25_NATIVE_WINDOW_COMPOSITION_SOURCE_FROZEN_ACTIVE_RUN_EXCLUDED','ownerCpuPermission':'允许约 25% CPU，继续后台实测',
 'cpuPercent':25,'maximumComputeThreads':4,'privateLimitBytes':2147483648,'actualWindowsLowMemoryStop':True,
 'originalWholeMeeting6501IdsRetained':True,'wholeMeetingResults':0,'weightsChanged':False,'newWeightTraining':False,'qualityQualified':False,'saleQualified':False,
 'groupedAttentionNotAdopted':True,'cpuWholeMappingNotSelectedForDefault':True,'activeOutputsExcluded':str(E/'stagea-cpu-composition-r2')}
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
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Bound native CPU window ASR to approved25percent and preserve failed full-KV routes'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'modelCommit':head,'parentCommit':prior['modelCommit'],'remoteVerified':False,'state':manifest['state'],'exactByteFiles':len(paths),'evidenceFiles':len(items),'wholeMeetingResults':0}
target=D/'protection-r34.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=180);(D/'push-r34-model.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=45);assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
