from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
prior=json.loads((D/'protection-r29.json').read_text());assert prior['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
dest=M/'evidence/20261116-day-whole-resume';assert not dest.exists();dest.mkdir(parents=True)
sources=['src/moss_native_greedy_20261115.py','src/moss_staged_meeting_worker_20261115.py']
entries=[]
for p,name in [(D/'joint-architecture-r1/staged-r5/staged-binding.json','staged-binding.json'),(Path('work/prepare_moss_day_resume_20261116.py'),'prepare-source.py'),(Path(__file__),'protect-source.py'),(Path('work/bilingual_progress.json'),'canonical-workpoint.json')]:
 q=dest/name;shutil.copyfile(p,q);digest=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(q.read_bytes()).hexdigest()==digest
 entries.append({'source':str(p),'file':name,'sha256':digest})
manifest={'at':datetime.now().astimezone().isoformat(),'parent':prior['modelCommit'],'entries':entries,'sources':{n:hashlib.sha256((M/n).read_bytes()).hexdigest() for n in sources},'state':'EXTENDED_TO_1600_CONTROL_PENDING_NO_NEW_QUALITY_RESULT','wholeMeetingOutputs':0,'newWeightTraining':False,'automaticKernelFailureRetries':0}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=M/'.gitattributes';b=p.read_bytes();rule=dest.relative_to(M).as_posix()+'/** -text -whitespace';assert rule.encode() not in b;p.write_bytes(b+b'\n'+rule.encode()+b'\n')
paths=['.gitattributes']+sources+[q.relative_to(M).as_posix() for q in dest.iterdir() if q.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(n.encode() for n in paths)+b'\0',check=True)
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0');assert set(staged)==set(paths)
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Continue retained whole meeting after reboot with synchronized paced native decoding'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'modelCommit':head,'parentCommit':prior['modelCommit'],'remoteVerified':False,'state':manifest['state'],'exactByteFiles':len(paths)}
target=D/'protection-r30.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=180);(D/'push-r30-model.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=45);assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
