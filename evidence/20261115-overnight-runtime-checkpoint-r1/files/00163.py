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
prior=read(D/'protection-r25.json');assert prior['remoteVerified']
parent=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip();assert parent==prior['modelCommit']
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
DEST=M/'evidence/20261115-overnight-runtime-checkpoint-r1';assert not DEST.exists();(DEST/'files').mkdir(parents=True)
items=[];bulk=[]
def take(path,logical):
 before=path.stat();digest=sha(path);target=DEST/'files'/(str(len(items)).zfill(5)+path.suffix)
 shutil.copyfile(path,target);assert sha(target)==sha(path)==digest and path.stat().st_mtime_ns==before.st_mtime_ns
 items.append({'source':str(path),'logicalPath':logical,'file':target.relative_to(DEST).as_posix(),'bytes':before.st_size,'sha256':digest})
names=['overnight-r1','overnight-r2','overnight-r3','overnight-r4','overnight-r5','decode-profile-r1','decoder-profile-r1','decoder-profile-r2','staged-r1']
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
take(C/'staged-r2/staged-binding.json','active-staged-r2/frozen-binding-only.json')
sources=['moss_causal_prefill_20261115.py','moss_decode_attention_20261115.py','moss_overnight_worker_20261115.py',
 'run_moss_overnight_20261115.py','score_joint_whole_meetings_20261115.py','moss_native_cache_store_20261115.py',
 'moss_staged_meeting_worker_20261115.py','run_moss_staged_meetings_20261115.py']
for n in ['prepare_moss_overnight_20261115.py','prepare_joint_whole_scoring_20261115.py','prepare_staged_moss_20261115.py',Path(__file__).name]:
 take(Path('work')/n,'continuation-tools/'+n)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
manifest={'at':datetime.now().astimezone().isoformat(),'state':'OVERNIGHT_FULL_PREFILL_MEMORY_FIX_AND_FAILURES_PROTECTED_STAGED_RUN_NOT_FINISHED',
 'parentCommit':parent,'entries':items,'bulkHashOnly':bulk,'sourceFiles':{n:sha(S/n) for n in sources},
 'fullPrefillTokensPassed':27924,'wholeMeetingTranscriptsCompletedAtCheckpoint':0,'newWeightTraining':False,
 'qualityQualified':False,'D2Complete':False,'productDefaultChanged':False,'finalHoldoutOpened':False,
 'activeRunExcludedFromSnapshot':str(E/'staged-r2'),'deadline':'2026-11-16T07:30:00+08:00'}
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=M/'.gitattributes';body=p.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
 if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
p.write_bytes(body)
with (M/'README.md').open('a',encoding='utf-8') as f:f.write('\n\n'+manifest['at']+' Owner授权推进至11月16早07:30。全decoder因果块+固定BF16存储/已填前缀视图原61s logits/KV逐值全等/16token一致，27924token整会prefill已完成/私有峰1.45GB；动态KV2GiB失败/原全宽Static数值失败均保留。真实解码21token太慢主动停，微基准排除单纯attention/适配/生成包装；冷解码阶段逐值恢复完整KV/首logits并退役已完成声学模块正在验证。4完整原字基线及两英语原DER已CPU复现；没有新整会质量成绩/新训练/默认变化。此提交为在途源码检查点，非交付或D2完成。\n')
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[f.relative_to(M).as_posix() for f in DEST.rglob('*') if f.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for n in paths:
 raw=(M/n).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+n],text=True).strip()==expected,n
staged=subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only','-z']).decode().strip('\0').split('\0');assert set(staged)==set(paths)
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Bound complete causal prefill and preserve overnight execution checkpoint'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'state':manifest['state'],'modelCommit':head,'exactByteStagedFiles':len(paths),'evidenceFiles':len(items),
 'evidenceBytes':sum(x['bytes'] for x in items),'bulkHashOnlyFiles':len(bulk),'remoteVerified':False,'D2Complete':False}
target=D/'protection-r26.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
r=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=600)
(D/'push-r26-model.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0
r=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert r.returncode==0 and r.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
