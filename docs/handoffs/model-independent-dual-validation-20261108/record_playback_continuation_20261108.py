"""Carry the owner's acoustic-test question into the existing model work point.

This is a capability/preparation decision, not new model or hardware acceptance.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-dual-mic-independent-meetings'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ready=read(R/'docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-full-r1/model-ready.json');source=Path(ready['sourceRoot'])/'inference.py';bound=next(x for x in ready['files'] if Path(x['file'])==source);assert sha(source)==bound['sha256']
model=next(x for x in ast.parse(source.read_text(encoding='utf8')).body if isinstance(x,ast.ClassDef) and x.name=='BSRNN');forward=next(x for x in model.body if isinstance(x,ast.FunctionDef) and x.name=='forward')
mono=any(isinstance(x,ast.Assign) and any(isinstance(y,ast.Name) and y.id=='nch' for y in x.targets) and isinstance(x.value,ast.Constant) and x.value.value==1 for x in ast.walk(forward));assert mono
next_action='继续原RM-OVERLAP的单一联合提取候选：由同场说话人样音生成目标声学线索，再与原始双路空间信息共同估计提取滤波，固定同一ASR逐人比较；不能把现有单路PS4直接标成双路模型，也不以二值活动门控预先丢掉弱声。先用现有真实数字双路原音验证，不依赖扬声器；有效后再安排双路独立保存和真实采音全链条。保留原失败、普通讲话回退、严格<5%、纪要事实及双端实卡售卖未完成门。'
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'ownerQuote':'那你看看怎么再继续咯, 需要外放扬声器嘛','state':'CONTINUATION_SCOPE_CONFIRMED_NO_LOUDSPEAKER_DEPENDENCY','loudspeakerNeededNow':False,'why':'现有原始双路真实会议数字录音可隔离判断分人、分离和ASR；额外回放会叠加房间、音箱和采集影响。','laterAcousticValidation':{'singleSource':'一只扬声器播放整段混合多人录音可验收回放采音、编码、上传和转写链路，不能证明按不同方向区分不同发言人。','spatialSeparation':'至少两个独立声源，分别播放不同人的声音，或真人分别发言；三人重叠另验。先确认录音卡分别保存两路且时间一致；回放域与真人现场成绩分别报告。','hardwareStatusOnly':'board_turn status观察到1项现有占用，mayClaim=false；未访问ST-Link/COM/BLE或改固件。'},'verifiedExistingBackbone':{'repository':ready['modelId'],'revision':ready['revision'],'sourceFile':str(source),'sourceSha256':sha(source),'nativeInput':'BSRNN.forward(B,T),nch=1','directTwoChannelModel':False,'inferencePerformed':False},'technicalSource':'https://www.isca-archive.org/interspeech_2017/zmolikova17_interspeech.html','interpretation':'声纹条件神经掩码参与多麦空间滤波是候选方向，不是本机已实现或达标的模型。上一轮真值活动辅助仍237编辑错误，不重复原GSS/门控参数试验。','next':next_action,'newModelCalls':0,'newTrainingRuns':0,'newAudioPlayback':False,'newHardwareAccess':False,'newProductCodeChanges':False,'qualityQualified':False,'productDefaultChanged':False}
target=C/'playback-and-next-step.json';assert not target.exists();target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
dest=M/'evidence/20261108-dual-mic-independent-meetings/playback-and-next-step.json';shutil.copyfile(target,dest)
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15')
def git(root,*argv):
    p=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m','-c','pack.deltaCacheSize=32m','-c','core.deltaBaseCacheLimit=32m',*argv],cwd=root,env=env,capture_output=True,text=True)
    assert p.returncode==0,(p.stdout+p.stderr)[-2000:];return p.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths);git(root,'commit','--only','-m',message,'--',*paths);head=git(root,'rev-parse','HEAD');branch=git(root,'branch','--show-current');git(root,'push','origin','HEAD:refs/heads/'+branch);assert git(root,'ls-remote','origin','refs/heads/'+branch).split()[0]==head;return head
head=ship(M,['evidence/20261108-dual-mic-independent-meetings/playback-and-next-step.json'],'Record playback scope and joint model continuation');record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json'
for attempt in range(8):
    raw=path.read_bytes();d=json.loads(raw);node=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104'];assert node['ownerIndependentDualMicValidation20261108']['phase']=='complete'
    node['ownerAcousticPlaybackClarification20261108']=record;node['next']=next_action
    temp=path.with_suffix('.playback-note.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=raw:temp.unlink();continue
    try:os.replace(temp,path)
    except PermissionError as error:
        if getattr(error,'winerror',None) not in [5,32,33]:raise
        temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
    break
else:raise RuntimeError('Shared backlog busy; evidence already safe on remote')
log=R/'docs/development_log.md';marker='原RM-OVERLAP外放条件与联合模型续作澄清20261108';assert marker not in log.read_text(encoding='utf8')
with log.open('a',encoding='utf8') as f:f.write('\n\n## '+record['at']+'｜'+marker+'\n\nOwner问“'+record['ownerQuote']+'”。本轮确认当前数字模型验证不依赖外放；一只音箱混合回放不能验证多声源方向区分，真实双麦采音验收需独立声源及两路独立保存。已核验原开源BSRNN输入B,T且nch=1，不把它直接冒充双路模型。仅续作条件与源码能力检查，无模型推理／训练／播放／接板／产品功能交付，原完整失败成绩和售卖未完成状态保留。记录'+head+'已远端核验。下一项：'+next_action+'\n')
out=S/'docs/handoffs/model-independent-dual-validation-20261108';shutil.copyfile(target,out/'playback-and-next-step.json');shutil.copyfile(__file__,out/Path(__file__).name)
for f in [path,log]:shutil.copyfile(f,S/'docs'/f.name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-independent-dual-validation-20261108/playback-and-next-step.json','docs/handoffs/model-independent-dual-validation-20261108/'+Path(__file__).name],'Clarify acoustic playback conditions without blocking model work')
print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True,'newModelCalls':0},ensure_ascii=False),flush=True)
