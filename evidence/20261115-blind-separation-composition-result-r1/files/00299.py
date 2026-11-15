from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,shutil,subprocess
import psutil

p=argparse.ArgumentParser();p.add_argument('--stage',choices=['component','final'],required=True);a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'blind-separation-composition-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/blind-separation-composition-r1')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
component=a.stage=='component';number=14 if component else 15
parent='4054ff699ba084fa39e1f955d9a6d64edcc66f36' if component else read(D/'protection-r14.json')['modelCommit']
DEST=M/('evidence/20261115-blind-separation-'+('component-r1' if component else 'composition-result-r1'))
assert not DEST.exists()
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==parent
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
if component:
    assert read(E/'control-r1/state.json')['state']=='PASS_BLIND_SEPARATOR_NUMERICAL_AND_LOSSLESS_STITCH_CONTROLS'
    state=read(E/'separate-r1/state.json');assert state['state']=='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING' and len(state['results'])==32
    stamp=datetime.now().astimezone().isoformat(timespec='seconds')
    with (M/'README.md').open('a',encoding='utf-8') as f:
        f.write('\n\n'+stamp+' Owner继续要求分离与组合模型：已按旧目标样音分离两训练的塌缩/漏词/参考不稳失败纠偏为公开55.735M盲双路MossFormer2_SS16k原核+既有Qwen。原1099张量全等，CPU/GPU波形max5.2452e-6，2s单窗原核/CSS全等，交换与尾段校验7.45e-9，保留原输入全部帧，float32双路不逐路RMS放大；本地2s/1.5s CSS拼接适配不是原wrapper逐字节重现。32原固定片段239核心前向已全部产64路，分离族峰1.145GB；ASR独立进程在转全部64路，重复/串音也计入，原32baseline复用，尚无质量提升结论、不改默认或原门。\n')
    note=Path('outputs/Companion-分离组合模型进度-20261115.txt')
    note.write_text('Companion 分离组合模型\n'+stamp+'\n\n已转到：单麦原音→双路盲人声分离→现有中英文ASR分别识别→原时间轴和人物关联。\n原模型权重/计算核保持，本地固定2秒窗/1.5秒步长处理跨块两路交换与片尾。输出保留浮点，不把每路都放大到输入响度。\n\n已完成：组件CPU/GPU、完整权重和无丢帧拼接控制；原12段多轮重叠+20段单人短回应全部分离为64路。\n正在进行：现有识别模型转写全部64路，再对比原始32段基线。两路所有词、重复、串音和空目标插入都计分，不挑一路好结果。\n本次尚未训练新的分离权重，先验证原公开分离器接入是否有效；尚无准确率改善或售卖结论，原默认和质量门保持。\nOwner无需听审、标注、账号或录音。\n',encoding='utf-8')
else:
    asr=Path(read(C/'asr-execution.json')['run']) if (C/'asr-execution.json').exists() else E/'asr-r1'
    assert read(asr/'state.json')['state']=='COMPLETE_FIXED_SEPARATION_ASR_COMPOSITION_SCORING_PENDING'
    assert (C/'decision.json').exists()
(DEST/'files').mkdir(parents=True);items=[]
def take(f,logical):
    before=f.stat();digest=sha(f);assert before.st_size<32*1024**2,(f,before.st_size)
    target=DEST/'files'/(str(len(items)).zfill(5)+f.suffix)
    shutil.copyfile(f,target);assert sha(target)==sha(f)==digest and before.st_mtime_ns==f.stat().st_mtime_ns
    items.append(dict(source=str(f),logicalPath=logical,file=target.relative_to(DEST).as_posix(),bytes=before.st_size,sha256=digest))
roots=[C]+([E/'control-r1',E/'separate-r1'] if component else [E/'asr-r1',E/'asr-r2',asr,E/'calibrated-float-r1'])
for root in roots:
    for directory,dirs,files in os.walk(root):
        dirs[:]=[n for n in dirs if n not in ['__pycache__','offline-hf-cache','matplotlib-cache']]
        for name in sorted(files):
            f=Path(directory)/name
            if f.name=='run.json':
                run=read(f);assert 'finishedAt' in run
                if 'pid' in run and 'pidCreatedAt' in run and psutil.pid_exists(run['pid']):assert abs(psutil.Process(run['pid']).create_time()-run['pidCreatedAt'])>=.01
            if f.suffix.lower() in {'.json','.jsonl','.log','.py','.txt','.npy'}:take(f,root.name+'/'+f.relative_to(root).as_posix())
if component:
    for item in read(C/'source-binding.json')['files']:take(Path(item['file']),'official-source/'+Path(item['file']).relative_to(Path(read(C/'preparation.json')['sourceRoot']).parent.parent).as_posix() if Path(item['file']).is_relative_to(Path(read(C/'preparation.json')['sourceRoot']).parent.parent) else 'official-source/'+Path(item['file']).name)
    names=['prepare_blind_separation_composition_20261115.py','prepare_blind_separator_runtime_20261115.py','inspect_blind_separator_checkpoint_20261115.py','freeze_blind_separation_composition_20261115.py']
else:names=['record_blind_separation_result_20261115.py','fix_blind_composition_asr_thread_owner_20261115.py',
            'analyze_blind_separation_waveforms_20261115.py','restore_blind_separator_common_units_20261115.py',
            'freeze_blind_separation_router_20261115.py','score_routed_blind_separation_20261115.py']
for name in names:take(Path('work')/name,'continuation-tools/'+name)
take(Path(__file__),'continuation-tools/'+Path(__file__).name)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
take(Path('outputs/Companion-分离组合模型进度-20261115.txt'),'owner-separation-composition-note.txt')
manifest=dict(state='BLIND_SEPARATOR_COMPONENT_AND_ALL_32_FLOAT_OUTPUTS_PROTECTED_ASR_PENDING' if component else 'BLIND_SEPARATION_COMPOSITION_ACTUAL_DIAGNOSTIC_RESULT_PROTECTED',
    at=datetime.now().astimezone().isoformat(),entries=items,parentCommit=parent,
    sourceAudioOrBaseWeightsCopied=False,derivedFloatSeparationOutputsCopied=component,
    newTraining=False,qualityQualified=False,d2Complete=False,productDefaultChanged=False,ownerParticipationRequired=False)
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
attrs=M/'.gitattributes';body=attrs.read_bytes();rule=(DEST.relative_to(M).as_posix()+'/** -text -whitespace').encode()
if rule not in body:attrs.write_bytes(body+b'\n'+rule+b'\n')
sources=['blind_separation_composition_20261115.py','blind_separation_worker_20261115.py','run_blind_separation_composition_20261115.py','score_blind_separation_composition_20261115.py']
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for name in paths:
    raw=(M/name).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+name],text=True).strip()==expected,name
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m',
                'Preserve blind separator component and32complete two-stream outputs' if component else 'Record complete blind separation plus localASR diagnostic and fixed decision'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt=dict(state=manifest['state'],modelCommit=head,exactByteStagedFiles=len(paths),evidenceFiles=len(items),
             evidenceBytes=sum(i['bytes'] for i in items),remoteVerified=False,d2Complete=False)
target=D/('protection-r'+str(number)+'.json');target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
result=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=120)
(D/('push-r'+str(number)+'-model.log')).write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0
result=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert result.returncode==0 and result.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
