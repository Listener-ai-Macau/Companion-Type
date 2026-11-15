from pathlib import Path
from datetime import datetime
import json

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
D = R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
T = D/'public-speaker-adaptation-r1'
DEV = D/'public-speaker-development-r1'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
baseline = read(DEV/'baseline-decision.json')
candidate = read(DEV/'candidate-decision.json')
assert candidate['originalReferenceAndScorerUnchanged']
assert len(candidate['reports']) == 1 and not candidate['bothSpeakerDerAtMost10Percent']
assert not candidate['validationKeepRulePassed']
at = datetime.now().astimezone().isoformat(timespec='seconds')
decision = dict(
    state='REJECT_FIXED_PUBLIC_SPEAKER_ADAPTER_AT_ORIGINAL_DEVELOPMENT_GATE',
    at=at, baselineDer=baseline['aggregateDer'], candidateDer=candidate['aggregateDer'],
    requiredDerAtMost=.10, originalDevelopmentGatePassed=False,
    heldAdaptationValidationKeepRulePassed=True,
    heldAdaptationValidationIsNotProductQualification=True,
    adapterFile=read(T/'protocol.json')['adapterFile'],
    adapterSha256='c19f8701b1fc514eaf49ea4dce575a38a0676a8a0471221a97d0145109701de3',
    automaticProductAdoption=False, originalProductDefaultsUnchanged=True,
    newTrainingUpdates=0, additionalHyperparameterOrThresholdVariantsPlanned=False,
    remainingOldChineseAndEnglishAdapterInferenceSkippedBecauseHardGateAlreadyFailed=True,
    d1Complete=True, d2Complete=False, qualityQualified=False, saleQualified=False,
    ownerAudioAdjudicationRequired=False,
    explanation='Two held adaptation sources improved by only 2.2072 speaker-seconds; original difficult development meeting regressed and fails unchanged 10% gate. Retain weights/recovery/failures; reject this fixed adaptation for the product default.')
(DEV/'final-decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(publicSpeakerOriginalDevelopment=str(DEV/'final-decision.json'),
         publicSpeakerOriginalDevelopmentGatePassed=False,
         publicSpeakerAdapterDecision=decision['state'],
         publicSpeakerAdapterAdoptedInProduct=False, publicSpeakerDefaultChanged=False)
v['next']='固定公开人物适配已在原34分钟难例失败并拒绝默认，保护本轮真实权重/8恢复点/全部失败，停止同参数、阈值和其余昂贵整会复跑。继续原复杂会议文字缺口：先依公开原标注与成熟SOT文献核对重叠训练目标及旧训练覆盖，只有与旧孤立短句LM试验有实质不同、可自动核验的固定方案才执行。原D1可用，D2原文字/逐人/人物门未过；无需Owner听审、录音或Community1许可才能做独立工作，最终留出不打开。'
v['logResult'] += ' '+at+' 原困难34分钟会议已完成一次相同最终适配推理（21.891秒，族峰1175171072B，5%/2GiB保持，禁用适配原前缀logits全等），特征raw字节与已保护原官方FP32整会特征完全一致，复用旧baseline未重跑。相同连续时间/零collar/含重叠评分DER15.8414424%→15.9245204%，原<=10%门未过且退步0.08308百分点。按冻结规则拒绝该固定适配进入默认，不挑两场小改善替代原困难会，不继续旧中文/英文适配整会推理或LR/epoch/rank/阈值变体；8恢复点及原失败保留。本轮没有可交付质量改善，原D1与应用默认保持。接续重叠文字训练目标/覆盖核对，Owner无需人工听审。'
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=R/'model-research/README.md'
with p.open('a',encoding='utf-8') as f:
    f.write('\n\n'+at+' 固定公开人物适配原困难34分钟开发门最终失败：同字节特征、同评分、同阈值，DER15.8414424%→15.9245204%，未到原10%门。两留出适配源合计仅少2.2072秒，不足以证明原困难会改善；按冻结规则拒绝默认，不追加同参数/阈值变体、不继续不可能放行的其余整会推理。最终528024B适配和8恢复点、所有准备/执行失败保留，原D1可用，D2仍未合格，无Owner听审前置。\n')
out=Path('outputs/Companion-公开会议训练实际结果-20261115.txt')
out.write_text('Companion 公开复杂会议训练实际结果\n更新时间：'+at+'\n\n你不用听审或准备录音；公开原音与官方文字/人物标注由工程自行核对。\n\n本轮实际完成：两场7人中文公开会议约65分钟训练，另两场6/5人会议约72分钟完整验证；在原99M人物模型上只训练131072个适配参数，4轮8次完整会议更新，原参数不变。训练约123秒，训练族私有内存峰约1.57GB，仍保留5% CPU/2GiB与低内存停止。\n\n结果（DER人物错误率，越低越好，零容差且包含同时说话）：\n两场适配留出会议：4.334%→4.307%；7.928%→7.854%，小幅改善。\n原来34分钟困难会议：15.841%→15.925%，没有改善，仍未到10%门。\n决定：这份固定适配已拒绝进入产品默认，权重、8恢复点和所有失败保留。不靠改阈值或换容易样本宣称通过。\n\n当前交付：D1本地增量/离线到保存、重开、导出的候选入口已核验；D2文字/逐人和复杂人物质量没有达标，仍不能称可售。此次训练不改变文字识别质量，也没有替换日用版。\n\n下一步沿原待办核对公开会议重叠文字训练目标与旧数据覆盖，再决定一次有证据的不同方案；不再把人工听审或某一个有门禁的模型当全项目依赖。\n',encoding='utf-8')
print(json.dumps(decision,ensure_ascii=False))
