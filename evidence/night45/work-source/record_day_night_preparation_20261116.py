"""Record one completed daytime batch and its actual evening dependency."""
from datetime import datetime
from pathlib import Path
import hashlib
import json

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
J = R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C = J/'night-acoustic-pilot-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/night-acoustic-pilot-r1')
P = Path('work/bilingual_progress.json')
read = lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
now = datetime.now().astimezone().isoformat(timespec='seconds')
packet = read(C/'packet.json'); packet_sha = sha(C/'packet.json')
checks = {name:read(path) for name,path in {
    'offline':E/'offline-audit/offline-audit.json',
    'admission':C/'missing-preflight-admission-proof.json',
    'contracts':C/'offline-verification.json',
    'baseline':C/'baseline-score-replay.json',
}.items()}
assert checks['offline']['binding']['packetSha256'] == packet_sha
assert checks['admission']['packetSha256'] == checks['contracts']['packetSha256'] == packet_sha
assert checks['contracts']['testsPassed'] == 11
assert checks['baseline']['baselineReplayOnly'] and checks['baseline']['ordinaryChineseWhole']['candidate']['errors'] == 461
assert not (E/'gpu-preflight').exists() and not (E/'training').exists() and not (E/'evaluation').exists()
entry = '"'+packet['runtime']['python']+'" "'+packet['nightEntry']+'" --packet "'+str(C/'packet.json')+'" --execute-night'
notes = '\n'.join([
    'Companion：白天分析与离线准备／夜间单一GPU训练批次',
    '目标98%，底线95%；原逐人、DER、事实、防回退与最终盲测要求保留。',
    '当前：离线准备已验；真实GPU前反传、显存、吞吐与恢复仍未实测。没有启动训练或定时任务。',
    '',
    '白天已完成：已有错误归因；944条训练输入的音频头、token与标签检查；固定中英采样顺序；目标标签遮罩；仅独显准入；分块checkpoint/元数据校验/中断及并发保护；原分数复现。',
    '训练：22个公开源，944条，约2.81小时；声学编码器+桥接约3.1748亿参数，语言模型冻结；一个固定epoch、batch1、累积2。所有原词、短回应、重复、数字与EOS保留。',
    '对照：24条严格无重叠验证片段，以及同一普通中文整会79个原输入叶；保留原173采样点尾部补零，以及只跳过完全数字零的原策略，非零轻声不截除。',
    '',
    '夜间入口（当前不执行）：',entry,
    '入口依次完成：真实6800XT预检 → 从原权重新开一批训练 → 最终epoch原生BF16固定对照 → 独立原评分。任一阶段失败停止，保留状态，不自动换模型或重试失败前缀。',
    '如已有停下的批次，先核对应state.json/console；确认停止原因已解决后，技术续作可使用--resume-training或--resume-evaluation。不是重新训练或更换参数。',
    '',
    '资源：约25%CPU/最多4计算线程供预处理及调度，2GiB本作业族私有内存硬限；开始/恢复需空闲3.18GiB连续60秒，Windows低内存信号停止。前反传、训练参数与Adam动量全在经核实的6800XT，无CPU/780M训练兜底。',
    '理论GPU模型/梯度/优化器下界约8.52GB，尚未计激活和缓存；不能据此声称16GB显存实测可用。实际峰值与每步速度必须由夜间预检给出。',
    '恢复文件写E盘，按固定间隔保留完整状态；GPU实际预检与训练数据均未复制成用户安装包。',
    '本批只准备并检验训练/原文对照入口。新文字的时间对齐、整会人物归属、逐人/事实、未见会议与商用品质仍需后续验收；默认模型不变。',
])+'\n'
(C/'说明.txt').write_text(notes,encoding='utf-8')
state = {
    'at':now,'state':'DAYTIME_DIAGNOSIS_AND_OFFLINE_NIGHT_BATCH_READY_ACTUAL_GPU_PREFLIGHT_PENDING',
    'ownerQuotes':[
        '看一下咯，然后。除了哦。就是你现在没没法做别的事情了，对吧？因为没有显卡。你看，继续把没有显卡可以做的事情做一下。',
        '让你白天集中分析问题，然后晚上再集中训练，这样子会好一点吧？因为我们有显卡的时间是只有晚上才可以。',
    ],
    'ownerWorkMode':{'day':'Existing errors, data/label/segmentation and implementation checks; no neural training.','night':'When actual RX6800XT is connected: one fixed preflight, then one prepared training/evaluation batch.','cpuTraining':False,'integratedGpuTraining':False,'automaticScheduledStartCreated':False},
    'packet':str(C/'packet.json'),'packetSha256':packet_sha,
    'nightEntry':packet['nightEntry'],'description':str(C/'说明.txt'),
    'implemented':['Native acoustic+bridge full-coverage GPU worker; frozen language model,FP32 trainable masters/moments and BF16 autocast.','Explicit prompt/padding/EOS masks and token-weighted accumulation; balanced fixed944-example order.','Bounded checkpoint writer, immutable tensors/receipt, receipt SHA and atomic last-committed pointer; stop/corruption/concurrent-run rejection.','Actual present-PnP/HIP6800XT selection and original CPU/private-memory/low-RAM guards; no integrated/CPU training fallback.','Night controller with explicit execute mode, no timer/retries, separate phases and opt-in technical resume.','Audio-only final-epoch BF1624-clip+ordinary whole evaluation, original padding/exact-zero input contract, independent unchanged raw scoring.'],
    'verifiedOffline':{'examples':944,'languages':checks['offline']['languages'],
                       'targetTokens':checks['offline']['targetTokens'],'maxTargetTokens':checks['offline']['maxTargetTokens'],
                       'targetTruncated':False,'torchImportedByAudit':False,
                       'contractChecksPassed':11,'checkpointFormatReadByIndependentSafetensors':True,
                       'missingActualPreflightRefusedBeforeTorch':True,
                       'originalEnglishStrictErrors':141,'originalEnglishStrictWords':709,
                       'originalChineseStrictErrors':73,'originalChineseStrictCharacters':1258,
                       'originalChineseWholeErrors':461,'originalChineseWholeCharacters':8325,
                       'oldOrdinaryInputExactZeroLeaves':3,'oldTailInputPaddingSamples':173},
    'theoreticalResources':packet['resources'],
    'actualGpuPreflightPassed':False,'actualForwardBackwardOrOptimizerOnGpuTested':False,
    'actualGpuPeakOrTrainingDurationMeasured':False,'actualGpuCheckpointReloadTested':False,
    'trainingStarted':False,'newNeuralCalls':0,'newWeightUpdates':0,
    'modelQualityImprovedByThisBatch':False,'qualityQualified':False,'saleQualified':False,
    'rawEvaluationDoesNotReplacePersonFactsOrHoldoutAcceptance':True,
    'preparationFailuresRetained':['Builder first assumed audio-only manifest contains role; corrected freeze-time role lookup while excluding every validation label from model inputs.','Real admission test exposed the old resource constructor10% ceiling; reused existing owner25% JobObject override without changing the shared default or2GiB limit.','Review found one173-sample native tail padding and3 exact-zero leaves; restored the same input contract before any candidate inference.'],
    'next':'Actual RX6800XT presence plus original RAM stability gate; run the frozen night entry. Numerical GPU loss/accumulation/coverage, optimizer precision, checkpoint reload and true memory/time checks must pass before the fresh fixed epoch. Then use raw cross-meeting and ordinary-regression results to decide the next person/activity/facts acceptance work; do not count today’s code as an accuracy gain.',
}
(C/'day-preparation.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
d = read(P); j = d['jointArchitecture20261115']
j['dayNightPreparation20261116'] = state
j['state'] = state['state']
j['candidate']['state'] = 'IMPLEMENTED_AND_OFFLINE_VERIFIED_ACTUAL_GPU_PREFLIGHT_PENDING'
candidate = j['dayNightStageASteering20261116']['nextSingleTrainingCandidate']
candidate.update(status=j['candidate']['state'],trainingWorker=packet['trainingWorker'],
                 packet=str(C/'packet.json'),packetSha256=packet_sha,nightEntry=packet['nightEntry'],
                 trainingStarted=False,actualGpuPreflightPassed=False,
                 marketReviewQualification='Frozen-output diagnosis and offline implementation checks completed. Broader acoustic adaptation benefit, real GPU numerical behavior and resource feasibility remain unproven.')
d['state'] = state['state']
d['next'] = '白天分析与离线准备已完成本批：目标98%/底线95%不改；夜间唯一入口joint-architecture-r1/night-acoustic-pilot-r1/packet.json，当前SHA'+packet_sha+'。实际6800XT接入且原3.18GiB空闲稳定60秒后，执行meeting_acoustic_night_20261116.py --execute-night：先真实GPU前反传/累积梯度/显存/吞吐/分块恢复预检，过后才从原底座训练一个固定epoch，并跑24验证片段+原中文整会79叶及独立原评分。无CPU/核显训练、无定时任务、不自动重试换参。今天11项离线代码检查和944条输入检查、原分数复现通过，但没有新推理/参数更新/准确率提升，真实GPU数值与2GiB私有内存条件尚未实测；后续仍需新文字对齐/连续人物、每人/事实/未见会议验收，默认模型不变。'
j['nextExecutableGate'] = d['next']
d['d1d2Execution20261115']['currentPriority'] = d['next']
d['logResult'] += '\n'+now+' Owner要求继续无显卡可做工作，并明确白天集中分析、晚上集中训练。沿原A阶段和98%目标/95%底线落实一批可执行准备：新增本机原生声学+桥接训练worker、纯轻量契约、最终BF16音频对照、独立原评分、明确执行模式夜间入口及对应检查。保留原2GiB作业族私有内存、Windows低内存停止、3.18GiB稳定60秒；25%CPU沿既有已授权override，预处理最多4线程，无CPU/核显前反传或动量。训练范围317477504参数，语言模型冻结，FP32参数/梯度/Adam动量在GPU，BF16 autocast，避免把小LoRA接口直接当整编码器训练。单一22源944条约2.81h，一epoch/472更新；完整checkpoint分1MiB主机块写，状态收据SHA、原子pointer和互斥run，首更新/固定间隔/最终保留恢复。通过当前11项离线检查、944音频头/标签/token检查(26148目标token、最长103，未裁字)、实际训练入口缺真实GPU预检时导入torch前拒绝；只执行夜间入口inspect，未建定时任务/训练进程。固定24验证+原中文整会79叶，发现并保持原173采样尾补零和3完全数字零叶，只保留原精确零跳过，不删非零轻声；原评分复现中文73/1258、英文141/709、整会461/8325，原口径未变。准备中role字段假设和共享constructor10%上限两次失败已在收据保留并修源头，未改共享默认/标签/基线。理论模型梯度优化器下界8520790016字节、未计激活缓存；不能称16GiB已适用。GPU损失/梯度累积/覆盖/保存恢复/实际峰值速度均待夜间实测，预检权重不会当正式批次起点；当天0新推理/0更新/0质量改善，原默认模型、每人/DER/事实/盲测及售卖状态不改。证据：'+str(C/'day-preparation.json')
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':d['state'],'packetSha256':packet_sha,'trainingStarted':False,
                  'gpuPreflightPassed':False,'newNeuralCalls':0,'next':str(C/'说明.txt')},ensure_ascii=False))
