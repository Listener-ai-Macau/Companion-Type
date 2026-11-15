from pathlib import Path
from datetime import datetime
import json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-speaker-adaptation-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/public-speaker-adaptation-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
old=D/'model-quality-dependency-audit.json';archive=D/'model-quality-dependency-audit-before-owner-public-training.json'
if not archive.exists():shutil.copyfile(old,archive)
old.write_text(json.dumps({'state':'OWNER_RESUMED_AUTONOMOUS_PUBLIC_TRAINING_OLD_WHOLE_BLOCKER_WITHDRAWN',
 'at':datetime.now().astimezone().isoformat(),'previousAuditArchive':str(archive),
 'consecutiveWholeGoalDependencyAudits':0,'goalMarkedBlockedThisAudit':False,
 'ownerAudioAdjudicationRequired':False,'community1AccessOnlyOptional':True,
 'independentTrainingRunning':True,'note':'Owner explicitly instructed engineer to select public meetings/official labels and train without owner listening. Old platform blocked receipt remains historical; no new artificial human dependency.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
packet_path=D/'asr-audio-adjudication-r1/packet.json';packet=read(packet_path)
packet.update(ownerParticipationNoLongerRequired=True,ownerRequirementWithdrawn=True,
 status='HISTORICAL_DIAGNOSTIC_MATERIAL_ENGINEER_USES_OFFICIAL_LABELS_NO_OWNER_ACTION')
packet_path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(publicSpeakerAdaptation=str(C),publicSpeakerAdapterMethod=str(C/'protocol.json'),
 publicSpeakerControl=str(E/'control-r3/state.json'),publicSpeakerBaseline=str(C/'baseline-decision.json'),
 publicSpeakerTraining=str(E/'train-r2'),publicSpeakerTrainingStatus=read(E/'train-r2/state.json')['state'],
 ownerAudioAdjudicationRequired=False,wholeModelQualityDependencyAuditCount=0)
v['next']='完成已启动的原Nemotron复杂会议人物/重叠固定适配：2个7人训练会议65分钟，2个6/5人独立验证会议72分钟；4epoch/8次整会更新、原PIL/ATS/activity/phantom目标，最终适配一次完整验证。先解决执行源头，不改epoch/lr/rank或门限；若验证无一致收益则保留失败不采用。所有公开标签由工程自主使用，Owner无听审任务；Community1只可选不阻塞。原D1/D2整体范围保持，D2原字门仍未过。'
v['logResult']+=' '+datetime.now().astimezone().isoformat(timespec='seconds')+' 公开复杂会议训练已实际推进：4原FLAC和官方标签SHA核，训练3926.4043秒/7+7人、验证4340.6998秒/6+5人，重叠各358.33/225.06秒，单麦0所有采样保留；原dev/最终留出不参与。CPU预处理初版因已知ROCm默认16线程分配失败留证，复用验证过的DLL进程内设1后完成，峰1990344704B、0NN；上游11个纯监督函数/损失forward AST原样保留，恢复原训练专用活动头，原99M骨干仅后8层q/v的131072个LoRA参数训练。control-r1整段/分块差被严格守卫拦下，改与原模型相同整段冻结投影后r2全部逐字节一致：原forward/缓存detach/零适配输出全等，独立整会梯度与分块梯度差7.45e-9/1.49e-8，真实LoRA梯度有限非零，冻结参数全等；16真实core控制调用原计数12漏4已另留说明和修计数、未重跑无关控制。完整72分钟原验证baseline15:19:43—15:20:08完成，两个严格零collar含重叠DER4.33445%/7.92762%，合计6.16115%，无真实人数提示；非原D2通过。固定训练r1完成5次整会更新后，在第6会回放第5chunk出现与校准不一致而停止，旧代码/历史/状态保留，没放松2e-5，原计划只存最终适配导致5次更新无可恢复权重也如实记录。源头改成保存校准中的离散cache输入路径并逐值回放，验证/产品推理仍原cache算法；同时每更新存恢复用adapter/optimizer/RNG，不以验证选epoch，最终仍固定第8更新。r3对新路径真实反向控制15:28:37—15:28:56通过、原输出及零适配仍精确、梯度正常、峰约1.35GB；同一4epoch/8更新/lr1e-4/rank8的train-r2已启动，非换参扫选。当前Owner已明确撤销人工听审前置，旧整体阻塞归档并重置0，不再把4原音/Community1作为整体阻塞；平台旧Goal blocked收据仅保留历史，实际本次授权工作持续执行。'
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':v['state'],'trainingStatus':e['publicSpeakerTrainingStatus'],'ownerActionRequired':False},ensure_ascii=False))
