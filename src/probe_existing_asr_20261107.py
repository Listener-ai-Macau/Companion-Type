"""Check the existing offline ASR's actual timing fields, not a new model sweep."""
from pathlib import Path
import hashlib,json,os,psutil,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5);psutil.Process().cpu_affinity([12,13]);pressure=SystemRamPressure()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-cpu-r1');target=C/'asr-smoke.json';assert not target.exists()
tick=time.perf_counter();state={'state':'PREPARING_EXISTING_SENSEVOICE_CONTROL','newAsrAccuracyEvidence':False,'referenceOpened':False}
try:
    if pressure.low():raise RuntimeError('Actual Windows low RAM before model import')
    import sherpa_onnx,numpy as np
    model=Path(os.environ['APPDATA'])/'Companion Type/models/local-asr/sherpa-onnx-sense-voice-2024-07-17'
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    audio=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/engine-smoke30s-restored.wav')
    state.update(runtime=sherpa_onnx.__version__,modelFiles={n:{'file':str(model/n),'sha256':sha(model/n)} for n in ['model.int8.onnx','tokens.txt']},audioSha256=sha(audio))
    rec=sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(model/'model.int8.onnx'),tokens=str(model/'tokens.txt'),num_threads=1,provider='cpu',language='zh',use_itn=True)
    with wave.open(str(audio),'rb') as source:
        assert source.getnchannels()==1 and source.getsampwidth()==2 and source.getframerate()==16000
        samples=np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(np.float32)/32768
    if pressure.low():raise RuntimeError('Actual Windows low RAM before decode')
    stream=rec.create_stream();stream.accept_waveform(16000,samples);before=time.perf_counter();rec.decode_stream(stream)
    result=stream.result
    state.update(state='EXISTING_ASR_CONTROL_COMPLETE',audioSeconds=len(samples)/16000,inferenceSeconds=time.perf_counter()-before,text=result.text,tokens=list(result.tokens),timestamps=list(result.timestamps),durations=list(getattr(result,'durations',[])),rawResult=str(result),scope='Public30s compatibility and real output-field inspection only; no reference/quality score, no replacement/default model changed.')
except BaseException as error:
    state.update(state='ASR_CONTROL_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    pressure.close();state.update(wholeSeconds=time.perf_counter()-tick,limits=limits.query());target.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(state,ensure_ascii=False),flush=True)
