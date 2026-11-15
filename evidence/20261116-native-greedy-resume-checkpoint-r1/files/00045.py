"""Protect changed execution source and closed failures; never snapshot live output."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prior=read(D/'protection-r26.json');assert prior['remoteVerified']
parent=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip();assert parent==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
DEST=M/'evidence/20261116-native-greedy-resume-checkpoint-r1';assert not DEST.exists();(DEST/'files').mkdir(parents=True)
items=[];bulk=[]
def take(path,logical):
 before=path.stat();digest=sha(path);target=DEST/'files'/(str(len(items)).zfill(5)+path.suffix)
 shutil.copyfile(path,target);assert sha(target)==sha(path)==digest and path.stat().st_mtime_ns==before.st_mtime_ns
 items.append({'source':str(path),'logicalPath':logical,'file':target.relative_to(DEST).as_posix(),'bytes':before.st_size,'sha256':digest})
names=['staged-r2','staged-r3']
for name in names:
 for root in [C/name,E/name]:
  assert root.is_dir(),root
  if root.parent==E:assert read(root/'run.json').get('finishedAt'),root
  for directory,dirs,files in os.walk(root):
   dirs[:]=sorted(d for d in dirs if d!='__pycache__')
   for filename in sorted(files):
    f=Path(directory)/filename
    if f.suffix=='.f32' or f.stat().st_size>=32*1024**2 or 'cache' in f.relative_to(root).parts:
     if filename!='manifest.json':
      bulk.append({'source':str(f),'bytes':f.stat().st_size,'sha256':sha(f),'reason':'Reproducible original-wave map or bit-exact native KV state, manifest included; do not duplicate bulk.'});continue
    if f.suffix in ['.json','.jsonl','.log','.py','.txt','.npy'] or filename=='stop.request':take(f,name+'/'+('control/' if root.parent==C else 'execution/')+f.relative_to(root).as_posix())
# Current run is live. Only its immutable input contract is part of this checkpoint.
take(C/'staged-r4/staged-binding.json','active-staged-r4/frozen-binding-only.json')
for n in ['whole-scoring-only.json','whole-scoring-only-before-evidence-path-fix.json','baseline-evidence-link-correction.json']:
 take(C/'overnight-r5'/n,'unchanged-quality-contract/'+n)
sources=['moss_native_greedy_20261115.py','moss_staged_meeting_worker_20261115.py']
for n in ['prepare_moss_overnight_20261115.py','prepare_joint_whole_scoring_20261115.py','prepare_staged_moss_20261115.py',Path(__file__).name]:
 take(Path('work')/n,'continuation-tools/'+n)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
manifest={'at':datetime.now().astimezone().isoformat(),'state':'NATIVE_GREEDY_RESUME_CONTROL_AND_HIP_FAILURE_PROTECTED_WHOLE_QUALITY_PENDING',
 'parentCommit':parent,'entries':items,'bulkHashOnly':bulk,'sourceFiles':{n:sha(S/n) for n in sources},
 'fullPrefillTokensPassed':27924,'wholeMeetingTranscriptsCompletedAtCheckpoint':0,'newWeightTraining':False,
 'qualityQualified':False,'D2Complete':False,'productDefaultChanged':False,'finalHoldoutOpened':False,
 'activeRunExcludedFromSnapshot':str(E/'staged-r4'),'deadline':'2026-11-16T07:30:00+08:00'}
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=M/'.gitattributes';body=p.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
 if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
p.write_bytes(body)
with (M/'README.md').open('a',encoding='utf-8') as f:
 f.write('\n\n'+manifest['at']+' ES2003b完整native27924token缓存已逐值落盘恢复，staged-r2实际2294token后HIP C++ abort在GPU停止检查同步呈现，族私有约1.2GB，原失败/前缀/完整缓存保留。staged-r3未设置generation字段None被前向前检查阻止，已按标准默认修复；不放宽数值门。staged-r4将相同batch1 argmax/EOS改为CPU持有，原公开61s回放8续8严格复现16token，原ES2294生成ID全部回放保留继续，无重新编码原音、无换模型/训练/删词。当前整会尚无最终分数，07:20停止推理/07:30汇总；这是在途源检查点，不是D2或售卖完成。\n')

paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[f.relative_to(M).as_posix() for f in DEST.rglob('*') if f.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected,n
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0');assert set(staged)==set(paths)
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Preserve original generated tokens with controlled CPU EOS native continuation'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'state':manifest['state'],'modelCommit':head,'exactByteStagedFiles':len(paths),'evidenceFiles':len(items),
 'evidenceBytes':sum(x['bytes'] for x in items),'bulkHashOnlyFiles':len(bulk),'remoteVerified':False,'D2Complete':False}
target=D/'protection-r27.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=600)
(D/'push-r27-model.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))

