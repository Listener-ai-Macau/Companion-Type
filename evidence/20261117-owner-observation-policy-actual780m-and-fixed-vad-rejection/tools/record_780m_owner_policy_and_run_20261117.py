"""Record the owner override and actual current 780M component execution."""
from pathlib import Path
from datetime import datetime
import json,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/igpu-native8-r3')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
case=read(J/'igpu-native8-r3/audio-only.json')[1];run=read(E/(case['meeting']+'-run.json'))
live=False
try:
    worker=psutil.Process(run['pid']);live=abs(worker.create_time()-run['createdAt'])<.01
except psutil.NoSuchProcess:pass
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
at=datetime.now().astimezone().isoformat(timespec='seconds')
o['ownerCpuTemperaturePolicy20261117']={'at':at,'mode':'observe-only','maximumStartCelsius':None,'stopCelsius':None,
    'ownerQuote':'这个为什么会有这个软件门栏呢？没有必要有这个东西啊。',
    'scope':'Current Companion model task CPU temperature telemetry; no task start/stop temperature gates. System hardware/OS controls unchanged.',
    'originalMemoryCpuTimeLimitsRetained':True,'cpuOrIntegratedGpuTrainingAuthorized':False}
o['ownerGpuCompatibilityHypothesis20261117']={'ownerReport':'Games and3DMark heavy loads previously stable; repeated reboots associated with model work with USB4 external GPU dock.',
    'priority':'Investigate actual compute backend/driver/eGPU path; graphical stress stability does not qualify the model compute path.',
    'causeProven':False,'cpuTemperatureCauseProven':False,'gpuDriverCauseProven':False,
    'systemDriverTdrPowerOrFanSettingsChanged':False,
    'primaryReference':'https://learn.microsoft.com/en-us/windows-hardware/drivers/display/timeout-detection-and-recovery'}
o['currentOwnedNeuralWorker']={'pid':run['pid'],'createdAt':run['createdAt'],'run':str(E),
    'meeting':case['meeting'],'training':False} if live else None
o['currentWorkerState']='EXPLICIT_780M_NATIVE8_FULL_MEETING_INFERENCE' if live else run['state']
o['state']=x['state']='ACTUAL_780M_CONTROL_PASSED_FULL_MEETING_INFERENCE_RUNNING' if live else run['state']
x['at']=at
x['logResult']+='\n\n'+at+'｜Owner明确质疑CPU85/95软件门槛，指出游戏/3DMark重载稳定且怀疑显卡计算/显卡坞兼容性。本任务已按最新指示改CPU温度为仅观测；这不是证明CPU绝不可能热重启，也不是认定GPU驱动根因，系统温控不改。旧协议保持历史，当前新协议CPU cutoff为None，诊断丢失也不当计算准入；2GiB私有/CPU5%/实际低RAM/60秒RAM稳定/有界时限及不CPU核显训练保留。r3动态准备器沿r2旧描述称阈值不改不准确，以本更正和实际observe-only协议为准。780M实际已完成61秒/976000原始样本FP16同模型控制，Vulkan0明确780M，3次神经push/6101帧；模型创建加推理2.4110s、全worker69.79s含60秒RAM稳定与哈希，job峰1920823296B<2GiB。48808后验比较最大绝对差0.016933918/均差0.000102672，0.5活动判定13/48808分歧0.00026635，全部在原冻结容差内；不是逐位等价、速度公平基准或新识别质量合格。首门通过后同冻结完整ES2003b活动推理已启动，当前实际活状态'+str(live)+'；这是说话人活动组件，不冒充完整ASR文字合格。记录脚本前一手写shell因中文弯引号导致Python字符串截断，未写入原账本/未影响独立推理；改用此独立脚本写完整原文。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'meeting':case['meeting'],'pid':run['pid'],'createdAt':run['createdAt'],
    'live':live,'state':run['state'],'cpuTemperatureMode':'observe-only'},ensure_ascii=False))
