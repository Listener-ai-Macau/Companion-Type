from pathlib import Path
from datetime import datetime
import json
import os

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
p=Path('work/bilingual_progress.json');v=json.loads(p.read_text(encoding='utf-8'))
j=v['jointArchitecture20261115'];q=j['overnightExecution20261116'];now=datetime.now().astimezone().isoformat(timespec='seconds')
for meeting in ['ES2003b','S_R004S03C01']:
    f=J/'native-context180-r1'/('score-'+meeting+'.json');s=json.loads(f.read_text(encoding='utf-8'))
    q.setdefault('completedSourceScores',{})[meeting]={'file':str(f),**{k:s[k] for k in ['rawText','baselineRawText','relativeRawErrorReduction'] if k in s},'stageASubsetScoreUpdated':False,'productQualified':False}
f=J/'english-transducer-r1/score.json';s=json.loads(f.read_text(encoding='utf-8'))
q['conditionalEnglishTransducer'].update(state='COMPLETE_PRETRAINED_FIXED_CLIPS_DIRECT_ADMISSION_REJECTED_NO_GRID',score=str(f),trainingUpdates=0,measuredErrors=123,referenceWords=709,WER=123/709,
    reason='Only1edit lower than priorMOSS124, worse ES2003b52vs51; old20percentrelative gate99edits not met. No automatic whole-source promotion.')
q['ownerLanguageSpecificSteering'].update(latestQuestions=['这种字错率你去降低它的原理是什么','是的, 估计不同的语言要用不同的公开模型, 从效果好的开始训练','然后做轻量化之类的'],
    acceptedOrder='Compare language-specific public pretrained bases, adapt the selected best using public meeting data when training fit/labels are verified, then independently evaluate lightweight/CPU deployment regression. Shared diarization/alignment and bilingual code-switch fallback remain.')
incident=json.loads((E/'system-restart-20261116-213635/incident.json').read_text(encoding='utf-8'))
summary={
    'at':now,'state':'OWN_GPU_WORKLOAD_LEADING_SUSPECT_COMPATIBILITY_ISOLATION_BEFORE_BOUNDED_REENTRY',
    'ownerQuotes':['你刚刚看我电脑死机重启了, 是不是因为你训练模型过载导致的原因','突然黑屏／直接重启','是你的显存问题吧, 是因为我现在用显卡坞, 已经最近每晚都这样, 以前不会, 所以高度怀疑你这边的问题, 白天上班的时候都不会','就是你在跑显卡训练的时候看看有啥导致它出现bug啥的, 以前我跑3dmaerk啥的都不会这样, 感觉是一些奇怪的兼容性问题, 然后你看看还是要把显卡用起来的'],
    'rawLocalEvidence':str(E/'system-restart-20261116-213635/incident.json'),
    'shutdown':'2026-11-16T21:36:35+08:00','boot':incident['currentBoot'],
    'lastWorker':'FRCRN pretrained enhancement, RX6800XT index1/gfx1030, first27.2500625second public clip',
    'lastWorkerSample':'2026-11-16T21:36:15+08:00','completedRealEnhancementClips':0,
    'trainingUpdates':0,'smallZeroForwardCompleted':True,'lastObservedPrivateGiB':incident['lastObservedWorkerPrivateGiB'],
    'lastObservedPrivateMemoryNotCrashVramSample':True,'historicVramPowerTemperaturePcieUnavailable':True,
    'windowsEvidence':'KernelPower41/BugcheckCode0 +EventLog6008, no matched current dump; no2004/4101/WHEA in inspected preboot interval. Old1ccWER is actuallyNov12, not this crash.',
    'history':'Windows also retains Nov15 evening and Nov16 00:14 unexpected restarts;00:14 recorded0x101. These are separate symptoms, not proof of the same cause.',
    'causeConclusion':'Owner repeated-night reports +20second correlation make ownedGPUworkload the leading trigger. VRAM exhaustion vsMIOpen/driver/dock/power/thermal not yet distinguished;3DMark stability is useful but does not validate the ML operator path.',
    'decision':'LatestOwner asks GPU remain in use. Retain interruptedFRCRN without retrying27second/defaultMIOpen path. Inspect runtime/ops and perform one bounded, instrumented GPU compatibility check under existing CPU/RAM protection before model work resumes. No driver/TDR/BIOS/clock/power change, no CPUtraining, no whole-batch stress reproduction.',
    'productQualified':False,'saleQualified':False,
}
d=J/'gpu-compatibility-r1';d.mkdir(exist_ok=True);(d/'restart-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
q.update(state=summary['state'],currentWorkerState='INTERRUPTED_BY_VERIFIED_SYSTEM_REBOOT_NOT_LIVE',pid=None,currentOwnedNeuralWorker=None,gpuRestartInvestigation20261116=summary)
q['nextIndependentGpuTask'].update(state='FRCRN_R2_INTERRUPTED_WITH_SYSTEM_RESTART_NO_REAL_CLIP_OUTPUT_NO_QUALITY_SCORE',run=str(E/'frcrn-front-end-r1/run-r2'),currentWorkerLive=False,trainingUpdates=0)
j['state']=summary['state'];v['state']=summary['state']
v['next']='先定位AMD计算兼容性：不重跑导致重启的FRCRN27秒默认路径；有边界GPU算子验证并记录实际显存/算子时间后再恢复模型。原中英文适配→轻量化目标与07:30阶段交付保持；无需GPU的源头分析和代码续作。'
entry=f'\n\n{now}｜Owner反馈黑屏直接重启、显卡坞近几晚发生但3DMark以前稳定，明确仍需用显卡。Windows证实21:36:35异常关机，FRCRN推理最后21:36:15，0训练更新，2秒静音控制完成、首条27.25秒真实增强未输出；最后私有内存1.076GiB不是崩溃显存样本，原保护未涵盖GPU功耗/驱动。Kernel41码0，当前无匹配转储/显存遥测，不能认定VRAM耗尽或排除本任务触发。旧1cc报告实为11月12日；历史昨晚另有0x101不混为本次。已核实际本任务GPU进程0、旧句柄85880不存在，未自动重启。原音/中断状态和系统证据保留E盘，摘要{d}/restart-summary.json。当前将本任务GPU负载列首要嫌疑，按最新指示做有边界兼容性隔离再恢复显卡，不用整批重跑碰运气、不修改驱动/TDR/功耗。同期已完成原整源中文MOSS428/8325=5.1411%CER，英文1051/5781=18.1802%WER，均未合格；英文TDT123/709旧固定99门未过，拒绝直接晋级。Owner按语言选好公开基座→适配→轻量化次序已承接，未因准备/推理计训练成果。'
v['logResult']+=entry
temp=p.with_suffix('.restart.tmp');temp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,p)
print(json.dumps({'state':v['state'],'next':v['next'],'summary':str(d/'restart-summary.json')},ensure_ascii=False))
