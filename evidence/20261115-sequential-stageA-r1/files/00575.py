from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
ROOT=Path('E:/CodexData/Companion/product-d1d2-20261114')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parent=read(D/'protection-r23.json')['modelCommit'];assert read(D/'protection-r23.json')['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==parent
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
assert read(D/'sequential-meeting-stageA-r2/decision.json')['qualityQualified'] is False
DEST=M/'evidence/20261115-sequential-stageA-r1';assert not DEST.exists();(DEST/'files').mkdir(parents=True)
items=[];not_copied=[]
def take(f,logical):
 before=f.stat();digest=sha(f)
 target=DEST/'files'/(str(len(items)).zfill(5)+f.suffix);shutil.copyfile(f,target)
 assert sha(target)==sha(f)==digest and before.st_mtime_ns==f.stat().st_mtime_ns
 items.append({'source':str(f),'logicalPath':logical,'file':target.relative_to(DEST).as_posix(),'sha256':digest,'bytes':before.st_size})
for root in [D/'sequential-meeting-stageA-r1',D/'sequential-meeting-stageA-r2',ROOT/'sequential-meeting-stageA-r1',ROOT/'sequential-meeting-stageA-r2']:
 for directory,dirs,files in os.walk(root):
  dirs[:]=[n for n in dirs if n not in ['__pycache__','offline-hf-cache','matplotlib-cache']]
  for name in sorted(files):
   f=Path(directory)/name
   if name=='run.json':assert read(f).get('finishedAt'),f
   if f.name=='features.npy' or f.name.endswith('.Array1-01.wav') or f.stat().st_size>=32*1024**2:
    not_copied.append({'source':str(f),'bytes':f.stat().st_size,'sha256':sha(f),'reason':'Original public long wave / reproducible full features kept locally with official source and byte-exact frontend proof; do not duplicate bulk cache.'});continue
   if f.suffix.lower() in {'.json','.jsonl','.log','.py','.txt','.npy','.wav','.pcm'}:take(f,root.name+'/'+f.relative_to(root).as_posix())
scripts=['prepare_sequential_meetings_20261115.py','bind_sequential_asr_20261115.py','prepare_sequential_speakers_20261115.py',
 'prepare_sequential_alignment_20261115.py','run_sequential_alignment_20261115.py','repair_sequential_ami_coverage_20261115.py',
 'merge_sequential_reuse_20261115.py','prepare_english_activity_calibration_20261115.py','calibrate_english_activity_20261115.py',
 'audit_english_activity_boundaries_20261115.py','calibrate_english_activity_gaps_20261115.py','check_english_activity_head_20261115.py',
 'evaluate_english_activity_candidate_20261115.py','record_sequential_results_20261115.py',Path(__file__).name]
for name in scripts:take(Path('work')/name,'continuation-tools/'+name)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
take(Path('outputs/Companion-多人轮流发言阶段A-20261115.txt'),'owner-stageA-results.txt')
sources=['ami_reference_coverage_20261115.py','disk_nemotron_frontend_20261115.py',
 'meeting_activity_threshold_20261115.py','meeting_activity_gap_20261115.py','meeting_activity_head_20261115.py',
 'run_sequential_meeting_asr_20261115.py','run_sequential_meeting_speaker_20261115.py',
 'score_sequential_meetings_20261115.py','score_sequential_speakers_20261115.py',
 'sequential_meeting_asr_worker_20261115.py','sequential_meeting_speaker_worker_20261115.py']
manifest={'state':'SEQUENTIAL_STAGE_A_REAL_BASELINE_SOURCE_FIX_FAILURES_AND_TRAINING_REJECTIONS_PROTECTED',
 'at':datetime.now().astimezone().isoformat(),'parentCommit':parent,'entries':items,'bulkHashOnly':not_copied,
 'originalWeightsCopied':False,'newWeightsTrained':False,'qualityQualified':False,'D2Complete':False,
 'sourceCoverageBugFixed':True,'invalidOldEnglishScoreWithdrawn':True,'productDefaultChanged':False,
 'sourceFiles':{name:sha(S/name) for name in sources},'priority':'A nonoverlap sequential first; B overlap and C noise pending.'}
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
attrs=M/'.gitattributes';body=attrs.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
 if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
attrs.write_bytes(body)
with (M/'README.md').open('a',encoding='utf-8') as f:
 f.write('\n\n'+manifest['at']+' 按Owner改为先原单麦多人轮流无重叠，再重叠/噪声。固定32段739.262125s/10回场。修AMI本轮A-D漏五人EN2001a的E：官方元数据与全部word文件严格一致；原无效英文55.10%失败保留，26精确复用+6替代推理。正确覆盖后中文验证CER73/1258=5.80%、原DER2.33%、人物CER75/1258=5.96%；英文WER141/709=19.89%、原DER20.90%、人物WER244/709=34.41%，均非产品合格。独立IS1000a/TS3005a训练源校准敏感度/短洞/原辅助头均未过预置训练门，未对验证寻参、无新权重/默认。磁盘前端61s上游全等+两旧中文65.44min特征整文件SHA全等，原CPU5%/2GiB和低RAM保护保持。完整原分数/最终holdout不变。\n')
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for name in paths:
 raw=(M/name).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+name],text=True).strip()==expected,name
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Establish sequential meeting baseline and fix complete AMI speaker coverage'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt={'state':manifest['state'],'modelCommit':head,'exactByteStagedFiles':len(paths),'evidenceFiles':len(items),
 'evidenceBytes':sum(x['bytes'] for x in items),'bulkHashOnlyFiles':len(not_copied),'remoteVerified':False,'D2Complete':False}
target=D/'protection-r24.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
result=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=600)
(D/'push-r24-model.log').write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0
result=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert result.returncode==0 and result.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
