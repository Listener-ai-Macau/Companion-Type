"""Official native8-speaker model via its stable C ABI; no Torch/HIP or references.

Read raw10ms probabilities every input push, before native20min compaction.
This avoids the CLI's old4-speaker callhome segment filter on the prefix.
Use one frozen0.5 frame threshold with no duration/pad tuning throughout.
"""
from pathlib import Path
from datetime import datetime
import argparse,ctypes as ct,hashlib,json,math,os,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json

class ModelConfig(ct.Structure):
    _fields_=[('size',ct.c_size_t),('model_path',ct.c_char_p),('gpu',ct.c_int32),('preset',ct.c_char_p),('chunk_frames',ct.c_int32),('right_context_frames',ct.c_int32),('left_context_frames',ct.c_int32),('fifo_frames',ct.c_int32),('spkcache_frames',ct.c_int32),('update_period_frames',ct.c_int32)]

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def probability_segments(array,frames,seconds_per_frame,audio_seconds,threshold):
    import numpy as np
    rows=[]
    for speaker in range(array.shape[1]):
        values=array[:frames,speaker];last=np.maximum.accumulate(np.where(values!=threshold,np.arange(frames),-1));active=(last>=0)&(values[np.maximum(last,0)]>threshold)
        edges=np.diff(np.r_[0,active,0].astype(np.int8));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
        for start,end in zip(starts,ends):
            a,b=float(start*seconds_per_frame),min(float(end*seconds_per_frame),audio_seconds)
            if 0<=a<b:rows.append({'start':a,'end':b,'speaker':speaker})
    return sorted(rows,key=lambda row:(row['start'],row['end'],row['speaker']))

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--index',required=True,type=int);args=p.parse_args();C=Path(args.control).resolve()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));P=read(C/'protocol.json');case=read(C/'audio-only.json')[args.index];assert not any('reference' in k.lower() for k in case)
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);out=C/'results'/case['meeting'];out.mkdir(parents=True,exist_ok=False);cache=Path(P['probabilityCacheRoot'])/case['meeting'];cache.mkdir(parents=True,exist_ok=False)
    now=lambda:datetime.now().astimezone().isoformat(timespec='seconds');tick=time.perf_counter();state={'state':'LOADING_NATIVE8_CPU','pid':os.getpid(),'startedAt':now(),'audioSha256':case['audioSha256'],'referencePassedToWorker':False,'gpuUsed':False,'automaticRetries':0,'sourceSha256':sha(__file__),'nativeGeometry':P['preset'],'newNeuralPushes':0,'completedNeuralFrames':0};model=ct.c_void_p();stream=ct.c_void_p();lib=None;directory_cookie=None
    def save(progress=False):
        state['limits']=limits.query();atomic_json(out/'state.json',state,progress=progress)
    def checkpoint(array,frames,sample):
        array.flush()
        with Path(array.filename).open('r+b') as file:os.fsync(file.fileno())
        digest=hashlib.sha256(memoryview(array[:frames]).cast('B') if frames else b'').hexdigest()
        atomic_json(cache/'probabilities.json',{'audioSha256':case['audioSha256'],'modelSha256':P['modelSha256'],'protocolSha256':sha(C/'protocol.json'),'nativeLibrarySha256':P['nativeLibrarySha256'],'shape':list(array.shape),'dtype':str(array.dtype),'committedFrames':frames,'submittedSample':sample,'committedPrefixSha256':digest,'stateContinuity':'One continuous native AOSC stream; no reset between chunks. Probabilities alone are not a restorable speaker cache.','neuralStateExported':False})
    save()
    try:
        assert sha(case['audio'])==case['audioSha256'] and sha(P['model'])==P['modelSha256'] and sha(P['nativeLibrary'])==P['nativeLibrarySha256']
        assert all(sha(Path(P['nativeLibrary']).parent/name)==digest for name,digest in P['nativeFiles'].items())
        assert P['preset']=='v3-offline' and P['probabilityThreshold']==.5 and P['postProcessing']=='uniform_frame_threshold_no_pad_no_duration_filter'
        folder=Path(P['nativeLibrary']).parent;directory_cookie=os.add_dll_directory(str(folder));os.chdir(folder)
        lib=ct.CDLL(P['nativeLibrary']);void=ct.c_void_p;fptr=ct.POINTER(ct.c_float)
        signatures={'nemo_speech_asr_last_error':([],ct.c_char_p),'nemo_speech_diar_create':([ct.POINTER(ModelConfig),ct.POINTER(void)],ct.c_int),'nemo_speech_diar_destroy':([void],None),'nemo_speech_diar_stream_open':([void,ct.POINTER(void)],ct.c_int),'nemo_speech_diar_stream_push_f32':([void,fptr,ct.c_size_t,ct.c_int32],ct.c_int),'nemo_speech_diar_stream_finish':([void],ct.c_int),'nemo_speech_diar_stream_close':([void],None),'nemo_speech_diar_num_speakers':([void],ct.c_int32),'nemo_speech_diar_seconds_per_frame':([void],ct.c_double),'nemo_speech_diar_frame_count':([void],ct.c_int64),'nemo_speech_diar_frame_probs_start':([void],ct.c_int64),'nemo_speech_diar_frame_probs':([void,fptr,ct.c_size_t],ct.c_int)}
        for name,(params,result) in signatures.items():fn=getattr(lib,name);fn.argtypes=params;fn.restype=result
        def check(code):
            if code:raise RuntimeError('Native status '+str(code)+': '+(lib.nemo_speech_asr_last_error() or b'').decode('utf8',errors='replace'))
        config=ModelConfig(size=ct.sizeof(ModelConfig),model_path=P['model'].encode('utf8'),gpu=-1,preset=P['preset'].encode('ascii'),left_context_frames=0)
        check(lib.nemo_speech_diar_create(ct.byref(config),ct.byref(model)));speakers=lib.nemo_speech_diar_num_speakers(model);cadence=lib.nemo_speech_diar_seconds_per_frame(model);assert speakers==8 and abs(cadence-.01)<1e-8
        check(lib.nemo_speech_diar_stream_open(model,ct.byref(stream)))
        import numpy as np
        with wave.open(case['audio'],'rb') as source:
            assert source.getnchannels()==1 and source.getsampwidth()==2 and source.getframerate()==16000;count=source.getnframes();assert abs(count/16000-case['audioSeconds'])<1/16000
            capacity=math.ceil(count/(16000*cadence))+1024;array=np.lib.format.open_memmap(cache/'probabilities.npy',mode='w+',dtype=np.float32,shape=(capacity,speakers));done=0;submitted=0
            def collect():
                nonlocal done
                frames=lib.nemo_speech_diar_frame_count(stream);start=lib.nemo_speech_diar_frame_probs_start(stream);assert 0<=start<=done<=frames<=capacity,'Native probability gap or unexpected frame bounds'
                if frames>start:
                    data=np.empty((frames-start,speakers),dtype=np.float32);check(lib.nemo_speech_diar_frame_probs(stream,data.ctypes.data_as(fptr),data.size));assert np.isfinite(data).all() and data.min()>=0 and data.max()<=1
                    assert np.array_equal(array[start:done],data[:done-start]),'Native revised a previously committed chunk; refuse a false stable-prefix claim'
                    array[start:frames]=data
                done=frames;checkpoint(array,done,submitted);state.update(state='NATIVE8_STREAMING_FULL_AUDIO',completedNeuralFrames=done,submittedSamples=submitted,totalAudioSamples=count,nativeFrameProbabilitiesStart=start,nativeOutputSpeakers=speakers,nativeSecondsPerFrame=cadence);save(True)
            block=P['inputPushSamples'];assert block==486400
            while submitted<count:
                if (C/'stop.request').exists():raise InterruptedError('Explicit stop requested; probabilities and original audio retained')
                data=np.frombuffer(source.readframes(min(block,count-submitted)),dtype='<i2').astype(np.float32)/32768.;assert len(data)>0
                check(lib.nemo_speech_diar_stream_push_f32(stream,data.ctypes.data_as(fptr),len(data),16000));submitted+=len(data);state['newNeuralPushes']+=1;collect()
            check(lib.nemo_speech_diar_stream_finish(stream));collect();assert submitted==count and done>=math.floor(case['audioSeconds']/cadence)
        rows=probability_segments(array,done,cadence,case['audioSeconds'],P['probabilityThreshold']);assert rows
        atomic_json(out/'speaker-journal.json',{'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'segments':rows,'scope':'Official native Q8 eight-channel activity; one continuous cached stream, uniform0.5 frame threshold. Anonymous IDs only, not separated words or real names/roles. No reference input.'})
        rttm=out/'predicted.rttm';rttm.write_text(''.join(f"SPEAKER {case['meeting']} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> speaker_{r['speaker']} <NA> <NA>\n" for r in rows),encoding='utf8')
        state.update(state='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED',meeting=case['meeting'],audioSeconds=case['audioSeconds'],predictedSpeakers=len({r['speaker'] for r in rows}),segments=len(rows),rttmSha256=sha(rttm),allOriginalAudioSamplesSubmitted=True,oneContinuousSpeakerState=True,probabilityManifestSha256=sha(cache/'probabilities.json'))
    except BaseException as error:
        state.update(state='FAILED_NATIVE8_PARTIAL_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        if lib is not None:
            if stream.value:lib.nemo_speech_diar_stream_close(stream)
            if model.value:lib.nemo_speech_diar_destroy(model)
        if directory_cookie is not None:directory_cookie.close()
        state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-tick);save();atomic_json(out/'completed-state.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
