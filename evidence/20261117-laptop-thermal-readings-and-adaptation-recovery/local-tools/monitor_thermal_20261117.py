"""Owned one-hour read-only ACPI temperature log; no GPU/CPU training."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,subprocess,sys,time
import psutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
from read_amd_temperatures_20261117 import query as amd_temperatures

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=3600);parser.add_argument('--laptop',action='store_true');a=parser.parse_args()
    assert 10<=a.seconds<=3600
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
    a.output.mkdir(parents=True,exist_ok=False)
    command=['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive',
        '-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('read_laptop_thermal_stream_20261117.ps1' if a.laptop else 'read_thermal_stream_20261117.ps1')),
        '-DurationSeconds',str(a.seconds),'-IntervalSeconds','5']
    before={p.pid:(p.info['cpu_times'].user+p.info['cpu_times'].system) for p in psutil.process_iter(['cpu_times'])}
    previous=time.monotonic();psutil.cpu_percent();samples=0;minimum=None;maximum=None;cpu_minimum=None;cpu_maximum=None
    started={'state':'READ_ONLY_LAPTOP_THERMAL_MONITOR_RUNNING' if a.laptop else 'READ_ONLY_ACPI_AMD_THERMAL_MONITOR_RUNNING','at':datetime.now().astimezone().isoformat(),
        'pid':os.getpid(),'createdAt':psutil.Process().create_time(),'durationSeconds':a.seconds,
        'sampleIntervalSeconds':5,'readOnly':True,'driverInstalledByThisLogger':False,
        'cpuSensorDriverPreviouslyExplicitlyAuthorized':a.laptop,'externalGpuQueried':not a.laptop,'torchImported':False,
        'gpuTasksStarted':0,'cpuTrainingStarted':False,'limits':limits.query()}
    atomic_json(a.output/'started.json',started)
    with (a.output/'stderr.log').open('w',encoding='utf-8') as error,(a.output/'samples.jsonl').open('x',encoding='utf-8') as log:
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=error,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for line in iter(proc.stdout.readline,b''):
                if not line.strip():continue
                row=json.loads(line.decode('utf-8-sig'));tick=time.monotonic();elapsed=tick-previous
                process_rows=[];after={}
                for process in psutil.process_iter(['name','cpu_times']):
                    value=process.info['cpu_times'].user+process.info['cpu_times'].system;after[process.pid]=value
                    if process.pid in before:
                        rate=100*max(0,value-before[process.pid])/elapsed/psutil.cpu_count()
                        if process.pid!=0 and rate>=1:process_rows.append({'pid':process.pid,'name':process.info['name'],'cpuPercentOfWholeMachine':round(rate,2)})
                before=after;previous=tick
                row.update(cpuPercent=psutil.cpu_percent(),availableRamBytes=psutil.virtual_memory().available,
                    topCpuProcesses=sorted(process_rows,key=lambda r:r['cpuPercentOfWholeMachine'],reverse=True)[:6])
                if not a.laptop:
                    try:row['amdDriverTemperatures']=amd_temperatures()
                    except Exception as error:row['amdDriverTemperatures']={'queryError':repr(error)}
                for zone in row['Zones']:
                    value=zone['Celsius']
                    if value is not None:minimum=value if minimum is None else min(minimum,value);maximum=value if maximum is None else max(maximum,value)
                for sensor in row.get('CpuSensors',[]):
                    value=sensor['Celsius']
                    if value is not None:cpu_minimum=value if cpu_minimum is None else min(cpu_minimum,value);cpu_maximum=value if cpu_maximum is None else max(cpu_maximum,value)
                log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush();os.fsync(log.fileno());samples+=1
                atomic_json(a.output/'latest.json',{'state':started['state'],'samples':samples,'minimumCelsius':minimum,
                    'maximumCelsius':maximum,'cpuMinimumCelsius':cpu_minimum,'cpuMaximumCelsius':cpu_maximum,
                    'latest':row,'physicalAcpiSensorLocationVerified':False})
                if (a.output/'stop.request').exists():proc.terminate();break
            code=proc.wait(timeout=20)
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=20)
    result={'state':'READ_ONLY_ACPI_THERMAL_MONITOR_FINISHED','at':datetime.now().astimezone().isoformat(),
        'exitCode':code,'samples':samples,'minimumCelsius':minimum,'maximumCelsius':maximum,
        'cpuMinimumCelsius':cpu_minimum,'cpuMaximumCelsius':cpu_maximum,'externalGpuQueried':not a.laptop,
        'physicalSensorLocationVerified':False,'overheatCauseProven':False,'readOnly':True,
        'ownedStopRequested':(a.output/'stop.request').exists(),
        'newNeuralCalls':0,'parameterUpdates':0,'limits':limits.query()}
    atomic_json(a.output/'completed.json',result);print(json.dumps(result))

if __name__=='__main__':main()
