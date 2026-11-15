from pathlib import Path
from datetime import datetime
import argparse,json
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['source','natural'],required=True);p.add_argument('--aligned',action='store_true');p.add_argument('--continuous',action='store_true');a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
T=D/'supervised-blind-separation-r1'
C=T/('continuous-overlap-composition-r1' if a.continuous else 'natural-window-unit-alignment-r1' if a.aligned else 'natural-composition-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
training=read(Path(read(T/'protocol.json')['trainRun'])/'state.json')
assert training['state']=='COMPLETE_ONE_FIXED_BLIND_SEPARATOR_TRAINING_PASS'
source=read(T/'source-decision.json');stamp=datetime.now().astimezone().isoformat(timespec='seconds')
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(supervisedBlindSeparationStatus=source['state'],supervisedBlindSeparationSourceDecision=str(T/'source-decision.json'),
    supervisedBlindSeparationSourceMetrics=dict(baseline=source['baseline'],candidate=source['candidate']),
    supervisedBlindSeparationTrainingExamples=training['trainingExamples'],
    supervisedBlindSeparationOptimizerUpdates=training['optimizerUpdates'],
    supervisedBlindSeparationFinalCheckpoint=training['finalCheckpoint'])
before=source['baseline']['all']['meanErrorRatio'];after=source['candidate']['all']['meanErrorRatio']
summary=f'{stamp} 唯一固定盲分离完整核训练真实完成319窗/80次更新，最终10分片重新载入全部1099张量全等；ASR/人物权重未训练。84个独立1D验证音频全部预测后独立波形评分，平均误差能量比{before:.8f}→{after:.8f}，结论{source["state"]}。原公开自然词/整会中英文人物门及最终留出不变。'
passed=source['state']=='PASS_SOURCE_GATE_NATURAL_WORD_EVALUATION_REQUIRED'
if passed:
    v['next']='仅以固定最终update80分离权重执行原32自然会议完整双路+原Qwen全64路词评；原未训练Nemotron路由与原ASR基线原样复用，两路所有词/串音保留，两个会议及短回应不退步才整会人物/中英文验收。源验证通过不代表自然或售卖达标，不调阈值/窗口/轮数。'
else:
    v['next']='固定唯一分离训练未过独立源门：保留最终权重和失败样本，不再追加学习率/轮数/模型变体；先用已生成波形CPU定位源失真与空路泄漏，明确真实训练数据差距，保留原可用产品及未完成的复杂会议词/人物/中英文交付，不把合成源成绩替代产品门。'
if a.phase=='natural':
    natural=read(C/'routed-decision.json')
    e.update(supervisedBlindSeparationNaturalDecision=str(C/'routed-decision.json'),
        supervisedBlindSeparationNaturalStatus=natural['state'],
        supervisedBlindSeparationNaturalMetrics=natural['byCondition'])
    if a.continuous:
        e.update(continuousOverlapComposition=str(C),continuousOverlapCompositionDecision=str(C/'routed-decision.json'),
            continuousOverlapCompositionStatus=natural['state'],continuousAudioRoutingImplemented=True,
            separatedStreamSpeakerAssociationImplemented=False)
    if natural['keepForOriginalWholeMeetingTesting']:
        v['next']='固定最终分离训练与自然32词门通过，仅进入原完整会议/稳定人物/中英文严格验收；保持同一分离权重、原Nemotron预测和原Qwen，不打开最终留出、不调参数、不提前改默认。'
    else:
        v['next']='最终固定分离训练的自然会议词门仍失败，保留两路全部词/原分数/最终权重；执行已有结果的CPU错误归因，核清源失真和跨块串音，不再小样本调轮数/阈值或换模型试错。原D1交付保留，D2逐字/人物/自然混说、真实设备增量等未完成项继续保留，未达售卖标准。'
    summary+=(' 连续时间路由已实现：原0.5Nemo每样本预测>=2才用同一最终80分离声音，其他处逐样本保留原麦克风；原粗片段273.7275s含253.6031s非预测重叠/92.648%，此次按时间路由，不调整阈值或新训练。32个原输入完整覆盖、原音保护通过；18无重叠病例复用原ASR+真实全零副路，仅28新ASR，无新分离前向，人物与分离流关联未完成。' if a.continuous else ' 修复训练/验证窗内共同尺度在自然推理被错误移至整段拼接后的运算顺序；同一2s声音输出数值控制通过，未改最终80权重、窗口/路由/阈值。' if a.aligned else '')+' 自然32固定病例全部双路64转写完成，沿相同原Nemotron预测路由，'+json.dumps(natural['byCondition'],ensure_ascii=False)+'；'+natural['state']+'，所有使用路文字完整计分，未替换参考/原门。'
v['logResult']+=' '+summary
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['Companion 分离训练与组合模型实际进度',stamp,'',
    '当前主线：单麦原音 → 原人物/重叠检测 → 重叠段双路分离 → 原本地中英文识别 → 时间轴与人物关联。',
    '已完成：同一公开55.7M盲分离核，89组已知一/双源单位、319个2秒窗口、固定一轮80次真实更新；最终全权重分片保存并重新加载核验。识别模型与人物模型未训练。',
    '独立源验证：另一批公开会议24组声音成分、84个窗口，实际单源39/双源45；输入文件与目标波形分开，推理不读取目标。',
    f'平均误差能量比：{before:.6f} → {after:.6f}（越低越好）；结论：{source["state"]}。']
for key in ['active:1','active:2']:
    lines.append(key+': '+f'{source["baseline"][key]["meanErrorRatio"]:.6f} → {source["candidate"][key]["meanErrorRatio"]:.6f}')
if a.phase=='natural':
    for key,value in natural['byCondition'].items():
        lines.append(key+': '+f'{value["baselineDiagnosticEdits"]} → {value["candidateDiagnosticEdits"]} 错误 / {value["referenceCharacters"]} 字；'+natural['state'])
lines+=['','先前原分离器未训练的组合已拒绝：自然多轮161→419错误，原检测路由后仍161→360；单人短回应13→51，路由后13→19。失败证据保留。',
    '本次波形验证含人工叠加混音，保留真实远场房间背景，不是自然重叠的独立原声金标。自然会议、稳定人物、中英文整体和真实设备验收仍按原规则。',
    '准确率和售卖标准尚未达标；最终留出未打开，产品默认未改，Owner无需听审、标注、提供账号或录音。','',
    '下一步：'+v['next'], '声音验证：'+str(T/'source-decision.json'),'自然会议验证：'+str(C/'routed-decision.json')]
Path('outputs/Companion-分离组合模型进度-20261115.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(dict(state=source['state'],next=v['next'],trainingUpdates=80),ensure_ascii=False))
