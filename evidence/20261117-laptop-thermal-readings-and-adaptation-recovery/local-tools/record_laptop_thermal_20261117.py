"""Preserve identified CPU readings and Owner's laptop-cooling priority."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
scene=E/'system-restart-20261116-2315';run=scene/'laptop-thermal-r3'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
at=datetime.now().astimezone().isoformat(timespec='seconds')
started=read(run/'started.json');process=psutil.Process(started['pid'])
assert abs(process.create_time()-started['createdAt'])<.01 and process.is_running()
latest=read(run/'latest.json');first=read(scene/'cpu-package-r1/result.json')
assert latest['latest']['ExternalGpuQueried'] is False and latest['latest']['MotherboardEcOrSmbusProbed'] is False
assert latest['latest']['CpuSensors'][0]['Identifier']=='/amdcpu/0/temperature/2'
snapshot={}
for name in ['monitor_thermal_20261117.py','read_laptop_thermal_stream_20261117.ps1']:
    source=Path('work')/name;dest=run/name
    if not dest.exists():shutil.copyfile(source,dest)
    assert sha(source)==sha(dest);snapshot[name]=sha(dest)
report={'at':at,'state':'IDENTIFIED_CPU_TCTL_TDIE_CONTINUOUS_LAPTOP_MONITOR_LIVE_NO_OVERHEAT_CAUSE_PROOF',
    'ownerQuotes':['允许安装并读取 CPU 温度',
        '感觉像是显卡，我在训练的时候太热了，然后把那个东西给搞死机了。是不是要买个外部的散热器呢？因为我发现开空调的时候就不死机。',
        '显卡屋的温度就不用管，应该是笔记本的温度。显卡屋的温度不会导致笔记本死机的。'],
    'priority':'Laptop CPU and internal thermal behavior. ExternalGPU temperature polling stopped as requested; external-link/runtime hypotheses are not logically disproven.',
    'driver':{**read(scene/'prepared-cpu-sensor-tool/installation-result.json'),
        'provenance':read(scene/'prepared-cpu-sensor-tool/prepared-receipt.json'),
        'officialArchiveSha256':'086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001',
        'release':'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6'},
    'firstIdentifiedCpuBaseline':first,
    'currentMonitor':{'run':str(run),'pid':started['pid'],'createdAt':started['createdAt'],'session':69371,
        'liveVerifiedAt':at,'durationSeconds':3600,'sampleIntervalSeconds':5,
        'sourceSha256':snapshot,'latestAt':latest['latest']['At'],'samplesObserved':latest['samples'],
        'cpuRangeCelsius':[latest['cpuMinimumCelsius'],latest['cpuMaximumCelsius']],
        'acpiRangeCelsius':[latest['minimumCelsius'],latest['maximumCelsius']],
        'latest':latest['latest'],'privateMemoryBytes':process.memory_info().private},
    'cpuSensorPhysicalIdentity':'AMD Ryzen7 7840HS Core(Tctl/Tdie), /amdcpu/0/temperature/2',
    'cpuPackageMeasured':True,'motherboardVrmsUsb4ControllerTemperaturesMeasured':False,
    'acpiZoneIsNotCpuSensor':True,'acpiPhysicalLocationUnknown':True,
    'oldAcpi96CWasNotPersistentAcrossWholeRun':True,
    'airConditioningObservationIsOwnerReportNotControlledExperiment':True,
    'lastNightTemperaturePeakKnown':False,'overheatRestartProven':False,
    'cpuTjmax':{'celsius':100,'url':'https://www.amd.com/zh-cn/products/processors/laptop/ryzen/7000-series/amd-ryzen-7-7840hs.html'},
    'coolingDecision':'Improve laptop intake clearance/room cooling first; use an existing fan for a matched normal-workload temperature comparison before choosing a pad. A cooling pad may help airflow; it does not repair a failing internal fan/heatsink/thermal interface. No product-specific temperature reduction or purchase guarantee.',
    'coolingReference':'https://www.dell.com/support/kbdoc/en-us/000133111/dell-portable-system-heat-issue-or-the-system-is-overheating',
    'modelGpuTasksStarted':0,'cpuModelTraining':False,'fanClockPowerSettingsChanged':False,
    'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'saleQualified':False,
    'next':'Continue bounded laptop-only logging and correlate identified CPU temperature with ordinary workload/cooling. Do not trigger a thermal shutdown to prove the hypothesis. Keep original ASR data/code work moving without CPU/iGPU training.'}
target=J/'gpu-compatibility-r1/laptop-thermal-status-20261117.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
old=o['thermalMonitor20261117'];o['thermalMonitor20261117']={'initialAcpiAndAmdReceipt':old.get('initialAcpiAndAmdReceipt',old),
    'latest':report,'latestReceipt':str(target)}
x['next']='先沿laptopThermalStatus实测CPU Tctl/Tdie及ACPI连续温度，按Owner最新要求聚焦笔记本，外显卡温度轮询已停。已授权安装的签名PawnIO只用于传感器；当前无模型GPU/CPU训练，不用热关机复现。开空调稳定属于Owner线索，未认定根因；保留计算环境/链路旧证据。继续英文TDT119M适配CPU侧独立评分/协议，GPU梯度/稳态最大形状/检查点仍待安全执行条件，原95/98及人物/盲测门不变。'
x['logResult']+='\n\n'+at+'｜Owner明确允许安装并读CPU温度，补充开空调不死机、优先笔记本而非显卡坞散热。已下载LHM0.9.6官方稳定包，SHA与GitHub资产digest一致；仅反射提取内附PawnIO安装器、Windows签名Valid/namazso.eu、SHA a3a46226...，授权后-install exit0，无本任务重启。后台CPU-only传感器首60秒13点读7840HS Core(Tctl/Tdie)86.125–92.375°C，非原96°C不明ACPI测点；AMD官方Tjmax100°C，不据当前温度认定昨晚热关机。后续r3单一CPU/ACPI采样器每5秒持续1小时，PID'+str(started['pid'])+'实际核活，CPU5%/私有256MiB保护；外GPU轮询r2依最新要求自有stop.request终止，原源/数据保留，不当再次崩溃。r2完整196点ACPI55.05–96.05°C，原先固定96只是局部时段；主板供电/USB4控制器无直接温度，不混CPU。未改风扇/频率/功耗，不压测、不训练；原空调相关性保留未控对照，建议先改善笔记本进风和现有风扇、按相近正常负载温度决定散热底座，不把购买当修复。结果'+str(target)+'。\n'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'receipt':str(target),'pid':started['pid'],'cpuRange':report['currentMonitor']['cpuRangeCelsius'],'samples':latest['samples']},ensure_ascii=False))
