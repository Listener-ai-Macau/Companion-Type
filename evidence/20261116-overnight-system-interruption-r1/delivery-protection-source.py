"""Package only retained public output and interruption evidence, then protect the final checks."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1/overnight-system-interruption-r1'
OUT=Path('C:/Users/Billy/Documents/Codex/2026-11-14/xu-y/outputs/Companion-整夜会议模型结果-20261116')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prior=read(D/'protection-r28.json');assert prior['remoteVerified']
for name in ['retained-integrity-check.json','crash-evidence-availability.json','interruption.json']:
 shutil.copyfile(C/name,OUT/name)
shutil.copyfile(D/'protection-r28.json',OUT/'源码与原始输出保护.json')
archive=OUT.parent/'Companion-整夜结果-20261116.zip'
assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(OUT.iterdir()):
  if p.is_file():z.write(p,p.name)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
delivery={'at':datetime.now().astimezone().isoformat(),'archive':str(archive),'archiveSha256':sha(archive),
 'files':[{'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file()],
 'wholeMeetingResults':0,'qualityQualified':False,'saleQualified':False,'systemInterrupted':True,
 'retainedCacheHashesPassed':True,'noGpuInferenceAfterReboot':True,'originalSourceCommit':prior['modelCommit']}
(D/'overnight-delivery-20261116.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
dest=M/'evidence/20261116-overnight-system-interruption-r1';manifest=read(dest/'manifest.json')
paths=[]
for p,label in [(C/'retained-integrity-check.json','final-check-cache-integrity.json'),(C/'crash-evidence-availability.json','final-check-dump-availability.json'),(D/'overnight-delivery-20261116.json','owner-delivery-manifest.json'),(Path('work/check_retained_overnight_20261116.py'),'integrity-check-source.py'),(Path(__file__),'delivery-protection-source.py')]:
 target=dest/label;assert not target.exists();shutil.copyfile(p,target);assert sha(p)==sha(target)
 manifest['entries'].append({'source':str(p),'logicalPath':'final-check/'+label,'file':label,'bytes':p.stat().st_size,'sha256':sha(p)})
 paths.append(target.relative_to(M).as_posix())
manifest['finalChecks']={'at':datetime.now().astimezone().isoformat(),'cacheFiles':59,'cacheBytes':3203305920,'unchangedPrefix':2294,'retainedTokens':4064,'wholeMeetingsCompleted':0,'dumpAvailableAtStandardConfiguredPaths':False,'archiveSha256':delivery['archiveSha256']}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');paths.append((dest/'manifest.json').relative_to(M).as_posix())
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0');assert set(staged)==set(paths)
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Verify retained full cache and package interrupted overnight meeting output'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'at':datetime.now().astimezone().isoformat(),'modelCommit':head,'parentCommit':prior['modelCommit'],'state':'INTERRUPTED_OVERNIGHT_DELIVERY_AND_FILE_CHECKS_PROTECTED','exactByteStagedFiles':len(paths),'remoteVerified':False,'D2Complete':False,'wholeMeetingOutputs':0}
target=D/'protection-r29.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=180)
(D/'push-r29-model.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=45)
assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p)
d['sourceProtection'].update(overnightInterruptionCommit=prior['modelCommit'],overnightInterruptionRemoteVerified=True,
 overnightFinalChecksCommit=head,overnightFinalChecksRemoteVerified=True,overnightFinalChecksReceipt=str(target))
d['ownerOvernightRun20261115'].update(deliveryManifest=str(D/'overnight-delivery-20261116.json'),archive=str(archive),archiveSha256=delivery['archiveSha256'],retainedCacheIntegrityPassed=True)
d['logResult']+='\n'+datetime.now().astimezone().isoformat()+' 早间文件核对通过59个完整缓存文件/3203305920字节原SHA，2294旧生成ID为4064新ID的精确前缀；无活动自有神经进程。标准配置转储目录无本次dmp，未读/上传内存转储内容。部分原文、明确未完成的交付说明和恢复绑定已打包，CRC检查通过；源码/原输出/中断证据私有保护'+head+'，独立远端回读一致。此为中断交付，不是完整会议质量或售卖通过。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'archive':str(archive),'sha256':delivery['archiveSha256'],'protection':receipt},ensure_ascii=False))
