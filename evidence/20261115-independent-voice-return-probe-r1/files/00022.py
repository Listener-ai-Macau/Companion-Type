from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'independent-voice-return-probe-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/independent-voice-return-probe-r1/probe-r1')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
result=read(C/'decision.json');state=read(E/'state.json');run=read(E/'run.json')
assert result['state']=='REJECT_FIXED_INDEPENDENT_VOICE_RETURN_PROBE' and not result['allThreeCorrect']
assert state['explicitForwardCalls']==8 and state['parameterUpdates']==0
# Check the retained independent annotation format, without changing either
# its labels or the original acceptance reference.
rttm=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/official-annotations/20200623_S_R001S07C01.rttm')
intervals=[]
for line in rttm.read_text(encoding='utf-8').splitlines():
    p=line.split();intervals.append(dict(start=float(p[3]),end=float(p[3])+float(p[4]),speaker=p[7]))
matched=[]
for case in read(C/'scoring-only.json'):
    ref=case['referenceUtterance'];matches=[r for r in intervals if abs(r['start']-ref['start'])<.00011 and abs(r['end']-ref['end'])<.00011]
    assert len(matches)==1 and matches[0]['speaker']==case['referenceSpeaker']
    matched.append(dict(id=case['id'],textgridSpeaker=case['referenceSpeaker'],rttmSpeaker=matches[0]['speaker'],matchingLabel=True))
at=datetime.now().astimezone().isoformat(timespec='seconds')
check=dict(state='OFFICIAL_RTTM_AND_TEXTGRID_AGREE_ON_ALL_SEVEN_DIAGNOSTIC_LABELS',at=at,
           rttm=str(rttm),rttmSha256=hashlib.sha256(rttm.read_bytes()).hexdigest(),cases=matched,
           originalReferenceChanged=False,
           interpretation='Two annotation formats agree but are not independent human identity verification. Independent pretrained voice representation also groups the late003-M examples nearer early004-M than early003-M. This remains unresolved model/profile/domain/annotation uncertainty, not grounds to relabel gold or claim the full model corrected.')
(C/'annotation-source-cross-check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=(f"独立公开WeSpeaker声纹最小诊断已完整执行：7段34.9745s，原mic0无增益/分离，固定参考辅助切段和4早期人物/3返场只用于评分，神经端仅匿名PCM；本轮无训练。8次显式前向含实际权重CPU/GPU首样控制，特征最大差{state['maximumFeatureDifference']:.10g}/均差{state['meanFeatureDifference']:.10g}、完整embedding余弦{state['embeddingCpuGpuCosine']:.10g}通过，worker {state['seconds']:.3f}秒、外层含运行时核对{run['seconds']:.3f}秒、族私有峰{run['privatePeakBytes']}B，5%/2GiB/实际低RAM保持。按原官方标签3次均应003-M，最高却均004-M：相似度0.76315/0.70170/0.66495，对本标注003-M早期参考0.48602/0.40641/0.36716；0/3通过，按冻结规则停止该固定诊断、不继续原整会重标或更换参考/窗口/相似阈值。官方RTTM与TextGrid全部7段人物一致，不是两格式读取差；这不证明每段真实身份，保留模型/参考样本/域差及标签本身的不确定性，不擅自改gold。独立模型也未提供直接组合放行的证据，不能说整个领域不可做；原D1可用，D2与售卖仍未过，Owner无需听审/录音/账号。")
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    independentVoiceReturnProbeStatus=result['state'],independentVoiceReturnProbeDecision=str(C/'decision.json'),
    independentVoiceReturnProbeAnnotationCheck=str(C/'annotation-source-cross-check.json'),
    independentVoiceReturnProbeCorrect=0,independentVoiceReturnProbeTotal=3,
    independentVoiceReturnProbeUsedForProductQualification=False,
    publicTrainingBatchClosed=True,publicTrainingBatchDeliveredQualityImprovement=False)
v['state']='D1_AVAILABLE_D2_OPEN_PUBLIC_TRAINING_AND_VOICE_DIAGNOSES_REJECTED'
v['next']='本批公开人物/声学训练和独立返场声纹诊断均已完整执行并按冻结规则拒绝默认，先保护全部实际权重/恢复点/失败和原标注，再沿原复杂会议组合路线核对完整训练规模、监督可靠性与模型适配边界。停止本小样本两微调、原片声纹参考和阈值变体，不以更容易会议或改gold关闭原D2；D1原内测候选继续可用，文字/逐人/人物/售卖仍开放。后续只执行能改变当前判断的完整数据或架构方案，Owner无需听审、录音、标注或提供可选模型账号；原音和最终留出保持。'
v['logResult']+=' '+at+' '+summary
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (R/'model-research/README.md').open('a',encoding='utf-8') as f:f.write('\n\n'+at+' '+summary+'\n')
p=Path('outputs/Companion-公开会议训练实际结果-20261115.txt')
with p.open('a',encoding='utf-8') as f:f.write('\n\n'+at+' 独立声纹组合前诊断\n'+summary+'\n本批最终：没有可交付的识别质量提升；不代表D1流程被撤回，不能称D2已完成或可售。\n')
print(json.dumps({'state':v['state'],'voiceProbe':result['state'],'correct':0,'total':3,'d2Complete':False,'ownerParticipationRequired':False},ensure_ascii=False))
