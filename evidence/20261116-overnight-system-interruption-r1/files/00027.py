"""Protect the closed reboot interruption, partial output and honest current workpoint."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
OUT=Path('C:/Users/Billy/Documents/Codex/2026-11-14/xu-y/outputs/Companion-整夜会议模型结果-20261116')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prior=read(D/'protection-r27.json');assert prior['remoteVerified']
parent=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip();assert parent==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
DEST=M/'evidence/20261116-overnight-system-interruption-r1';assert not DEST.exists();(DEST/'files').mkdir(parents=True)
items=[]
def take(path,logical):
 before=path.stat();assert before.st_size<32*1024**2
 digest=sha(path);target=DEST/'files'/(str(len(items)).zfill(5)+path.suffix)
 shutil.copyfile(path,target);assert sha(target)==sha(path)==digest and path.stat().st_mtime_ns==before.st_mtime_ns
 items.append({'source':str(path),'logicalPath':logical,'file':target.relative_to(DEST).as_posix(),'bytes':before.st_size,'sha256':digest})
for root,label in [(C/'overnight-system-interruption-r1','system-interruption'),(C/'staged-r4','frozen-contract'),(E/'staged-r4','reboot-interrupted-run'),(OUT,'owner-delivery')]:
 for p in sorted(root.rglob('*')):
  if p.is_file():take(p,label+'/'+p.relative_to(root).as_posix())
take(E/'staged-r2/cache/ES2003b/manifest.json','retained-complete-context/cache-manifest.json')
take(E/'staged-r2/ES2003b-prefill-state.json','retained-complete-context/prefill-producer-state.json')
for name in ['finalize_overnight_20261116.py',Path(__file__).name,'bilingual_progress.json']:
 take(Path('work')/name,'continuation-tools/'+name)
manifest={'at':datetime.now().astimezone().isoformat(),'state':'OVERNIGHT_SYSTEM_REBOOT_INTERRUPTION_AND_PARTIAL_OUTPUT_PROTECTED',
 'parentCommit':parent,'entries':items,'fullPromptTokens':27924,'retainedGeneratedTokens':4064,
 'wholeMeetingTranscriptsCompleted':0,'wholeMeetingQualityScores':0,'newWeightTraining':False,
 'qualityQualified':False,'D2Complete':False,'productDefaultChanged':False,'finalHoldoutOpened':False,
 'originalRunJsonPreserved':True,'noNewNeuralInferenceAfterReboot':True,
 'crashCauseNotAttributedToComponent':True,'privateMemoryDumpContentsExcluded':True,
 'bulkCacheHashManifestOnly':True,'deadline':'2026-11-16T07:30:00+08:00'}
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=M/'.gitattributes';body=p.read_bytes();rule=DEST.relative_to(M).as_posix()+'/** -text -whitespace'
assert rule.encode() not in body;p.write_bytes(body+b'\n'+rule.encode()+b'\n')
with (M/'README.md').open('a',encoding='utf-8') as f:
 f.write('\n\n'+manifest['at']+' 整夜作业在00:16系统0x101异常重启中断。最后00:14保留4064原token，完整27924token原上下文KV仍在；完整四会0/4、候选质量分数0/4，无新训练或默认替换。原RUNNING文件保留，独立reconciliation纠正当前状态；重启后未再启动GPU推理。原始部分文本、CPU导出、系统事件和恢复绑定已归档，未将未完成输出算验收或售卖进展。下一关先稳定部署，再同四完整会议冻结对比。\n')
paths=['.gitattributes','README.md']+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected,n
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0');assert set(staged)==set(paths)
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Preserve overnight system interruption and original partial meeting output'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'state':manifest['state'],'modelCommit':head,'parentCommit':parent,'exactByteStagedFiles':len(paths),
 'evidenceFiles':len(items),'evidenceBytes':sum(x['bytes'] for x in items),'remoteVerified':False,'D2Complete':False,'wholeMeetingOutputs':0}
target=D/'protection-r28.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=180)
(D/'push-r28-model.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=45)
assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
