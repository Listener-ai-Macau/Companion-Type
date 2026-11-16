"""Preserve the second overnight restart, without loading a neural runtime."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import psutil

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
run=E/'guarded-native-context180-r2/run-extension';out=E/'system-restart-20261116-2315'
out.mkdir(exist_ok=False);raw=out/'owned-run-original-bytes';raw.mkdir()
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
copies=[]
for p in run.rglob('*'):
    if not p.is_file():continue
    target=raw/p.relative_to(run);target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p,target);assert sha(p)==sha(target)
    copies.append({'source':str(p),'copy':str(target),'bytes':p.stat().st_size,
        'sha256':sha(p),'modified':datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat()})
ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
q='*[System[TimeCreated[@SystemTime >= "2026-11-16T14:50:00.000Z" and @SystemTime <= "2026-11-16T15:25:00.000Z"]]]'
events={}
for channel in ['System','Application']:
    r=subprocess.run(['C:/Windows/System32/wevtutil.exe','qe',channel,'/q:'+q,'/rd:false','/f:xml','/c:2000'],
        capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode==0,r.stderr
    text='<Events>'+r.stdout+'</Events>';(out/(channel+'.xml')).write_text(text,encoding='utf-8')
    rows=[]
    for e in ET.fromstring(text):
        s=e.find('e:System',ns)
        rows.append({'timeUtc':s.find('e:TimeCreated',ns).get('SystemTime'),
            'provider':s.find('e:Provider',ns).get('Name'),'id':int(s.findtext('e:EventID',namespaces=ns)),
            'level':int(s.findtext('e:Level',namespaces=ns)),
            'data':[(x.get('Name'),x.text) for x in e.findall('e:EventData/e:Data',ns)]})
    events[channel]=rows
    (out/(channel+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
operators=[]
for line in (raw/'gpu-operators.jsonl').read_text(encoding='utf-8').splitlines():
    try:operators.append(json.loads(line))
    except json.JSONDecodeError:pass
last=next(r for r in reversed(operators) if r.get('event')=='exit' and 'memory' in r)
partial=json.loads((raw/'current-partial.json').read_text(encoding='utf-8'))
blocks=[]
for f in sorted((raw/'results').glob('*.json')):
    d=json.loads(f.read_text(encoding='utf-8'))
    blocks.append({k:d[k] for k in ['id','meeting','startFrame','endFrame','frames','naturalEos','seconds','trainingUpdates']})
assert len(blocks)==2 and sum(x['frames'] for x in blocks)==5760000
assert blocks[0]['endFrame']==blocks[1]['startFrame'] and all(x['naturalEos'] for x in blocks)
zero=[]
for rel in ['state.json','inference/state.json']:
    p=raw/rel;b=p.read_bytes();zero.append({'file':str(p),'bytes':len(b),'allZero':not any(b),'sha256':sha(p)})
models=[]
for p in psutil.process_iter(['name','cmdline','create_time']):
    if p.pid==__import__('os').getpid():continue
    if p.info['name'] and 'python' in p.info['name'].lower() and any('model-research' in a or 'amd-runtime' in a for a in p.info['cmdline'] or []):models.append({'pid':p.pid,**p.info})
system=events['System'];before=[x for x in system if x['timeUtc']<'2026-11-16T15:16:08.000Z']
old_report=Path('C:/ProgramData/Microsoft/Windows/WER/ReportQueue/Kernel_1cc_a7926a1d767f542ccdc47716af41ce0a07aa0_00000000_764e2650-bf3e-4c73-8b48-90786cd7e00a/Report.wer')
wer=None
if old_report.exists():
    fields=dict(s.split('=',1) for s in old_report.read_text(encoding='utf-16',errors='replace').splitlines() if '=' in s)
    wer={'file':str(old_report),'code':fields.get('Sig[0].Value'),'reportId':fields.get('ReportIdentifier'),
        'actualEventUtc':datetime.fromtimestamp((int(fields['EventTime'])-116444736000000000)/1e7,timezone.utc).isoformat()}
summary={'state':'SECOND_OVERNIGHT_UNEXPECTED_RESTART_DURING_MOSS_GPU_INFERENCE_CAUSE_NOT_IDENTIFIED',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),'windowsReportedPreviousShutdown':'2026-11-16T23:15:26+08:00',
    'actualBoot':datetime.fromtimestamp(psutil.boot_time()).astimezone().isoformat(),
    'timeBoundary':'Event6008 reports23:15:26; persisted model/operator files reach23:15:50/51. Treat this as an approximate23:15 incident, not an exact synchronized crash instant.',
    'ownedRun':str(run),'pidBeforeRestart':19924,'modelRole':'Published nativeMOSS0.9B complete-source180s ASR inference on RX6800XT, not weight training',
    'gpuProfile':'MIOpen convolution disabled, per-operator synchronization, Torch allocator50percent, CPU25percent and2GiB private limit; no hard GPU power/thermal limit',
    'lastCompletedOperator':last,'lastCompleteOperatorWasNotAnError':True,
    'lastObservedGpuReservedGiB':last['memory']['reservedBytes']/2**30,
    'observedGpuReservedPeakGiB':last['memory']['peakReservedBytes']/2**30,
    'lastObservedDriverFreeGiB':last['memory']['driverFreeBytes']/2**30,
    'lastObservedSystemAvailableGiB':last['memory']['systemAvailableBytes']/2**30,
    'resourceSamplesAreNotGuaranteedInstantOfCrash':True,
    'completedOriginalBlocks':blocks,'completedAudioSeconds':360,
    'wholeSourcesCompleted':0,'trainingParameterUpdates':0,'english119MTrainingStarted':False,
    'operatorRowsPreserved':len(operators),'lastPartialId':partial['id'],'lastPartialGeneratedTokens':len(partial['generatedIds']),
    'zeroFilledProgressFiles':zero,'progressFileDurabilityDefectObserved':True,
    'unexpectedEvents':[x for x in system if x['id'] in [41,6008]],
    'prebootErrorsAndWarnings':[x for x in before if x['level']<=3],
    'prebootMemoryExhaustionOrDisplayRecoveryEvents':[x for x in before if x['id'] in [2004,4101]],
    'currentDumpFiles':{'minidumpFiles':[str(p) for p in Path('C:/Windows/Minidump').glob('*')],
        'liveKernelCurrent':[str(p) for p in Path('C:/Windows/LiveKernelReports').glob('*.dmp') if p.stat().st_mtime>=datetime(2026,11,16,23).timestamp()]},
    'oldRequeuedWerNotThisIncident':wer,'currentOwnedModelProcesses':models,'preservedFiles':copies,
    'conclusion':'The ownedGPUworkload remains the leading suspected trigger. Recurrence with a different model while MIOpen is bypassed disproves that the previous workaround established long-run stability or isolated the issue to MIOpen. Available samples do not showVRAM/RAM exhaustion. No matched newdump/bugcheck identifies compute runtime, driver, dock link, power or thermal cause.',
    'next':'Do not automatically rerun this unchanged GPU recipe. Preserve original bytes, fix journal durability and continue read-only driver/runtime/dock analysis plus CPU code/data work. No driver/TDR/power/BIOS change or GPU stress test in this inspection.',
    'newNeuralCalls':0,'parameterUpdates':0,'torchImported':'torch' in sys.modules,
    'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
f=out/'incident.json';f.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/gpu-compatibility-r1'
compact={k:v for k,v in summary.items() if k not in ['preservedFiles','prebootErrorsAndWarnings','limits']}
(J/'second-restart-20261117.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'report':str(f),'boot':summary['actualBoot'],'completedAudioSeconds':360,
    'gpuPeakReservedGiB':summary['observedGpuReservedPeakGiB'],'lastDriverFreeGiB':summary['lastObservedDriverFreeGiB'],
    'lastSystemAvailableGiB':summary['lastObservedSystemAvailableGiB'],'zeroProgressFiles':len(zero),
    'newMatchingDumpFiles':summary['currentDumpFiles'],'currentOwnedModelProcesses':models,'newNeuralCalls':0},ensure_ascii=False))
