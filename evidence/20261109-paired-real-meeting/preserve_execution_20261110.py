"""Preserve continuation in the original task, timeline, research and app remotes."""
from pathlib import Path
from datetime import datetime
import argparse,ast,copy,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=Path(__file__).parent
P=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109')
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['checkpoint','complete'],required=True);a=p.parse_args()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=datetime.now().astimezone().isoformat(timespec='seconds')
task=P/'fixed-native-r2-runs/near-N_SPK8013/task.json'
assert read(task)['state']=='INCOMPLETE_RETAINED_RESUMABLE'
shutil.copy2(task,C/'fixed-native-r2-stop-receipt.json')
for name in ['resources.jsonl','native-attempt-0001.log']:
    shutil.copy2(task.parent/name,C/('fixed-native-r2-'+name))
failure=P/'mobile-product-baseline/instrumentation-command-failure.txt'
shutil.copy2(failure,C/'mobile-product-baseline/instrumentation-install-failure.txt')
score=read(C/'product-five-source-ci/score.json') if (C/'product-five-source-ci/score.json').exists() else None
decision=read(C/'paired-product-decision20261110.json') if (C/'paired-product-decision20261110.json').exists() else None
if a.phase=='complete':assert score and decision and decision['state']=='COMPLETE_DEPLOYED_MODEL_PAIRED_SOURCE_AND_KNOWN_ACTIVITY_DIAGNOSTICS_NOT_QUALIFIED'
next_point=('保留当前产品Paraformer和Qwen固定基线。对照本批完整近讲逐人漏字/替换/插入与远场原混音，先按插入/丢字和同场串音证据定位一个可归因模块，不把混音全文CER与逐人CER直接相减；不扫新模型、不用Eval训练。Qwen本机原近讲任务因实际Windows低内存、加载前停止，资源发生实质恢复后先刷新6800XT身份/ordinal，保持原包和断点显式续作；CPU5%/private2GiB/真实低内存停止不放宽。继续原严格<5%、未见会议/最终留出、自动分人/重叠、纪要事实和双端实卡门，软件081/115已验交付路径复用。' if score else '独立CI42652152343正在顺序执行同一公开AliMeeting四路近讲和一路原始远场共同覆盖音频，使用当前产品固定Paraformer原生CLI；收齐五输出后独立按对应逐人参考/混音参考评分，不混比口径。Qwen原任务因本机实际低内存在模型加载前停止，保留断点不原样自动重跑。继续原软件081/115已验范围和未完成模型/实卡门，不回退旧062/110或重做已过文件流程。')
if decision:next_point=decision['next']
record={'at':now,'phase':a.phase,'state':decision['state'] if decision else score['state'] if score else 'FIXED_PRODUCT_FIVE_INPUTS_RUNNING_ON_DEDICATED_CI_LOCAL_QWEN_STOPPED_BEFORE_MODEL','ownerLatest':'需要继续推进','root':str(C),'sourceTask':'owner_module_execution.frontendWindowsMobile20261102.ownerCoreDeliveryPriority20261104.ownerNightGpuModelPriority20261104.ownerPairedRealMeetingSource20261109','currentProductPair':read(C/'product-existing-pair/result.json'),'savedMinutesReview':{'state':read(C/'product-existing-pair/saved-minutes-fact-review.json')['state'],'receipt':'product-existing-pair/saved-minutes-fact-review.json','allFactsQualified':False},'productFiveInputScore':score,'pairedDiagnosticDecision':decision,'dedicatedCi':{'runId':42652152343,'testSource':'98bcca6a94d3fdfe379108a11856948dd39194a9','url':'https://github.com/Listener-ai-Macau/Companion-Type/actions/runs/42652152343','publicInputAsset':728094471,'knownActivityRunId':42654977467 if decision else None,'knownActivityTestSource':'47297dae29314ee6c2f993aa19a89210bddab82c' if decision else None,'knownActivityPublicInputAsset':728148741 if decision else None,'published':False,'newModelFamily':False,'nativeUiNotInvoked':True},'localQwen':{'inventory':read(C/'fixed-asr-night-r2/hip-inventory.json')['selected'],'attempt':read(task)['attempts'][-1],'modelLoaded':False,'neuralCalls':0,'frozenPackChanged':False,'qualityFailure':False,'resumeBindingPreparedNoModel':True},'phoneComparator':read(C/'mobile-product-baseline/closed-unstarted.json'),'originalSoftwareVersions':{'windows':'0.1.81','android':'0.1.115','productApkChangedThisContinuation':False},'newTrainingRuns':0,'newAccuracyGain':False,'newIndependentMeetings':0,'finalHoldoutOpened':False,'formalQualityTargetsChanged':False,'newCustomerEvaluationPerformed':False,'saleQualified':False,'next':next_point}
(C/'execution20261110.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
module=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-preserver','exec'),scope);ship=scope['ship']
EV=M/'evidence/20261109-paired-real-meeting';EV.mkdir(exist_ok=True)
def mirror(source,target):
    for f in source.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix in ['.json','.jsonl','.txt','.log','.py']:
            assert f.stat().st_size<4*1024**2,'Unexpected large file; inspect before preserving'
            dest=target/f.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
mirror(C,EV)
attr=M/'.gitattributes';text=attr.read_text(encoding='utf8')
for line in ['evidence/20261109-paired-real-meeting/** -text -whitespace','src/run_paired_fixed_asr_20261109.py -text','src/*paired_product_asr*20261110.py -text','src/audit_*20261110.py -text','src/CompanionPairedPhone*20261109.java -text']:
    if line not in text:text+='\n'+line+'\n'
attr.write_text(text,encoding='utf8')
if a.phase=='complete':
    doc=M/'README.md';marker='Paired product ASR continuation,2026-11-10'
    assert marker not in doc.read_text(encoding='utf8')
    with doc.open('a',encoding='utf8') as f:f.write('\n\n'+marker+': actual deployed Paraformer raw-WAV Windows and COP1 Android outputs from the same S_R004S03C01 yield strict chronological CER6.4024024% and6.6306306%; platform/segmentation differ, so0.2282282pp is not isolated codec damage. Both miss5%. A fresh6800XT inventory passed; local frozenQwen first1551.82s headset task stopped on actual Windows low RAM before model load, with0neural calls and no automatic retry. Dedicated CI42652152343 completed five raw public paired inputs with deployed Paraformer: raw-far chronological CER40.7559496%, known-headset aggregate140.8026132% dominated by14320insertions.59target-absent input windows literally match other speakers for>=12characters. A separate preregistered known-reference-activity arm42654977467 keeps full timelines/all four people, preserves target-intervalPCM+fixed150ms padding bit-exact and zeros outside. Against unchanged full references it has aggregate9.6033598% (person13.6577/7.1332/6.6970/7.7931%),0of4below5%; insertions292whileS+D737versus raw767. This is not automatic speaker/quality gain or isolated ASR causality: residual crosstalk, timing and gating/context effects remain. Full raw results, fixed protocol, costs and distinctions are in evidence/20261109-paired-real-meeting/execution20261110.json. Do not compare far chronological CER directly with source aggregate; close headsets are not clean targets. No new family/training/default change, holdout or sale pass.\n')
paths=['.gitattributes','evidence/20261109-paired-real-meeting','src/run_practical_qwen_native_20261107.py','src/run_paired_fixed_asr_20261109.py','src/score_paired_product_asr_20261110.py','src/audit_existing_product_asr_pair_20261110.py','src/audit_saved_phone_minutes_facts_20261110.py','src/audit_paired_headset_crosstalk_20261110.py','src/prepare_paired_known_activity_control_20261110.py','src/review_paired_product_diagnostics_20261110.py','src/CompanionPairedPhoneAsr20261109.java','src/CompanionPairedPhoneInstrumentation20261109.java']+(['README.md'] if a.phase=='complete' else [])
model_head=ship(M,paths,'Preserve matched product ASR and low-memory continuation '+a.phase)
record['sourceAndEvidenceCommit']=model_head;record['remoteReadbackConfirmed']=True
path=R/'docs/product_backlog.json'
for attempt in range(8):
    original=path.read_bytes();d=json.loads(original);targets=copy.deepcopy(d['quality_targets']);f=d['owner_module_execution']['frontendWindowsMobile20261102'];night=f['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104'];node=night['ownerPairedRealMeetingSource20261109']
    node['execution20261110']=record;node.update(status=record['state'],next=next_point);night.update(status=record['state'],next=next_point)
    f.update(at=now,state='WINDOWS081_ANDROID115_CORE_MEETING_SOFTWARE_DELIVERED_MODEL_QUALITY_CONTINUES',result='Windows081与Android115本批完整会议处理及文件交付按已验范围保留；当前产品相同公开整会严格CER为Windows6.40%、手机6.63%，复杂多人继续按原配对实会定位。整体售卖和原实卡/模型质量门未完成。',next=next_point)
    nxt=d['owner_module_execution']['nextBatch']
    if 'continuationBefore20261110' not in nxt:nxt['continuationBefore20261110']={k:nxt.get(k) for k in ['at','status','next','ownerLatest']}
    nxt.update(at=now,status=record['state'],ownerLatest='需要继续推进',next=next_point+' 固件和实卡未验项沿owner_module_execution.embedded.next当前工作点，不用旧固件版本或旧手机安装步骤替代。')
    assert d['quality_targets']==targets
    temp=path.with_suffix('.paired-execution.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=original:temp.unlink();continue
    os.replace(temp,path);break
else:raise RuntimeError('Canonical backlog changed concurrently; source already preserved')
log=R/'docs/development_log.md';marker='配对真实会议与双端现用识别续作20261110-'+a.phase
assert marker not in log.read_text(encoding='utf8')
with log.open('a',encoding='utf8') as f:f.write('\n\n## '+now+'｜'+marker+'\n\n承接Owner“需要继续推进”。当前产品同源完整38分47秒会议已保存转写统一评分：Windows533/8325=6.4024024%，Android552/8325=6.6306306%，两端387处同字替换/删除；路径同时包含平台、分段及codec差别，不把净差0.2282282pp冒称纯压缩影响。严格目标不改，记录7项已保存纪要数值的声明抽查，非全会事实门。GPU身份已实际确认6800XT ordinal1；第一次inventory模型前实际低内存停止旧终态误留PREPARING，已保留原收据并修启动前终态；短暂RAM恢复后第一路原Qwen近讲在36.496s、私有峰422416384B、可用715059200B时实际低内存保护停止，未加载模型、0新神经调用、非模型质量失败。保留不可变包、断点，修同卡新inventory时间戳不破坏绑定及中断只停自有作业；未放宽5%CPU/2GiB、未关闭其它应用。手机独立app_process返回0但无状态文件，撤回假启动收据；测试instrumentation安装受限，未再试，产品APK/原资料/主屏未动，已清自有公开暂存并释放手机。独立CI42652152343按固定产品Paraformer顺序执行5份原始WAV，无新模型/训练/参考输入/Owner前台操作；本阶段状态：'+record['state']+'。M来源与证据'+model_head+'已推送并远端SHA核验。原081/115交付及失败保留，不称整机/客户/售卖合格。下一项：'+next_point+'\n')
if decision:
    with log.open('a',encoding='utf8') as f:f.write('\n同批第二固定对照也已完成（CI42654977467）：各人的参考讲话区间加固定150ms前后保留，其余置零，四人完整时间轴、不改原PCM、不作生产自动算法；逐人CER13.657693/7.133152/6.697039/7.793058%，合计1029/10715=9.6033598%，0/4低于5%。相同人参考下插入14320→292，替换+删除767→737；59个目标参考未发声窗口有至少12字匹配其他人原话，不能把近讲整路当干净目标或把所有插入当幻觉。原始远场全文顺序诊断4367/10715=40.75595%，不直接与逐人聚合相减。原始每输入约91–99s、私有采样峰约339MiB，已知活动约60–90s；均独立Windows原生后端成本，非手机/实卡/纪要交付延迟。剩余错漏仍混合识别、同时串音、标注时序及置零/分段上下文影响，暂不能分别定因。固定两臂均保留全部原始输出/哈希/耗时；不继续扫描控制参数，当前识别/分人/事实/售卖仍未合格。\n')
dest=S/'docs/handoffs/model-paired-real-meeting-20261109';dest.mkdir(exist_ok=True);mirror(C,dest)
(dest/'execution-preservation20261110.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for f in [path,log]:shutil.copy2(f,S/'docs'/f.name)
head=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-paired-real-meeting-20261109'],'Record same-task paired product ASR continuation '+a.phase)
print(json.dumps({'state':record['state'],'modelCommit':model_head,'mainCommit':head,'remoteReadbackConfirmed':True},ensure_ascii=False))
