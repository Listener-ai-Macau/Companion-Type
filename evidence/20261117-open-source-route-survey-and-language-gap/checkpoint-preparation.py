"""Explicit exact-byte private checkpoint of selected source and closed evidence."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=argparse.ArgumentParser();p.add_argument('configuration',type=Path);a=p.parse_args();B=read(a.configuration);revision=B['revision']
prior=read(D/('protection-r'+str(revision-1)+'.json'));assert prior['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
dest=M/B['evidenceDirectory'];assert not dest.exists();dest.mkdir(parents=True);items=[]
def take(p,name):
 assert p.is_file() and p.stat().st_size<32*1024**2
 q=dest/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);digest=sha(p);assert sha(q)==digest
 items.append({'source':str(p),'file':name,'bytes':p.stat().st_size,'sha256':digest})
for source in B['closedDirectories']:
 root=Path(source['directory']);doc=read(root/source['stateFile'])
 assert doc['state']==source['requiredState']
 for file in root.rglob('*'):
  if file.is_file():take(file,source['label']+'/'+file.relative_to(root).as_posix())
for item in B['files']:take(Path(item['source']),item['name'])
take(a.configuration,'checkpoint-configuration.json');take(Path(__file__),'checkpoint-preparation.py')
manifest={'at':datetime.now().astimezone().isoformat(),'parent':prior['modelCommit'],'entries':items,
 'sources':{n:sha(M/n) for n in B['sources']},**B['claims']}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=M/'.gitattributes';b=p.read_bytes()
for rule in [dest.relative_to(M).as_posix()+'/** -text -whitespace']+[n+' -text -whitespace' for n in B['sources']]:
 if rule.encode() not in b:b+=b'\n'+rule.encode()+b'\n'
p.write_bytes(b)
paths=['.gitattributes']+B['sources']+[p.relative_to(M).as_posix() for p in dest.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(n.encode() for n in paths)+b'\0',check=True)
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected,n
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0');assert set(staged)==set(paths)
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m',B['commitMessage']],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'modelCommit':head,'parentCommit':prior['modelCommit'],'remoteVerified':False,'state':B['claims']['state'],'exactByteFiles':len(paths),'evidenceFiles':len(items)}
target=D/('protection-r'+str(revision)+'.json');target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=32m','-c','pack.deltaCacheSize=32m','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=180);(D/('push-r'+str(revision)+'-model.log')).write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=45);assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
