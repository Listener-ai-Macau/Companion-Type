"""Continue the same metric/competitive decision, retaining all original quality gates."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-competitive-sale-standard';EV=M/'evidence/20261108-competitive-sale-standard';DEST=S/'docs/handoffs/model-competitive-sale-standard-20261108';W=Path(__file__).parent
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';functions=[n for n in ast.parse(publisher.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']];exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
for repo in [M,S]:assert not git(repo,'status','--porcelain')
at=datetime.now().astimezone().isoformat(timespec='seconds');review=read(C/'prefix-quality-review.json');probe=read(C/'existing-service-probe.json');run=read(C/'prefix-run.json')
assert run['state']=='COMPLETE_PUBLIC_PREFIX_REFERENCE_ASR_REVIEW_REQUIRED' and not review['saleQualified']
interpretation={
 'at':at,'ownerQuote':'你判断一下我们那个指标是不是一个合理的指标，然后就跟着我们那个指标去继续优化就好。感觉这个东西还是主要是靠软件去优化吧。',
 'judgment':'指标方向合理，保留全部原数值。分清研发阶段、固定验收集结果和未来使用保证；软件主攻身份/内容/事实，不把音量变小或文档数量当进展。',
 'items':[
  {'id':'QM04','decision':'普通真实会议严格CER<5%是合理且继续追求的质量目标；每场及逐人统计，单场/拼接/短片达到不代表通用。','guard':'保留插删替和关键字段，阅读去语气词与原始逐字稿分开，不能为评分删原词。'},
  {'id':'QM05','decision':'自动分人DER<=10%为正式目标，<=15%仅阶段；保持原零宽容、含重叠口径。','guard':'同口径才比较；已知声纹命中率不是自动分人，人数正确也不抵消漏掉整位发言者或短回应。'},
  {'id':'RM-OVERLAP','decision':'真实重叠逐人CER<5%属于有挑战的研发/验收目标，不是行业普遍保证。数值不降低，失败保持开放；双人/三人分开。','guard':'重点看漏掉多少真实词、是否串人和整路消失；减少插入但增加真实讲话删除不能以平均总分晋级。'},
  {'id':'QM06','decision':'原事实覆盖>=95%、决定/负责人/期限/金额/否定100%正确及关键无根据结论0，解释为固定人工事实验收集要求，不是对任意未来会议的零错误承诺。','guard':'姓名/角色/期限无依据保持未知，建议不变决定；对原音事实核对，忠于错误转写仍失败。'},
  {'id':'QM07-LONG','decision':'初始长会RTF<=1只是研发起步门；1小时等1小时不能据此宣称有竞品般会后速度。准确达标后再确定目标设备的产品等待指标。','guard':'分开实时流与离线文件，停录后等待与文件就绪后总处理；按原规则样本不足20不报P95。当前近实时发送的服务对照不是极速批处理测速。'},
  {'id':'QM09','decision':'原至少3场>=30分钟、跨房间、独立留出及双端/实卡链为最低工程资格，不证明所有客户场景通用。','guard':'当前刻意选择困难窗口只诊断，不是完整会议，不代表真实卡近双麦或无噪声/任意距离。原留出未打开。'},
 ],
 'supplementaryUsabilityMeasure':'在有实际用户验收时记录一场会需要修改的关键事实数、修订耗时和是否完成其目的；暂未实测，不设虚构时长成绩或用AI模拟修订代替真人负担。',
 'hardwareBoundary':'主要优化工作在软件：稳定解码/分人/分离/转写/事实校验与使用流程。采音仍需不丢样、不削波并完整传回原音；软件不承诺恢复根本未采到的信息。双麦数目本身不证明可分离。',
 'sources':[
  {'url':'https://pyannote.github.io/pyannote-metrics/reference.html','supports':'DER明确支持collar和skip_overlap，比较必须固定边界/重叠口径。'},
  {'url':'https://github.com/fgnt/meeteval','supports':'会议转写分别有cpWER/tcpWER等评估；单一混合文字错误率不能验证谁在何时说了什么。中文按原字符口径执行，缺少真实词时标不补造。'},
 ],
 'originalThresholdsChanged':False,'currentSaleQualificationChanged':False,
}
write(C/'metric-review.json',interpretation)
p=read(C/'benchmark-protocol.json');p['metricInterpretation']=interpretation;p['status']='FIXED_PUBLIC_STRESS_SERVICE_DIAGNOSTIC_COMPLETE_NOT_COMPETITOR_OR_FULL_MEETING';p['noNewInferenceOrTraining']=False;p['newLocalTrainingOrInference']=False;p['executionEvidence20261108']={'existingServiceProbe':probe,'publicStressDiagnostic':str(C/'prefix-quality-review.json'),'liveCompetitorProductResultsAvailable':False};write(C/'benchmark-protocol.json',p)
assessment=read(C/'assessment.json');assessment['metricReview20261108']=interpretation;assessment['existingServiceProbe']=probe;assessment['publicStressDiagnostic']=review;assessment['previousWorkpointBeforeStressDiagnostic']=assessment['next'];assessment['state']='METRICS_REVIEWED_PUBLIC_COMPLEX_SERVICE_DIAGNOSTIC_NOT_QUALIFIED'
assessment['observedEvidence']['currentApplicationAdapters']='既有Windows适配器代码已查；读取其明确兼容的旧服务目标，在内存中使用凭据，一秒静音服务检查通过，固定公开真实会议困难窗已完成实际调用；未升级服务、未读/传私人录音、未改产品默认。仍不是实际竞品应用成绩。'
if review.get('cpCer') and review.get('strictWindowCerBelow5'):
 next_action='当前困难窗文字仅局部通过；先核对逐人身份/漏词与事实，随后冻结已有服务和本地候选的完整会议同音比较，原最终留出仍不用于选型。'
else:
 next_action='现有服务37段均返回同一人物0：先对照官方多人能力契约及既有Windows请求/资源/输出路径定位，不能按这次人物塌缩把所有商业模型判差；没有可证实变化不重发五分钟或扩展整会。原最难002/003/007身份条件复核继续，只有能保护目标内容的最小修复才做下一次验证。'
assessment['next']=next_action+' 保留普通严格CER<5%、分人DER<=10%、真实重叠逐人<5%、事实、双端实卡及售卖门；固定多段参考库保留、128步退化候选拒绝。'
assessment['newModelTrainingOrInference']=True;assessment['newLocalTrainingOrInference']=False;assessment['newConfiguredServiceInference']=True;assessment['thisBatchIsDecisionAndProtocolNotCapabilityImprovement']=False;assessment['capabilityImprovementProven']=False
write(C/'assessment.json',assessment)
for file in C.iterdir():
 if file.is_file() and file.suffix in ['.json','.jsonl','.txt']:shutil.copyfile(file,EV/file.name)
scripts=['probe_existing_companion_asr_20261108.py','prepare_companion_commercial_prefix_20261108.py','run_companion_commercial_prefix_20261108.py','score_companion_commercial_prefix_20261108.py','preserve_companion_metric_review_20261108.py']
for name in scripts:shutil.copyfile(W/name,EV/name)
head=ship(M,['evidence/20261108-competitive-sale-standard'],'Validate existing ASR on a frozen real overlapping meeting window')
assessment['sourceAndEvidenceCommit']=head;assessment['remoteReadbackConfirmed']=True;write(C/'assessment.json',assessment)
path=R/'docs/product_backlog.json';before=read(path);quality=before['quality_targets'];oldlog=(R/'docs/development_log.md').read_bytes()
def task(d):return d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);n=task(d);assert n['ownerCompetitiveSaleStandard20261108']['sourceAndEvidenceCommit']=='512a8643ec420e860ae3bdf3b7d8034d98993b58';n['ownerCompetitiveSaleStandard20261108']=assessment;n.update(status=assessment['state'],next=assessment['next']);temp=path.with_suffix('.metric-review.tmp');write(temp,d)
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path);break
 except PermissionError:temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2))
else:raise RuntimeError('Original backlog busy; evidence preserved')
assert read(path)['quality_targets']==quality
marker='原模型任务指标合理性与真实困难窗20261108';log=R/'docs/development_log.md';assert marker.encode('utf8') not in log.read_bytes()
metric=review.get('cpCer') or {};brief={'audioSeconds':review['audioSeconds'],'referencePeople':review['referencePeople'],'overlapFraction':review['referenceOverlapFraction'],'cpCer':metric.get('characterErrorRate'),'identityContract':review.get('identityContractDiagnostic'),'mixedChronologicalDiagnostic':review.get('mixedChronologicalDiagnostic'),'perPerson':review['perReferencePerson'],'wallSeconds':run['wallSeconds'],'privatePeakBytes':run['privatePeakBytes'],'provider':run['providerGeneration'],'liveCompetitorProductTested':False,'saleQualified':False}
entry='\n\n## '+at+'｜'+marker+'\n\n承接Owner“判断指标合理性，按指标继续优化，软件为主”。复核后保留原数字/范围，澄清重叠<5%是挑战目标、关键事实100%为固定验收集要求、RTF1仅起步门，未降低售卖门。既有服务静音检查通过并实际执行固定公开真实会议困难窗：'+json.dumps(brief,ensure_ascii=False)+'。这是刻意困难开发片非整会/竞品应用/新本地模型改善，真实活动DER、纯重叠词CER和tcpCER缺词时标不补造。准备期PY缺PraatIO后复用现有干净评分环境；原最初305秒仅0.91%重叠、未推理，保留原件后在任何语音提交前按固定最大重叠规则选新窗。未升级服务、不打印凭据、不上传私人录音、不接管前台。证据'+head+'已远端核验。结果与剩余：'+review['decision']+' 下一项：'+assessment['next']+'\n'
entry=entry.replace('未升级服务、不打印凭据','首次评分在512MiB限制下SciPy依赖导入MemoryError；限制数值库单线程并沿原2GiB上限后，复用同一响应完成评分，没有重发音频。未升级服务、不打印凭据')
with log.open('ab') as f:f.write(entry.encode('utf8'))
assert log.read_bytes().startswith(oldlog)
for file in [path,log]:shutil.copyfile(file,S/'docs'/file.name)
for file in C.iterdir():
 if file.is_file() and file.suffix in ['.json','.jsonl','.txt']:shutil.copyfile(file,DEST/file.name)
for name in scripts:shutil.copyfile(W/name,DEST/name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-competitive-sale-standard-20261108'],'Keep original quality targets and record real complex service diagnostic')
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':assessment['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True,'originalQualityTargetsUnchanged':read(path)['quality_targets']==quality,'oldTimelinePrefixPreserved':log.read_bytes().startswith(oldlog),'workingTreesClean':all(not git(repo,'status','--porcelain') for repo in [M,S]),'next':task(read(path))['next'],'saleQualified':False,'capabilityImprovementProven':False}
write(C/'metric-review-preservation.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
