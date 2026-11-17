"""One fixed WebRTC DSP VAD run on original full English sources; no neural runtime."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,math,sys,time,wave
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from meeting_acoustic_contract_20261116 import read,sha,require
from durable_model_state_20261117 import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    P=read(a.protocol);limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen DSP dependency changed')
    require(P['mode']==0 and P['frameSamples']==160 and P['sampleRate']==16000,'Fixed least-aggressive10ms profile')
    a.run.mkdir(parents=True,exist_ok=False);pressure=SystemRamPressure()
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),'assetReceiptSha256':sha(P['assetReceipt'])}
    state={'at':datetime.now().astimezone().isoformat(),'state':'PREPARING_WEBRTC_DSP_ONLY','binding':binding,
        'completed':[],'newNeuralCalls':0,'parameterUpdates':0,'gpuInitialized':False,'referencesRead':False,'processedDspFrames':0}
    def save(**values):
        state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
        atomic_json(a.run/'state.json',state,progress=True)
    def stop():
        require(not pressure.low(),'Windows low-memory protection')
        from psutil import virtual_memory
        require(virtual_memory().available>=P['minimumAvailableBytes'],'Original RAM floor')
        require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Bounded DSP cutoff')
        require(not(a.run/'stop.request').exists(),'Owned DSP stop')
    try:
        save();stop();asset=read(P['assetReceipt'])
        for item in asset['packageFiles']:require(sha(item['file'])==item['sha256'],'Pinned WebRTC file changed')
        sys.path.insert(0,asset['localImportRoot']);import webrtcvad
        require(webrtcvad.__version__==asset['version'],'Pinned DSP wheel version differs')
        require(not any(n in sys.modules for n in ['torch','onnxruntime','transcribe_cpp']),'Unexpected neural runtime import')
        require(webrtcvad.valid_rate_and_frame_length(16000,160),'Invalid native DSP geometry')
        silence=webrtcvad.Vad(0)
        require(all(not silence.is_speech(bytes(320),16000) for _ in range(200)),'DSP emits speech on2s digital zero')
        atomic_json(a.run/'silence-control.json',{'frames':32000,'dspWindows':200,'segments':[],'newNeuralCalls':0})
        cases=[r for r in read(P['audioOnly']) if r['meeting'] in P['meetings']]
        require([r['meeting'] for r in cases]==P['meetings'],'Original source order differs')
        for case in cases:
            stop();require(sha(case['audio'])==case['audioSha256'],'Original PCM changed')
            detector=webrtcvad.Vad(P['mode']);tick=time.perf_counter();segments=[];opened=None;submitted=0;windows=0
            with wave.open(case['audio'],'rb') as source:
                require((source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes())
                    ==(1,2,16000,case['frames']),'Original waveform geometry changed')
                while submitted<case['frames']:
                    raw=source.readframes(160);count=len(raw)//2;require(0<count<=160,'Unexpected source read')
                    active=detector.is_speech(raw+bytes((160-count)*2),16000)
                    if active and opened is None:opened=submitted
                    if not active and opened is not None:
                        segments.append({'start':opened,'end':submitted});opened=None
                    submitted+=count;windows+=1;state['processedDspFrames']+=1
                    if windows%1000==0:stop();save(state='WEBRTC_DSP_FULL_SOURCE',currentMeeting=case['meeting'],submittedFrames=submitted)
                if opened is not None:segments.append({'start':opened,'end':submitted})
            require(submitted==case['frames'] and windows==math.ceil(case['frames']/160),'Incomplete source coverage')
            require(all(0<=r['start']<r['end']<=submitted for r in segments),'Invalid raw DSP intervals')
            packet={'state':'COMPLETE_FIXED_WEBRTC_DSP_FULL_SOURCE','meeting':case['meeting'],'binding':binding,
                'frames':case['frames'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
                'segmentsInOriginalSamples':segments,'allOriginalFramesCovered':True,'dspWindows':windows,
                'tailZeroPaddingSamples':(-submitted)%160,'seconds':time.perf_counter()-tick,'mode':0,
                'oneContinuousDspState':True,'extraPaddingOrSmoothing':False,'referencesRead':False,
                'speakerIdentitiesProduced':False,'newNeuralCalls':0,'parameterUpdates':0}
            path=a.run/(case['meeting']+'-presence.json');atomic_json(path,packet)
            state['completed'].append({'meeting':case['meeting'],'file':str(path),'sha256':sha(path)})
            save(currentMeeting=None)
        save(state='COMPLETE_TWO_CPU_VAD_FULL_SOURCES_PENDING_COMPOSITION')
        atomic_json(a.run/'completed.json',state)
    except BaseException as error:save(state='FAILED_WEBRTC_DSP_RETAINED_NO_RETRY',error=repr(error));raise
    finally:pressure.close()
    print(json.dumps({k:state[k] for k in ['state','completed','processedDspFrames','newNeuralCalls','parameterUpdates','limits']},ensure_ascii=False))

if __name__=='__main__':main()
