"""Protect architecture decision, original failures and exact owned source bytes."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parent=read(D/'protection-r24.json')['modelCommit'];assert read(D/'protection-r24.json')['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==parent
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
assert not read(C/'decision.json')['qualityQualified']
DEST=M/'evidence/20261115-joint-architecture-r1';assert not DEST.exists();(DEST/'files').mkdir(parents=True)
items=[];bulk=[]
def take(f,logical):
 before=f.stat();digest=sha(f);target=DEST/'files'/(str(len(items)).zfill(5)+f.suffix)
 shutil.copyfile(f,target)
 assert sha(target)==sha(f)==digest and before.st_mtime_ns==f.stat().st_mtime_ns
 items.append({'source':str(f),'logicalPath':logical,'file':target.relative_to(DEST).as_posix(),'sha256':digest,'bytes':before.st_size})
for root in [C,E]:
 for directory,dirs,files in os.walk(root):
  dirs[:]=sorted(n for n in dirs if n not in ['__pycache__','.git','offline-hf-cache'])
  for name in sorted(files):
   f=Path(directory)/name
   if name=='run.json' or name=='inventory-run.json':assert read(f).get('finishedAt'),f
   if f.suffix.lower() in {'.gguf','.safetensors','.dll','.exe','.f32'} or f.stat().st_size>=32*1024**2:
    bulk.append({'source':str(f),'bytes':f.stat().st_size,'sha256':sha(f),
     'reason':'Pinned model/runtime artifact or reproducible complete-wave memmap; source and hashes retained, avoid duplicating bulk into Git.'});continue
   if f.suffix.lower() in {'.json','.jsonl','.log','.py','.txt','.bin','.npy','.wav','.pcm','.h','.gz'} or 'LICENSE' in f.name:
    take(f,root.name+'/'+f.relative_to(root).as_posix())
for directory in ['reference-annotation-audit-r1','reference-annotation-audit-en2002a-r1']:
 take(D/directory/'comparison.json','recovered-historical-evidence/'+directory+'/comparison.json')
scripts=['diagnose_language_gap_20261115.py','prepare_joint_architecture_20261115.py','prepare_joint_pilot_20261115.py',
 'prepare_joint_full_20261115.py','prepare_cpp_joint_backend_20261115.py','record_joint_architecture_20261115.py',Path(__file__).name]
for name in scripts:take(Path('work')/name,'continuation-tools/'+name)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
take(Path('outputs/Companion-会议模型架构收敛-20261115.txt'),'owner-architecture-report.txt')
sources=['moss_native_architecture_20261115.py','moss_native_pilot_worker_20261115.py','run_moss_native_architecture_20261115.py',
 'moss_native_full_execution_20261115.py','moss_native_full_worker_20261115.py','run_moss_native_full_20261115.py',
 'cpp_joint_meeting_worker_20261115.py','run_cpp_joint_meetings_20261115.py']
manifest={'state':'JOINT_ARCHITECTURE_NATIVE_PILOT_AND_WHOLE_RUNTIME_FAILURES_PROTECTED_NO_QUALITY_GAIN',
 'at':datetime.now().astimezone().isoformat(),'parentCommit':parent,'entries':items,'bulkHashOnly':bulk,
 'newWeightTraining':False,'qualityQualified':False,'D2Complete':False,'productDefaultChanged':False,
 'finalHoldoutOpened':False,'sourceFiles':{n:sha(S/n) for n in sources},
 'decision':'Deployment feasibility before whole-meeting model selection before meaningful domain adaptation; rejected tiny variants remain stopped.'}
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
attrs=M/'.gitattributes';body=attrs.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
 if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
attrs.write_bytes(body)
with (M/'README.md').open('a',encoding='utf-8') as f:
 f.write('\n\n'+manifest['at']+' Owner要求架构级收敛，停止无收益局部阈值/小样本变体。复用同MOSS0.9B权重重构官方native整文件SHA匹配，中英各180s短训练音频自然EOS；完整35min ES2003b在长上下文LLVM分配/2GiB保护失败，固定v0.4.2 C++/6800XT Vulkan在初始2048token KV分配失败，均无整会结果。失败保留，未自动重试/提限/切默认/训练新权重；不能称新准确率或D2/售卖完成。校正英语时间DER不等于真实漏话，历史原分/原门保留；四原开发会不是盲测。下一关先证明原资源下完整会议部署，再架构对照和公开会议隔离域适配；A轮流→B重叠→C噪声不变。\n')
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0')
assert set(staged)==set(paths),(set(staged)-set(paths),set(paths)-set(staged))
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected,n
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Evaluate joint meeting architecture and retain complete-runtime failures'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'state':manifest['state'],'modelCommit':head,'exactByteStagedFiles':len(paths),'evidenceFiles':len(items),
 'evidenceBytes':sum(x['bytes'] for x in items),'bulkHashOnlyFiles':len(bulk),'remoteVerified':False,'D2Complete':False}
target=D/'protection-r25.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
result=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=600)
(D/'push-r25-model.log').write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0
result=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert result.returncode==0 and result.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
