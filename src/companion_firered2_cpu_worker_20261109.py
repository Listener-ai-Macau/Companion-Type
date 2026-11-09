"""Recovered frozen FireRed2 AED checkpoint, raw-preserving serial CPU review."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,sys,time,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import repeated_block

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--phase',choices=['probe','full'],required=True);p.add_argument('--meeting');a=p.parse_args();C=Path(a.control);P=read(C/'run-protocol.json');assert sha(__file__)==P['workerSha256'];assert sha(C/'model-ready.json')==P['modelReadySha256'];inputs=read(C/'probe-audio-only.json') if a.phase=='probe' else [next(x for x in read(C/'full-audio-only.json') if x['meeting']==a.meeting)];out=C/('probe' if a.phase=='probe' else 'full-'+a.meeting);out.mkdir(exist_ok=False)
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();start=time.perf_counter();state={'state':'LOADING_FROZEN_FIRERED2_AED','pid':os.getpid(),'phase':a.phase,'referencePassedToWorker':False,'newNeuralCalls':0,'results':[],'weightsChanged':False,'startedAt':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')}
 def save():state.update(limits=limits.query(),wallSeconds=time.perf_counter()-start);atomic_json(out/'state.json',state)
 save()
 try:
  if pressure.low():raise RuntimeError('ActualWindowsLOWRAM beforeload')
  ready=read(C/'model-ready.json');assert ready['state']=='PINNED_COMPLETE_FIRERED2_AED_INT8_READY_NOT_INFERRED';root=Path(ready['modelRoot'])
  for name in ['encoder.int8.onnx','decoder.int8.onnx','tokens.txt']:
   entry=next(r for r in ready['files'] if Path(r['file']).name==name);assert sha(root/name)==entry['sha256']
  import sherpa_onnx
  import numpy as np
  tick=time.perf_counter();recognizer=sherpa_onnx.OfflineRecognizer.from_fire_red_asr(encoder=str(root/'encoder.int8.onnx'),decoder=str(root/'decoder.int8.onnx'),tokens=str(root/'tokens.txt'),num_threads=1,decoding_method='greedy_search',provider='cpu');state.update(modelLoadSeconds=time.perf_counter()-tick,runtime=sherpa_onnx.__version__,configuration=str(recognizer.config),state='READY');save()
  for packet in inputs:
   assert sha(packet['audio'])==packet['audioSha256']
   with wave.open(packet['audio'],'rb') as audio:
    assert (audio.getnchannels(),audio.getframerate(),audio.getsampwidth())==(1,16000,2);frames=audio.getnframes()
    spans=[(0,frames)] if a.phase=='probe' else [(n,min(n+480000,frames)) for n in range(0,frames,480000)]
    for index,(first,last) in enumerate(spans):
     if pressure.low():raise RuntimeError('ActualWindowsLOWRAM stopwithrawresults')
     audio.setpos(first);pcm=audio.readframes(last-first);value=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768;assert len(value)==last-first
     tick=time.perf_counter();exactzero=not np.any(value)
     if exactzero:text='';tokens=[];timestamps=[]
     else:
      stream=recognizer.create_stream();stream.accept_waveform(16000,value);recognizer.decode_stream(stream);result=stream.result;text=result.text;tokens=list(result.tokens);timestamps=list(result.timestamps)
     row={'id':packet.get('id',packet.get('meeting')),'index':index,'sourceAudioSha256':packet['audioSha256'],'startSample':first,'endSample':last,'text':text,'tokens':tokens,'timestampsRaw':timestamps,'nativeDecoderEOSOrLimitReasonObservable':False,'exactDigitalSilence':exactzero,'seconds':time.perf_counter()-tick,'loop':repeated_block(tokens),'sourceSha256':sha(__file__),'runProtocolSha256':sha(C/'run-protocol.json'),'modelReadySha256':P['modelReadySha256']}
     target=out/(row['id']+'-%04d.json'%index);atomic_json(target,row);state['results'].append({'file':str(target),'sha256':sha(target),'index':index,'sourceFrames':last-first,'seconds':row['seconds']});state['newNeuralCalls']+=not exactzero;state.update(state='RUNNING',activeInput=row['id'],completedWindows=len(state['results']));save();print(json.dumps({'id':row['id'],'index':index,'seconds':row['seconds'],'text':text},ensure_ascii=False),flush=True)
     if row['loop']:raise RuntimeError('Repeated20copy nativeoutput retained; no trimming orretuning')
  state.update(state='COMPLETE_FROZEN_FIRERED2_CPU_UNQUALIFIED',allOriginalSamplesCoveredOnce=True,finishedAt=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'));save()
 except BaseException as exc:state.update(state='FAILED',failureType=type(exc).__name__,reason=str(exc));save();raise
if __name__=='__main__':main()
