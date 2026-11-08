"""Preserve this same RM-OVERLAP review without taking the live board or app."""
from pathlib import Path
from datetime import datetime
import json,os,shutil,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261108-dual-mic-architecture-review';EV=M/'evidence/20261108-dual-mic-architecture-review'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
review=read(C/'review.json');assert not review['qualityQualified'];EV.mkdir(exist_ok=True)
for p in C.glob('*.json'):shutil.copyfile(p,EV/p.name)
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*args):
    deadline=time.monotonic()+45
    while True:
        p=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m',*args],cwd=root,env=env,capture_output=True,text=True)
        if p.returncode and 'index.lock' in p.stderr and 'File exists' in p.stderr and time.monotonic()<deadline:time.sleep(1);continue
        if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-4000:])
        return p.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths)
    if git(root,'diff','--cached','--name-only','--',*paths):
        git(root,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths)
        git(root,'commit','--only','-m',message,'--',*paths)
    h=git(root,'rev-parse','HEAD');b=git(root,'branch','--show-current');git(root,'push','origin','HEAD:refs/heads/'+b)
    assert git(root,'ls-remote','origin','refs/heads/'+b).split()[0]==h
    return h
source_names=['companion_multichannel_input_20261108.py','check_companion_multichannel_input_20261108.py','review_companion_dual_mic_architecture_20261108.py']
model_head=ship(M,['.gitattributes','README.md','evidence/20261108-dual-mic-architecture-review',*['src/'+n for n in source_names]],'Preserve channel-aware speaker-first architecture review')
now=datetime.now().astimezone().isoformat(timespec='seconds')
record={'at':now,'state':review['state'],'ownerOriginal':review['ownerOriginal'],'ownerCorrection':review['ownerCorrection'],
    'sourceAndEvidenceCommit':model_head,'remoteReadbackConfirmed':True,'review':str(C/'review.json'),
    'inputIntegrityReview':str(C/'input-integrity-review.json'),'previousModelWorkpoint':review['previousModelWorkpoint'],
    'normalStoredChannels':1,'channelAwareResearchInputImplemented':True,'realArchivedPairsChecked':2,
    'currentDeviceSpeakerSeparationQualified':False,'productDefaultChanged':False,'newModelsOrTraining':0,
    'newBoardAccess':False,'next':review['next'],'qualityQualified':False}
path=R/'docs/product_backlog.json'
for attempt in range(5):
    raw=path.read_bytes();d=json.loads(raw)
    node=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
    node['ownerDualMicArchitectureReview20261108']=record
    node.update(status=record['state'],next=record['next'],ownerQuote=review['ownerOriginal']+'；更正：先区分后转写')
    gate=next(g for g in d['quality_targets']['real_meeting_model_contract_20261103']['gates'] if g['id']=='RM-OVERLAP')
    gate['dualMicArchitectureReview20261108']={'state':record['state'],'sourceAndEvidenceCommit':model_head,'evidence':record['review'],'qualified':False}
    if path.read_bytes()!=raw:continue
    temp=path.with_suffix('.dual-mic-review.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=raw:temp.unlink();continue
    os.replace(temp,path);break
else:raise RuntimeError('Concurrent shared backlog changed; model source is already safe, do not overwrite other work')
log=R/'docs/development_log.md';marker='原RM-OVERLAP双麦架构复核20261108';assert marker not in log.read_text(encoding='utf8')
with log.open('a',encoding='utf8') as stream:
    stream.write('\n\n## '+now+'｜'+marker+'\n\nOwner要求“'+review['ownerOriginal']+'”，随后更正“转写”。保留此前两版活动小头失败及oracle局部对照，不再沿该小头调参。实际源码审计：当前66734/25e108f采音正常选择LEFT、编码/帧格式/APM1为单声道，Windows保留导入原文件但ASR派生会下混/可能改极性，Android完整后端及独立模型入口为mono。因此推荐先重构独立双路原音输入，再走说话人活动→内部引导式空间分离→逐人转写→共享Document/纪要；公开GSS/CHiME等为依据，但未证明两颗近距麦或本机AMD/CuPy可直接达到效果。已实现独立无损双路研究输入：两份历史实板2秒同步双路样本按137帧分块后逐字节重组一致，反相保持、单麦冒充双路和复制立体声拒绝过。只证明输入信息未丢，不是多人识别/分离交付。旧样本不是当前硬件几何资格；旧相似度0.9966仅对应当时有限声源摆法，不扩大为双麦永远无效。低码率立体声可能丢声道差异，两路16kbps裸负载14.4MB/h，需共同评估16MiB存储/两小时离线、实时CPU/RAM/续航/传输。当前两小时长录未接管，0板IO/刷包/安装/新模型/训练，原普通ASR与全部<5%/纪要事实/双端实卡/售卖门保留。源码与证据'+model_head+'已远端核验。下一步：'+record['next']+'\n')
dest=S/'docs/handoffs/model-dual-mic-architecture-20261108';dest.mkdir(exist_ok=True)
for p in [path,log]:shutil.copyfile(p,S/'docs'/p.name)
(dest/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
shutil.copyfile(__file__,dest/Path(__file__).name)
main_head=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-dual-mic-architecture-20261108'],'Record dual-mic architecture and preserve current workpoint')
print(json.dumps({'state':record['state'],'modelCommit':model_head,'mainCommit':main_head,'remoteReadbackConfirmed':True,'boardAccessed':False,'newModelRuns':0}),flush=True)
