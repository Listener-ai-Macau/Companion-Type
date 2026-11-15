from pathlib import Path
from datetime import datetime
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-acoustic-context-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/public-acoustic-context-r1/trial-r2')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
result=read(C/'decision.json');state=read(E/'trial-state.json');run=read(E/'run.json')
assert state['trainingSteps']==50 and state['optimizerUpdates']==25
assert result['frozenOriginalWeightsByteExact'] and result['adapterSavedReloadedTensors']==32
keep=result['keepForFullMeetingEvaluation'];now=datetime.now().astimezone().isoformat(timespec='seconds')
main=result['byCondition']['multi-turn-context'];short=result['byCondition']['clean-short-response']
failed=[k for k,v in result['checks'].items() if not v]
summary=(f"固定声学适配完整执行：50自然多轮段790.557s，3个官方train源，最后8层音频编码器q/v LoRA实际262144参数，语言模型与所有原参数冻结，1epoch/25更新、25恢复点保留；神经worker {state['startedAt']}至{state['finishedAt']}、{state['seconds']:.3f}秒、族私有峰{run['privatePeakBytes']}B，5%/2GiB/实际低RAM停止保持，最长完整训练段标签遮罩与梯度通过，无更新proof；原中文native前缀/零适配逐token全等，原参数字节前后全等，32适配张量保存/重新加载全等。原32条件验证逐一完成，12段多轮严格CER {main['baselineEdits']}→{main['candidateEdits']}/1476、{main['baselineCer']:.8%}→{main['candidateCer']:.8%}；20短响应{short['baselineEdits']}→{short['candidateEdits']}/87；允许重叠参考顺序诊断{main['baselineOracleOrderEdits']}→{main['candidateOracleOrderEdits']}/1476，仅诊断不换原分；英文规范化保留={result['checks']['englishNormalizedPreserved']}，自然中英混合编辑={result['mixedEdits']}。最终权重SHA {state['adapterSha256']}，决定{result['state']}，未过项{failed}。无Owner听审、私人上传、麦克风、外放或日用版替换；原D2全部质量门仍开放。")
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(publicAcousticContextStatus=result['state'],publicAcousticContextResult=str(C/'decision.json'),
         publicAcousticContextRun=str(E),publicAcousticActualTrainableParameters=state['trainableParameters'],
         publicAcousticAdapterFile=str(E/'final-adapter/adapter_model.safetensors'),
         publicAcousticAdapterSha256=state['adapterSha256'],publicAcousticAdapterAdoptedInProduct=False,
         publicAcousticKeepForFullMeetingEvaluation=keep)
v['newPublicAcousticAdapterWeightsCreated']=True;v['modelWeightsChanged']=True
if keep:
    v['next']='固定声学适配已过原32条件诊断与英文/自然混合控制，继续原完整中文/英文开发门后才考虑集成；此前人物适配失败仍拒绝默认。保护50段唯一训练/25恢复点/32完整候选与失败，原门不改，最终留出不打开，Owner无需听审。'
else:
    v['next']='固定公开人物和声学适配都已执行并依冻结规则拒绝默认；完整保护权重、8/25恢复点、原困难整会及32条件结果，不追加LR/rank/epoch/阈值或新片变体、不重跑已失败层。原D1候选继续可用，D2原文字/人物/逐人门未过。继续原公开复杂会议路线的训练数据规模/有效监督与组合架构取舍，只有能区分剩余根因或达到实际质量的新方案才执行；无需Owner听审，不以可选门禁模型作全项目依赖，最终留出不打开。'
v['logResult']+=' '+now+' '+summary
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (R/'model-research/README.md').open('a',encoding='utf-8') as f:f.write('\n\n'+now+' '+summary+'\n')
p=Path('outputs/Companion-公开会议训练实际结果-20261115.txt')
with p.open('a',encoding='utf-8') as f:
    f.write('\n\n'+now+' 追加实际声学训练结果\n'+summary+'\n下一步：'+v['next']+'\n')
print(json.dumps({'state':result['state'],'context':main,'short':short,'failedChecks':failed,'adoptedInProduct':False},ensure_ascii=False))
