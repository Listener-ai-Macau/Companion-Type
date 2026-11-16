from pathlib import Path
from datetime import datetime
import json,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1/stagea-cpu-composition-r2';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/stagea-cpu-composition-r2')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
score=read(C/'score.json');assert score['state']=='CPU_WINDOW_COMPOSITION_SCORED_NOT_PRODUCT_QUALIFIED'
run=read(E/'run.json');assert run['completedCases']==32 and run['workerExitCode']==0
obs=[json.loads(s) for s in (E/'physical-resource-observations.jsonl').read_text().splitlines()]
receipt={'at':datetime.now().astimezone().isoformat(),'state':score['state'],'scoreFile':str(C/'score.json'),'scoreSha256':sha(C/'score.json'),
 'groups':score['groups'],'meetings':score['meetings'],'runFile':str(E/'run.json'),'runSha256':sha(E/'run.json'),
 'all32InputsNaturalEos':True,'audioSeconds':sum(r['audioSeconds'] for r in score['cases']),'inferenceSeconds':sum(r['seconds'] for r in score['cases']),
 'privatePeakBytes':read(E/'inference-state.json')['limits']['jobPeakPrivateCommitBytes'],
 'observedFamilyWorkingSetPeakBytes':max(sum(y['workingSetBytes'] for y in x['family']) for x in obs),
 'observedCpuPercentPeak':max(x['totalMachineCpuPercent'] for x in obs),'observedSystemAvailableMinBytes':min(x['systemAvailableBytes'] for x in obs),
 'completeCpuSpeakerRuntimeUnmeasured':True,'qualityQualified':False,'saleQualified':False,'wholeMeetingAcceptance':False,'productDefaultChanged':False,
 'selection':'Both validation languages raw and attributed errors improved under one frozen recipe; advance this same CPU/native candidate to exact complete original4 recordings with metadata-only30s fixed nonoverlap chunks, not annotation-selected clips. No new models/weights/hyperparameter grid.'}
(C/'decision.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];d['state']='DAY_CPU32_COMPOSITION_SCORED_IMPROVED_NOT_QUALIFIED';o.update(currentState=d['state'],activePid=None,noOwnNeuralProcessActive=True,cpuWindowResult=receipt)
d['next']='同一固定组合继续：CPU原生MOSS短窗+全会Nemotron身份。32条全部自然EOS，英文验证raw19.89→17.49%、带人34.41→18.76%，中文5.80→5.01%、带人5.96→5.09%，尚未合格；CPU25%/4线程、2GiB私有保护内ASR用492s处理739s音频，完整CPU说话人仍待实测。下一步原4完整录音按时间固定30s连续不重叠分块，全样本覆盖、不按GT切段/选好片段、不换权重；原整会6501前缀缓存和失败保留。完成全会文本与身份评分后判断候选，未通过不替换交付默认/不开最终盲集。'
d['jointArchitecture20261115']['nextExecutableGate']=d['next'];d['jointArchitecture20261115']['cpuWindowComposition20261116']=receipt
d['logResult']+='\n'+receipt['at']+' CPU25%组合首批实测完成：32自然多人不重叠输入全自然EOS；739.262125s音频用491.9721225s，原生C++明确CPU，私有峰765276160bytes、观测工作集约2.1GiB分别记录。冻结预测对预测身份映射、沿原全会参考身份一次映射严格评分；英文验证124/709=17.49%、带人133/709=18.76%，原141/709与244/709；中文63/1258=5.00795%、带人64/1258=5.08744%，原73/1258与75/1258。DER沿用未改全会Nemotron，英文20.146%、中文2.330%，无改进声明；8训练角色另列，不混验证。未达售卖、每个人/事实/全会与完整CPU说话人未过或未测。按同一模型组合向原4完整录音固定时间分块推进，非开启新候选网格。源码与关闭失败已私有远端保护r34 a026a9882a6c965888e3516494c8c05b6bbb7814。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ['state','audioSeconds','inferenceSeconds','privatePeakBytes','observedFamilyWorkingSetPeakBytes','observedCpuPercentPeak']},ensure_ascii=False))
