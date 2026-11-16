"""Record actual diagnostic results and select the next evidence-led step."""
from pathlib import Path
from datetime import datetime
import json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1'; C=J/'microphone-diagnostic-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/microphone-diagnostic-r1/gpu-run')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
score=read(C/'diagnostic-score.json'); run=read(E/'completed.json')
assert len(run['completed'])==13 and run['nativeControlExact'] and run['newNeuralCalls']==13
assert run['trainingUpdates']==0 and not score['qualityQualified']
now=datetime.now().astimezone().isoformat(timespec='seconds')
if score['diagnosticAcousticConditionContributionMaterial']:
    route='RECORDING_CONDITION_AND_FAR_FIELD_ROBUSTNESS_FIRST'
    priority='先定位远场及实际录音卡输入链路、声学鲁棒性：这次同模型在两来源近讲条件一致显著改善，说明录音条件有实质贡献；尚不能归因到某一硬件故障、单一噪声或增益。'
elif score['bothSourcesImproveInEasierRecording']:
    route='ASR_FIDELITY_AND_RECORDING_CONDITION_JOINT_GAP_NO_TRAINING_ADMISSION'
    priority='近讲在两个来源都改善但未达预设显著诊断幅度，继续分开检查口语原文识别能力与录音条件；优先一个有证据的成熟现成组件对照，暂不准入声学训练。'
else:
    route='ASR_TASK_AND_INFERENCE_FIDELITY_FIRST_SOURCE_DEPENDENCE_REMAINS'
    priority='近讲并未在两个来源一致改善，不能把漏词普遍归因远场；优先核对成熟ASR对会议口语原文的能力和推理条件，同时保留来源/话筒混音差异不确定性，再决定一个组件对照。'
next_step=priority+' 仍先做多人轮流不重叠的中英文。文字和说话人活动/连续身份分别验收；原生MOSS长上下文路径只可作为已准备候选的有限对照，不重跑失败的固定30秒/Whisper-turbo/Q8网格。r45训练仅保留为有条件备选，95%底线/98%目标及逐人/事实/最终盲测要求保持。'
decision={'state':'PRETRAINED_MICROPHONE_DIAGNOSTIC_COMPLETE_DIRECTION_SELECTED',
    'at':now,'route':route,'decision':priority,'next':next_step,
    'actualGpuRun':str(E),'score':str(C/'diagnostic-score.json'),
    'actualNewGpuDecodes':13,'trainingUpdates':0,'nativeControlExact':True,
    'actualDevice':run['device'],'peakPrivateCommitBytes':run['limits']['jobPeakPrivateCommitBytes'],
    'words':score['referenceWords'],'distantErrors':score['distantErrors'],
    'headsetMixErrors':score['headsetMixErrors'],'distantWer':score['distantWer'],
    'headsetMixWer':score['headsetMixWer'],'sources':score['sources'],
    'headsetInputIsDiagnosticNotProduct':True,'unchangedOriginalSingleMicrophoneBaseline':True,
    'interpretationLimit':'Two exposed meetings,12 fixed short clips. The mix combines different microphones and may have different speaker coverage, background, gains, reverberation and acoustic arrival times. It is not clean ground truth or a pure SNR intervention. No universal causal attribution or statistical generalization.',
    'broadTrainingAutomaticAdmission':False,'targetAccuracy':.98,'minimumAccuracy':.95,
    'qualityQualified':False,'saleQualified':False}
target=C/'direction-decision.json'; assert not target.exists()
target.write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json'); d=read(p); j=d['jointArchitecture20261115']; q=j['directionFirst20261116']
q.update(decision,actualRunState=run['state'],actualCompletedInputs=13,actualNewNeuralCalls=13,
    actualTrainingUpdates=0,actualDevice=run['device'],modelWeightsChangedThisDiagnostic=False)
d['state']=j['state']=decision['state']; d['next']=j['nextExecutableGate']=next_step
j['decision']=priority+' Mature pretrained specialist composition remains the mainline; training is conditional.'
d['d1d2Execution20261115']['currentPriority']=next_step
d['logResult']+='\n'+now+' 实卡诊断实际完成：HIP选择RX6800XT/gfx1030，1条原远场控制生成token完全一致，12条官方头戴混音全部自然EOS；合计13次GPU推理，参数更新0，原2GiB私有内存/25%CPU/低内存保护保持，峰值私有提交'+str(run['limits']['jobPeakPrivateCommitBytes'])+'字节。独立原评分709词：远场'+str(score['distantErrors'])+'错(WER'+format(score['distantWer']*100,'.4f')+'%)，头戴混音'+str(score['headsetMixErrors'])+'错(WER'+format(score['headsetMixWer']*100,'.4f')+'%)。逐来源结果='+json.dumps(score['sources'],ensure_ascii=False)+'。判因路线='+route+'：'+priority+' 近讲混音有不同收音/增益/混响/说话人覆盖，只作两已暴露会议诊断，不是纯SNR干预，不改产品单麦成绩、不称合格或可售、不启动r45训练。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['Companion：方向优先，已完成固定预训练模型实卡诊断',now,
    '当前主线：成熟预训练专用组件组合 + 输入/推理/产品链路修复。自己训练是有依据后的备选，接入GPU不自动开训。',
    '实际完成：RX6800XT/gfx1030，1条原远场控制token完全一致 +12条官方头戴混音推理，13次新解码，参数更新0。',
    '同709词：原单麦远场 '+str(score['distantErrors'])+'错，WER '+format(score['distantWer']*100,'.4f')+'%；官方头戴混音 '+str(score['headsetMixErrors'])+'错，WER '+format(score['headsetMixWer']*100,'.4f')+'%。']
for source in score['sources']:
    n=source['referenceWords']; lines.append(source['meeting']+'：'+str(n)+'词；远场 '+str(source['distantErrors'])+'错('+format(source['distantErrors']/n*100,'.4f')+'%)；头戴混音 '+str(source['headsetMixErrors'])+'错('+format(source['headsetMixErrors']/n*100,'.4f')+'%)。')
lines += ['判断：'+priority,decision['interpretationLimit'],
    '时轴来源：原始帧区间、原PCM，未加增益/降噪/重采样/移动时轴；最初包络相关预检失败有存档，独立波形相关峰均在原100ms范围内并核对官方共享采样时钟。',
    '产品目标：98%，底线95%；中文CER和英文WER分开，单麦、逐人、事实、盲测条件保持。近讲成绩不替代产品分数。',
    '下一步：'+next_step,'原r45训练方案保留为有条件备选。当前产品仍未通过质量/可售验收。']
(C/'说明.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'state':decision['state'],'route':route,'distantWer':score['distantWer'],'headsetMixWer':score['headsetMixWer'],'qualityQualified':False},ensure_ascii=False))
