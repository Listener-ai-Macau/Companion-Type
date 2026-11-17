"""One CPU-only official Silero default inference, no training or GPU calls."""
from pathlib import Path
from datetime import datetime
import argparse,gc,hashlib,importlib.util,json,math,os,sys,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from meeting_acoustic_contract_20261116 import read,sha,require
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from meeting_acoustic_worker_20261116 import available_ram,exclusive_run
from companion_local_pcm_session_20261114 import exclusive_file
from durable_model_state_20261117 import atomic_json
from model_thermal_guard_20261117 import ThermalGuard,CpuThermalLimit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);P=read(a.protocol)
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen detector dependency changed')
    blas=P.get('cpuBlas');helper=Path(__file__).with_name('companion_community1_adapter_20261115.py')
    require(isinstance(blas,dict) and set(blas)>={'file','sha256'},'Frozen CPU BLAS binding missing')
    require(any(item['file']==blas['file'] and item['sha256']==blas['sha256'] for item in P['files'])
        and any(Path(item['file']).resolve()==helper.resolve() for item in P['files']),
        'CPU BLAS and explicit thread helper must be frozen inference dependencies')
    require(P['cpuInferenceOnly'] and P['threads']==1 and P['cpuPercent']==5,'Fixed low-CPU inference profile')
    cases=[r for r in read(P['audioOnly']) if r['meeting'] in P['meetings']]
    require([r['meeting'] for r in cases]==P['meetings'],'Original full-source order changed')
    run=a.run.resolve();run.mkdir(parents=True,exist_ok=False)
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),'weightsSha256':sha(P['weights'])}
    state={'state':'PREPARING_CPU_ONLY_SILERO_DEFAULT','at':datetime.now().astimezone().isoformat(),
        'pid':os.getpid(),'binding':binding,'completed':[],'newNeuralCalls':0,'parameterUpdates':0,
        'cpuInferenceOnly':True,'referenceRead':False,'gpuInitialized':False,'qualityQualified':False}
    pressure=SystemRamPressure();thermal=ThermalGuard(P['thermal']);last_save=0.
    def save(**values):
        state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
        atomic_json(run/'state.json',state,progress=True)
    def stop():
        require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'CPU detector cutoff')
        require(not(run/'stop.request').exists(),'Owned detector stop requested')
        require(not pressure.low() and available_ram()>=P['minimumAvailableBytes'],'Original RAM protection')
        try:state['cpuTemperature']=thermal.check()
        except CpuThermalLimit as error:
            state['cpuTemperature']=error.observation;raise
    try:
        with exclusive_run(run),exclusive_file(Path(P['neuralLock'])):
            save();began=time.monotonic()
            while time.monotonic()-began<60:stop();time.sleep(1)
            thermal.check(starting=True);save(state='LOADING_OFFICIAL_CPU_SILERO_JIT')
            import torch
            # Windows ROCm's separate CPU BLAS ignores the environment/thread
            # caps above. Reuse the existing exact-DLL one-thread binding;
            # otherwise the declared single-thread inference profile is false.
            from companion_community1_adapter_20261115 import pin_rocm_blas
            state['cpuBlasThreadPin']=pin_rocm_blas(blas['file'],blas['sha256'])
            import numpy as np
            require(torch.__version__==P['torch'],'Frozen CPU inference runtime changed')
            torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
            spec=importlib.util.spec_from_file_location('companion_pinned_silero_utils',P['upstreamUtils'])
            utility=importlib.util.module_from_spec(spec);spec.loader.exec_module(utility)
            model=utility.init_jit_model(P['weights'],device=torch.device('cpu'))
            for parameter in model.parameters():parameter.requires_grad_(False)
            require(all(t.device.type=='cpu' for t in list(model.parameters())+list(model.buffers())),
                'Detector tensors are not CPU-only')
            def parameters_digest():
                digest=hashlib.sha256()
                for name,value in model.named_parameters():
                    digest.update(name.encode()+b'\0');digest.update(value.detach().contiguous().numpy().tobytes())
                return digest.hexdigest()
            before=parameters_digest();counts={}
            def detect(samples,identity):
                nonlocal last_save
                calls=0;tick=time.perf_counter()
                def progress(percent):
                    nonlocal calls,last_save
                    calls+=1;state['newNeuralCalls']+=1;stop()
                    if time.monotonic()-last_save>=1:
                        save(state='DETECTING_CPU_ONLY_SILERO_DEFAULT',currentId=identity,
                            currentProgressPercent=percent,currentCompletedWindows=calls)
                        last_save=time.monotonic()
                segments=utility.get_speech_timestamps(samples,model,sampling_rate=16000,
                    return_seconds=False,progress_tracking_callback=progress)
                require(calls==math.ceil(samples.numel()/512),'Detector did not cover all original windows')
                require(all(type(r['start']) is int and type(r['end']) is int
                    and 0<=r['start']<r['end']<=samples.numel() for r in segments),'Invalid detector sample times')
                require(all(left['end']<=right['start'] for left,right in zip(segments,segments[1:])),'Overlapping presence intervals')
                return segments,calls,time.perf_counter()-tick
            silence=torch.zeros(32000,dtype=torch.float32)
            segments,calls,seconds=detect(silence,'two-second-digital-zero-control')
            require(not segments,'Official default detector emits speech on digital zero control')
            atomic_json(run/'silence-control.json',{'frames':32000,'segments':segments,'modelCalls':calls,'seconds':seconds})
            del silence
            for case in cases:
                stop();require(sha(case['audio'])==case['audioSha256'],'Original public source changed')
                with wave.open(case['audio'],'rb') as stream:
                    require((stream.getnchannels(),stream.getsampwidth(),stream.getframerate(),stream.getnframes())
                        ==(1,2,16000,case['frames']),'Original PCM format/frames differ')
                    raw=stream.readframes(stream.getnframes())
                samples=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768;del raw
                audio=torch.from_numpy(samples)
                segments,calls,seconds=detect(audio,case['meeting'])
                packet={'state':'COMPLETE_OFFICIAL_DEFAULT_CPU_VAD_FULL_SOURCE','meeting':case['meeting'],
                    'binding':binding,'audioSha256':case['audioSha256'],'frames':case['frames'],
                    'audioSeconds':case['audioSeconds'],'segmentsInOriginalSamples':segments,
                    'modelCalls':calls,'seconds':seconds,'allOriginalFramesCovered':True,
                    'tailZeroPaddingSamples':(-case['frames'])%512,'defaultSegmentationParametersUnchanged':True,
                    'referencesRead':False,'speakerIdentitiesProduced':False,'parameterUpdates':0}
                path=run/(case['meeting']+'-presence.json');atomic_json(path,packet)
                state['completed'].append({'meeting':case['meeting'],'file':str(path),'sha256':sha(path)})
                del audio,samples;gc.collect();save(currentId=None)
            require(parameters_digest()==before,'Fixed detector weights changed')
            require(not torch.cuda.is_initialized(),'CPU detector initialized GPU context')
            save(state='COMPLETE_TWO_CPU_VAD_FULL_SOURCES_PENDING_COMPOSITION',parameterDigest=before,gpuInitialized=False)
            atomic_json(run/'completed.json',state)
    except BaseException as error:
        save(state='FAILED_CPU_VAD_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
    finally:pressure.close()

if __name__=='__main__':main()
