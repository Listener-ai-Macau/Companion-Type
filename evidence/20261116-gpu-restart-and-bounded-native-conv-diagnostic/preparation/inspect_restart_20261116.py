"""Read-only Windows/owned-worker evidence for the21:36 unexpected restart.

No neural runtime, GPU query, stress test, system setting, or other-process action.
Raw system evidence stays local on E:. No raw audio or transcript is read.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import psutil
import winreg

SRC=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
sys.path.insert(0,str(SRC))
from meeting_acoustic_worker_20261116 import own_limits
limits=own_limits(5)
BASE=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
OUT=BASE/'system-restart-20261116-213635'
OUT.mkdir(exist_ok=True)
NS={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(data):return hashlib.sha256(data).hexdigest()
def events(channel,query,name):
    r=subprocess.run(['C:/Windows/System32/wevtutil.exe','qe',channel,'/q:'+query,
        '/rd:false','/f:xml','/c:2000'],capture_output=True,text=True,timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW)
    (OUT/(name+'.xml')).write_text('<Events>'+r.stdout+'</Events>',encoding='utf-8')
    if r.returncode: return {'error':r.stderr,'code':r.returncode}
    rows=[]
    for ev in ET.fromstring('<Events>'+r.stdout+'</Events>'):
        s=ev.find('e:System',NS)
        rows.append({'timeUtc':s.find('e:TimeCreated',NS).get('SystemTime'),
            'provider':s.find('e:Provider',NS).get('Name'),
            'id':int(s.findtext('e:EventID',namespaces=NS)),
            'level':int(s.findtext('e:Level',namespaces=NS)),
            'recordId':s.findtext('e:EventRecordID',namespaces=NS),
            'data':[(x.get('Name'),x.text) for x in ev.findall('e:EventData/e:Data',NS)]})
    write(name+'.json',rows)
    return rows

window='*[System[TimeCreated[@SystemTime >= "2026-11-16T09:30:00.000Z" and @SystemTime <= "2026-11-16T14:00:00.000Z"]]]'
system=events('System',window,'system-window')
application=events('Application',window,'application-window')
history=events('System','*[System[TimeCreated[timediff(@SystemTime) <= 1209600000] and (EventID=41 or EventID=6008 or EventID=1074 or EventID=2004 or EventID=4101 or Provider[@Name="Microsoft-Windows-WHEA-Logger"])]]','restart-history14d')
owned=[]
for folder in ['frcrn-front-end-r1/run-r2/enhance','native-context180-r1/run-initial','english-transducer-r1/run-r1']:
    root=BASE/folder
    for name in ['state.json','completed.json','dsp-control.json','dsp-roundtrip-inspection.json','weight-proof.json']:
        f=root/name
        if f.exists():
            b=f.read_bytes(); target=folder.replace('/','--')+'--'+name
            (OUT/target).write_bytes(b)
            owned.append({'source':str(f),'copy':str(OUT/target),'sha256':sha(b)})

def registry(key,names):
    result={}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,key) as h:
            for n in names:
                try:result[n]=winreg.QueryValueEx(h,n)[0]
                except OSError as e:result[n]={'error':str(e)}
    except OSError as e:result={'error':str(e)}
    return result

dumps=[];wers=[]
for folder in ['C:/Windows/Minidump','C:/Windows/LiveKernelReports',
               'C:/ProgramData/Microsoft/Windows/WER/ReportQueue',
               'C:/ProgramData/Microsoft/Windows/WER/ReportArchive']:
    d=Path(folder)
    try:
        for p in sorted(d.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True)[:20]:
            st=p.stat()
            dumps.append({'path':str(p),'bytes':st.st_size,'modified':datetime.fromtimestamp(st.st_mtime).astimezone().isoformat()})
            if p.is_dir():
                for f in p.glob('Report.wer'):
                    t=f.read_text(encoding='utf-16',errors='replace')
                    fields=dict(s.split('=',1) for s in t.splitlines() if '=' in s)
                    if fields.get('EventType')=='LiveKernelEvent':
                        ft=int(fields['EventTime']);dt=datetime.fromtimestamp((ft-116444736000000000)/10000000,timezone.utc)
                        wers.append({'path':str(f),'eventTimeUtc':dt.isoformat(),
                            'eventType':fields['EventType'],'code':fields.get('Sig[0].Value'),
                            'modified':datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(),
                            'sha256':sha(f.read_bytes())})
    except OSError as e:dumps.append({'path':str(d),'error':str(e)})
for name in ['C:/Windows/MEMORY.DMP']:
    p=Path(name)
    dumps.append({'path':name,'exists':p.exists()})

models=[]
for p in psutil.process_iter(['pid','name','cmdline','create_time']):
    if p.pid==os.getpid():continue
    try:
        cmd=p.info['cmdline'] or []
        if p.info['name'] and 'python' in p.info['name'].lower() and any('model-research' in a or 'amd-runtime' in a for a in cmd):
            models.append(p.info)
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
last= json.loads((OUT/'frcrn-front-end-r1--run-r2--enhance--state.json').read_text(encoding='utf-8'))
rows=system if isinstance(system,list) else []
unexpected=[r for r in rows if r['id'] in [41,6008]]
preboot=[r for r in rows if r['timeUtc']<'2026-11-16T13:37:12.000Z']
report={
    'state':'UNEXPECTED_RESTART_CORRELATED_WITH_OWNED_GPU_ENHANCEMENT_CAUSE_UNPROVEN',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'ownerReports':['突然黑屏／直接重启','显卡坞，最近每晚发生、以前没有、白天上班不发生；高度怀疑本任务'],
    'currentBoot':datetime.fromtimestamp(psutil.boot_time()).astimezone().isoformat(),
    'unexpectedShutdownLocalTime':'2026-11-16T21:36:35+08:00',
    'lastOwnedWorker':last,
    'inferenceNotTraining':last['trainingUpdates']==0,
    'lastObservedWorkerPrivateGiB':last['limits']['jobPeakPrivateCommitBytes']/2**30,
    'lastObservedMemoryIsNotFinalCrashSample':True,
    'historicalVramPowerTemperaturePcieTelemetryAvailable':False,
    'event41And6008':unexpected,
    'prebootRelevantEvents':[r for r in preboot if r['level']<=3 or r['id'] in [2004,4101,1074,6006]],
    'currentOwnedModelProcesses':models,
    'currentRamIsNotHistoricalEvidence':dict(psutil.virtual_memory()._asdict()),
    'diskFreeBytes':{d:shutil.disk_usage(d).free for d in ['C:/','E:/']},
    'crashControlReadOnly':registry('SYSTEM/CurrentControlSet/Control/CrashControl'.replace('/','\\'),['CrashDumpEnabled','AutoReboot','LogEvent','DumpFile','MinidumpDir']),
    'pagingReadOnly':registry('SYSTEM/CurrentControlSet/Control/Session Manager/Memory Management'.replace('/','\\'),['PagingFiles','ExistingPageFiles']),
    'dumpInventory':dumps,'kernelWerActualEventTimes':wers,'preservedWorkerFiles':owned,
    'decision':'Hold all new GPU inference/training. Do not rerun FRCRN, alter driver/TDR/power settings, or stress-test. Continue CPU-only code/data/error analysis with original limits.',
    'cause':'Owned GPU workload is the leading suspected trigger given timing and owner repeated-night reports. VRAM exhaustion, driver failure, dock link/power, thermal or other hardware cause not distinguished by current evidence.',
    'limits':limits.query(),'torchImported':'torch' in sys.modules,
    'newNeuralCalls':0,'trainingUpdates':0,'systemOrOtherAppSettingsChanged':False,
}
write('incident.json',report)
print(json.dumps({'evidence':str(OUT/'incident.json'),'state':report['state'],
    'lastWorkerObserved':last['observedAt'],'trainingUpdates':last['trainingUpdates'],
    'lastPrivateGiB':report['lastObservedWorkerPrivateGiB'],
    'currentOwnedModelProcesses':models,'prebootRelevantEvents':report['prebootRelevantEvents'],
    'kernelWerActualEventTimes':wers,
    'recentRestartEvents':[r for r in history if r['id'] in [41,6008]] if isinstance(history,list) else history,
    'torchImported':report['torchImported']},ensure_ascii=False))
