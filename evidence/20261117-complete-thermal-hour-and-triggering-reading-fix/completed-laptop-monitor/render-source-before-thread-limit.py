"""Plot the completed hour; ordinary workload, not a controlled cooling test."""
from pathlib import Path
from datetime import datetime
import json,os,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from meeting_acoustic_contract_20261116 import read,sha
from durable_model_state_20261117 import atomic_json
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
run=E/'system-restart-20261116-2315/laptop-thermal-r3'
complete=read(run/'completed.json');assert complete['exitCode']==0
rows=[json.loads(line) for line in (run/'samples.jsonl').read_text(encoding='utf-8').splitlines() if line]
assert len(rows)==complete['samples']
os.environ['MPLCONFIGDIR']=str(run/'mpl-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as dates
plt.rcParams['font.family']='Microsoft YaHei'
times=[datetime.fromisoformat(r['At']).replace(tzinfo=None) for r in rows]
cpu=[next(s['Celsius'] for s in r['CpuSensors'] if s['Identifier']=='/amdcpu/0/temperature/2') for r in rows]
zone=[r['Zones'][0]['Celsius'] if r['Zones'] else None for r in rows]
load=[r['cpuPercent'] for r in rows]
vad=read(E/'context-activity-r1/silero-presence-r1/run-default/state.json')
begin=datetime.fromisoformat(vad['at']).replace(tzinfo=None)
end=datetime.fromisoformat(vad['observedAt']).replace(tzinfo=None)
fig,(top,bottom)=plt.subplots(2,1,figsize=(13,6.8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
top.plot(times,cpu,color='#b24331',linewidth=1.5,label='CPU Tctl/Tdie（已识别传感器）')
top.plot(times,zone,color='#7e8c99',linewidth=1.1,label='ACPI TZ01（位置未知）')
top.axhline(95,color='#b24331',linestyle='--',linewidth=1,label='本任务停止条件 95°C')
top.axhline(100,color='#555555',linestyle=':',linewidth=1,label='7840HS 官方 Tjmax 100°C')
hot=[i for i,v in enumerate(cpu) if v>=95]
top.scatter([times[i] for i in hot],[cpu[i] for i in hot],color='#b24331',s=13,zorder=4)
top.set_ylabel('温度 / °C');top.set_ylim(40,103);top.legend(loc='lower left',fontsize=9,ncol=2)
bottom.plot(times,load,color='#24576c',linewidth=1,label='整机 CPU 占用（包含其它应用）')
bottom.set_ylabel('CPU 占用 / %');bottom.set_ylim(0,100);bottom.legend(loc='upper left',fontsize=9)
for axis in [top,bottom]:
    axis.axvspan(begin,end,color='#507fb0',alpha=.14)
    axis.axvline(end,color='#507fb0',linewidth=1)
    axis.grid(alpha=.18);axis.set_axisbelow(True)
bottom.xaxis.set_major_locator(dates.MinuteLocator(interval=10));bottom.xaxis.set_major_formatter(dates.DateFormatter('%H:%M'))
bottom.set_xlabel('北京时间 · 2026-11-17')
top.set_title('笔记本一小时温度记录｜蓝色区域为本任务 CPU VAD 生命周期（含启动等待）',loc='left',fontsize=12,pad=12)
fig.text(.07,.015,'09:17:40 读到 95°C；本任务 09:17:41 退出。此前也有高温记录。未运行模型 GPU 任务；未记录空调切换时刻，不能据此确认昨晚重启根因。',fontsize=9,color='#555555')
fig.tight_layout(rect=[0,.045,1,1]);target=run/'laptop-temperature-hour.png';assert not target.exists()
fig.savefig(target,dpi=150,facecolor='white');plt.close(fig)
peak=max(range(len(cpu)),key=lambda i:cpu[i]);last=rows[-1]
report={'state':'COMPLETE_ONE_HOUR_IDENTIFIED_LAPTOP_CPU_THERMAL_OBSERVATION',
    'at':datetime.now().astimezone().isoformat(),'samples':len(rows),'firstAt':rows[0]['At'],'lastAt':last['At'],
    'cpuMinimumCelsius':min(cpu),'cpuMaximumCelsius':max(cpu),'peakAt':rows[peak]['At'],
    'lastCpuCelsius':cpu[-1],'samplesAtOrAbove95C':len(hot),
    'firstHighSampleAt':rows[hot[0]]['At'] if hot else None,
    'detectorTaskStartedAt':vad['at'],'detectorStoppedAt':vad['observedAt'],
    'detectorStoppedByOwned95CTaskPolicy':True,'systemRebootedDuringObservation':False,
    'noGpuModelTaskExecuted':True,'modelParameterUpdates':0,'coolingOrWorkloadControlled':False,
    'airConditionerChangeTimeRecorded':False,'motherboardTemperatureMeasured':False,
    'thermalShutdownCauseProven':False,'plot':str(target),'plotSha256':sha(target),
    'samplesSha256':sha(run/'samples.jsonl'),'completedSha256':sha(run/'completed.json'),
    'loggerSourceSha256':{n:sha(run/n) for n in ['monitor_thermal_20261117.py','read_laptop_thermal_stream_20261117.ps1']},
    'monitorTerminal':True,'limits':limits.query()}
atomic_json(run/'analysis.json',report)
print(json.dumps(report,ensure_ascii=False))
