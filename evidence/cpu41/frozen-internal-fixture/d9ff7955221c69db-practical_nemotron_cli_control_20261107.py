"""Native61s oracle for the C ABI wrapper; same official weights/preset/threshold."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,subprocess,time,traceback
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--index',required=True,type=int);a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));P=read(C/'protocol.json');case=read(C/'audio-only.json')[a.index];assert case['audioSeconds']<=61
out=C/'results'/case['meeting'];target=out/'native-cli-control.json';assert not target.exists();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'RUNNING_OFFICIAL_CLI_CONTROL','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'pid':os.getpid(),'referenceInput':False,'gpuUsed':False};atomic_json(target,state)
try:
    exe=Path(P['nativeExe']);assert hashlib.sha256(exe.read_bytes()).hexdigest()==P['nativeExeSha256']
    assert all(hashlib.sha256((exe.parent/name).read_bytes()).hexdigest()==digest for name,digest in P['nativeFiles'].items())
    device='cpu'
    if P['backend']=='vulkan':
        from practical_native_devices_20261107 import devices,select_6800xt
        cookie=os.add_dll_directory(str(exe.parent));inventory=devices(exe.parent);selected=select_6800xt(inventory);device='vulkan:'+str(selected['gpuOrdinal']);state.update(gpuUsed=True,selectedNativeDevice=selected)
    g=P['streamingGeometry']
    command=[str(exe),'diarize',case['audio'],'--model',P['model'],'--device',device,'--diar-chunk',str(g['chunk_len']),'--diar-rc',str(g['right_context']),'--diar-lc',str(g['left_context']),'--diar-fifo',str(g['fifo_len']),'--diar-spkcache',str(g['spkcache_len']),'--diar-update-period',str(g['update_period']),'--no-batching','--format','json','--onset','0.5','--offset','0.5','--pad-onset','0','--pad-offset','0','--min-duration-on','0','--min-duration-off','0','--output',str(out/'native-cli-output.json')]
    env={k:v for k,v in os.environ.items() if not k.startswith('NEMO_SPEECH_')};env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with (out/'native-cli.log').open('xb') as log:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,cwd=exe.parent,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
    assert code==0,'Official native CLI failed, see retained log'
    expected=read(out/'native-cli-output.json')['segments'];actual=read(out/'speaker-journal.json')['segments']
    expected=[{**r,'end':min(r['end'],case['audioSeconds'])} for r in expected if r['start']<min(r['end'],case['audioSeconds'])]
    expected.sort(key=lambda r:(round(r['start'],3),round(r['end'],3),r['speaker']));actual.sort(key=lambda r:(round(r['start'],3),round(r['end'],3),r['speaker']))
    assert len(actual)==len(expected),'Native segment counts differ'
    for x,y in zip(actual,expected):assert x['speaker']==y['speaker']-1 and abs(x['start']-y['start'])<=.000501 and abs(x['end']-y['end'])<=.000501,'C ABI conversion differs from official CLI'
    state.update(state='PASS_NATIVE61_C_ABI_AND_OFFICIAL_CLI_SEGMENTS',segments=len(actual),allSpeakerIdsMatch=True,allTimesMatchToCliMillisecondPrecision=True,fullMultiPushStateExercised=case['audioSeconds']>60,qualityQualified=False)
except BaseException as error:state.update(state='FAILED_NATIVE_CLI_COMPATIBILITY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state,ensure_ascii=False),flush=True)
