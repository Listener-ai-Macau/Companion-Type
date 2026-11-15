"""Bounded, reference-free CPU speaker journal for one complete recording."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--index',required=True,type=int);args=p.parse_args()
C=Path(args.control);protocol=json.loads((C/'protocol.json').read_text(encoding='utf8'));case=json.loads((C/'audio-only.json').read_text(encoding='utf8'))[args.index]
assert not any('reference' in k.lower() for k in case)
runtime=protocol['runtime'];limits=WorkerLimits(cpu_percent=runtime['cpuPercent'],memory_bytes=runtime['privateBudgetBytes'])
out=C/'results'/case['meeting'];out.mkdir(parents=True,exist_ok=False)
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
state={'state':'LOADING_CPU_DIARIZATION','startedAt':now(),'pid':os.getpid(),'meeting':case['meeting'],'audioSha256':case['audioSha256'],'referencePassedToWorker':False,'modelGpuUsed':False}
started=time.perf_counter()
def save():
    state['limits']=limits.query()
    if not atomic_json(out/'state.json',state,progress=True):state['progressWriteDeferrals']=state.get('progressWriteDeferrals',0)+1
def checksum(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
save()
try:
    assert checksum(case['audio'])==case['audioSha256']
    import numpy as np,sherpa_onnx
    import sherpa_onnx.lib._sherpa_onnx as native
    assert sherpa_onnx.__version__==runtime['sherpa-onnx'] and checksum(native.__file__)==runtime['nativeExtensionSha256']
    for group in ['segmentation','embedding']:assert checksum(protocol[group]['model'])==protocol[group]['sha256']
    config=sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=protocol['segmentation']['model']),num_threads=1,provider='cpu'),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=protocol['embedding']['model'],num_threads=1,provider='cpu'),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=protocol['clustering']['numClusters'],threshold=protocol['clustering']['threshold']),
        min_duration_on=protocol['minDurationOn'],min_duration_off=protocol['minDurationOff'])
    assert config.validate() and config.clustering.num_clusters==-1
    diarizer=sherpa_onnx.OfflineSpeakerDiarization(config)
    assert diarizer.sample_rate==16000
    state.update(modelLoadSeconds=time.perf_counter()-started,actualConfig=str(config));save()
    with wave.open(case['audio'],'rb') as source:
        assert source.getnchannels()==1 and source.getsampwidth()==2 and source.getframerate()==16000 and source.getcomptype()=='NONE'
        count=source.getnframes();assert abs(count/16000-case['audioSeconds'])<1/16000
        audio=np.empty(count,dtype=np.float32)
        for start in range(0,count,65536):
            samples=np.frombuffer(source.readframes(min(65536,count-start)),dtype='<i2')
            np.divide(samples,32768.,out=audio[start:start+len(samples)],casting='unsafe')
    state.update(state='DIARIZING_FULL_AUDIO',audioSeconds=count/16000,inputSamples=count);save();tick=time.perf_counter()
    def progress(completed,total):
        if (C/'stop.request').exists():return 1
        state.update(embeddingChunksCompleted=completed,embeddingChunksTotal=total,inferenceElapsedSeconds=time.perf_counter()-tick);save();return 0
    result=diarizer.process(audio,callback=progress).sort_by_start_time()
    rows=[{'start':float(r.start),'end':float(r.end),'speaker':int(r.speaker)} for r in result]
    assert rows and all(0<=r['start']<r['end']<=case['audioSeconds']+.1 for r in rows)
    assert not (C/'stop.request').exists(),'Explicit stop requested'
    (out/'speaker-journal.json').write_text(json.dumps({'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'segments':rows,'scope':'Model-predicted anonymous speaker activity. No text, real identity, role or exact word alignment.'},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rttm=out/'predicted.rttm';rttm.write_text(''.join(f"SPEAKER {case['meeting']} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> speaker_{r['speaker']} <NA> <NA>\n" for r in rows),encoding='utf8')
    state.update(state='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED',inferenceSeconds=time.perf_counter()-tick,predictedSpeakers=len({r['speaker'] for r in rows}),segments=len(rows),rttmSha256=checksum(rttm))
except BaseException as error:
    state.update(state='FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-started);save()
    atomic_json(out/'completed-state.json',state)
    print(json.dumps(state,ensure_ascii=False),flush=True)
