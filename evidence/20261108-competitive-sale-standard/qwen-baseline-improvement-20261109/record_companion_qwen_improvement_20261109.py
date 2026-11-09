"""Record an evidence-led Qwen decision without changing weights or quality targets."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-competitive-sale-standard/qwen-baseline-improvement-20261109';EV=M/'evidence/20261108-competitive-sale-standard/qwen-baseline-improvement-20261109';DEST=S/'docs/handoffs/model-competitive-sale-standard-20261108/qwen-baseline-improvement-20261109'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
audit=read(C/'ordinary-r6-error-inventory.json');assert audit['strictEdits']==461 and audit['referenceCharacters']==8325 and not audit['rawTextOrScoringChanged']
path=R/'docs/product_backlog.json';d=read(path)
def task(d):return d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'at':at,'ownerQuote':'完整会议基线错误率再怎么压，换模型还是在千问基础上改善？','decision':'Keep Qwen3-ASR1.7B as the retained ASR backbone. Do not immediately replace it, increase model size, change weights or start fine-tuning. Ordinary remaining errors need verified cross-meeting causes; complex overlap requires source/content recovery rather than only another generic ASR checkpoint.','currentEvidence':{'bestOrdinaryCharacters':8325,'bestOrdinaryErrors':461,'bestOrdinaryCer':461/8325,'errorsAtStrictUnder5Maximum':416,'netErrorsRequired':45,'fixed30sErrors':480,'lowEnergyBoundaryNetGain':19,'complexFixed30sChronologicalCer':0.23155832180728447,'wholeModelQualityQualified':False},'newAudit':{'source':str(C/'ordinary-r6-error-inventory.json'),'sha256':hashlib.sha256((C/'ordinary-r6-error-inventory.json').read_bytes()).hexdigest(),'newNeuralCalls':0,'strictEditsUnchanged':461,'inspectionTags':audit['editsByInspectionTag'],'interpretation':'Groups/tags overlap and are not listening-confirmed causes. Number regex also matches nonnumeric一/点/分; do not call all tagged edits numerical mistakes. Filler/儿 differences are not a justification to delete reference words or change strictCER. Negation and lexical content must be audited separately before adaptation.'},'improvementOrder':[
 'Freeze the native1.7B fixed30s whole-meeting baseline and keep the5.54% boundary variant as a single-meeting candidate; the tested boundary-only change gained19edits and did not cross5%, so no further boundary/threshold sweep without a distinct proven cause.',
 'Check whether persistent substantive errors recur across different real meetings and whether the reference words agree with the original audio before creating adaptation labels. Handle actual names, quantities, negation and lexical mistakes before optimizing superficial score differences. Existing audio coverage/native weight equivalence proofs are reused, not re-run as a ritual.',
 'Where a real user provides agenda, names or domain vocabulary before recognition, test the official prompt/context interface with that source only and preserve a no-context route. Never derive hotwords from reference answers or silently use a language model to rewrite what was said.',
 'For true overlap retain the independent automatic-speaker-profile/separation workpoint: validate the17already-selected profiles, extract predicted simultaneous voices separately, then use the same ASR; ordinary speech bypasses separation. Profile preparation does not establish content recovery.',
 'Fine-tuning/adapter work is justified only after enough independently checked, authorized real-meeting audio/text exposes a stable recognizer error, with meetings/speakers separated between adaptation and evaluation. Freeze old model, protect ordinary content and key facts, and use heldout meetings; no one-meeting memorization.',
 'Replace the backbone only when a mature challenger wins a predeclared same-audio comparison across multiple meetings without protected-path regressions and within measured CPU/system-RAM/device limits. A headline score or one sample is insufficient. No from-scratch foundation-model plan is supported by current evidence.'
 ],'officialSupport':[{'url':'https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf','supports':'Native Transformers input supports language and prompt context/hotwords, and documents training/fine-tuning. Context support is not proof of an accuracy gain on our meetings.'},{'url':'https://github.com/QwenLM/Qwen3-ASR','supports':'Official inference, timestamps and finetuning references; timestamp alignment does not itself correct recognition words.'}],'previousWorkpoint':task(d)['next'],'next':'普通整会保留Qwen3-ASR1.7B，优先将不同真实会议的实词/数字/否定/漏词候选核到原音与独立标注，确定跨会稳定错误后只验证一项有依据的改动；现有5.54%缺45净错误，不再无依据扫切分/解码或立即微调。用户真实事先词表可按官方context作独立对照，无词表路径保留、不喂参考答案。复杂线原17段自动声纹稳定性→仅预测重叠逐人分离→同一ASR续作，不能拿标签修正代替恢复漏话。只有跨会议同音对照证明更强且资源合适才换底座，微调需可靠数据与独立验证。原普通/逐人<5%、说话人、关键事实、独立整会、完整构建/双端实卡与售卖门保留。','newInferenceOrTraining':False,'newAccuracyGainClaimed':False,'weightsChanged':False,'productDefaultChanged':False,'targetsChanged':False,'saleQualified':False}
write(C/'decision.json',record)
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';functions=[n for n in ast.parse(publisher.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']];exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
assert not git(M,'status','--porcelain') and not git(S,'status','--porcelain')
for file in C.iterdir():
 if file.is_file():EV.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,EV/file.name)
shutil.copyfile(__file__,EV/Path(__file__).name);head=ship(M,['evidence/20261108-competitive-sale-standard/qwen-baseline-improvement-20261109'],'Keep Qwen backbone and audit the remaining full-meeting error budget')
record.update(modelEvidenceCommit=head,remoteReadbackConfirmed=True);write(C/'decision.json',record);quality=d['quality_targets'];log=R/'docs/development_log.md';prefix=log.read_bytes()
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);n=task(d);n['ownerCompetitiveSaleStandard20261108']['qwenBaselineImprovement20261109']=record;n['next']=record['next'];n['ownerCompetitiveSaleStandard20261108']['next']=record['next'];temp=path.with_suffix('.qwen-improvement.tmp');write(temp,d)
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path);break
 except PermissionError:temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2))
else:raise RuntimeError('Original backlog busy; evidence preserved')
assert read(path)['quality_targets']==quality
marker='原模型任务千问底座改善而非盲换20261109';assert marker.encode('utf8') not in prefix
entry='\n\n## '+at+'｜'+marker+'\n\nOwner问完整会议基线继续压错率应换模型还是改善千问。保留Qwen1.7B作底座，暂不换更大checkpoint或启动微调。复用原审计器核对最佳低能量切分完整S：8325参考字/461错误=5.53754%，严格<5%需<=416即净减45；切分相对固定版本仅净减19，原预定停止继续保持，不再扫切分。新剩余误差清单使用原输出/参考/评分，严格分数未变；儿化/停顿/数字候选与实词/否定分开，标签重叠且未经核听，数字正则包含普通一/点/分，不能冒充已确定根因或删词刷分。官方原生接口支持事先真实context词表和微调路径，但不证明当前收益；不喂参考答案、不用LLM无依据润色原文。下一步按跨会稳定实错决定一次改动，有可靠标注与独立集才适配权重，换底座需同音跨会胜出。复杂线原自动参考→预测重叠分离→同ASR保留。当前6800XT在PnP可见只是设备观察，本轮无新模型推理/训练、无准确率提升、无安装；源码/权重和原门未改。证据'+head+'已推送核验。下一项：'+record['next']+'\n'
with log.open('ab') as f:f.write(entry.encode('utf8'))
for file in [path,log]:shutil.copyfile(file,S/'docs'/file.name)
for file in C.iterdir():
 if file.is_file():DEST.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,DEST/file.name)
shutil.copyfile(__file__,DEST/Path(__file__).name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-competitive-sale-standard-20261108/qwen-baseline-improvement-20261109'],'Record evidence-led Qwen improvement and preserve complex separation workpoint')
print(json.dumps({'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True,'targetsUnchanged':read(path)['quality_targets']==quality,'timelinePrefixPreserved':log.read_bytes().startswith(prefix),'newInferenceOrTraining':False,'newAccuracyGainClaimed':False,'saleQualified':False},ensure_ascii=False),flush=True)
