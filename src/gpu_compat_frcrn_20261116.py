"""Bounded GPU compatibility isolation after an unexpected system restart.

One alternative backend, fixed2s/6s public prefixes, no accuracy/model search.
Parent watchdog acts only on its created PID family. No global driver changes.
"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import argparse
import gc
import hashlib
import json
import os
import subprocess
import sys
import time
import wave

os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from meeting_acoustic_worker_20261116 import own_limits,available_ram,present_discrete_gpu,exclusive_run
from meeting_acoustic_contract_20261116 import read,require,sha,select_gpu
from practical_io_20261107 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file
from moss_windows_resource_limits_20261104 import SystemRamPressure

now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=ROOT/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
GPU_PY=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe')

def child(run,limits,full_clip=False):
    P=read(J/'frcrn-front-end-r1/protocol-r2.json')
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen frontend dependency changed')
    cases=read(P['audioOnly']);case=next(c for c in cases if c['id']=='20200709_L_R002S01C01-seq-000')
    require(sha(case['audio'])==case['audioSha256'],'Public diagnostic audio changed')
    require(sha(P['enhancer']['file'])==P['enhancer']['sha256'],'Enhancer weights changed')
    predecessor=None
    if full_clip:
        prior=run.parent/'bounded-native-conv-r1/completed.json'
        predecessor=read(prior)
        require(predecessor['state']=='PASS_BOUNDED2S6S_GPU_NATIVE_CONV_COMPATIBILITY_ONLY'
            and [r['seconds'] for r in predecessor['results']]==[2,6]
            and predecessor['workerSha256']=='00efb947d59658fd4627e33f58adccc0a49fd41823a4aef59bd45ca41d5d3c77'
            and predecessor['originalProtocolSha256']==sha(J/'frcrn-front-end-r1/protocol-r2.json'),
            'Completed bounded2s/6s same-model GPU evidence is required')
    input_frames=[case['frames']] if full_clip else [32000,96000]
    state={'state':'PREPARING_BOUNDED_NO_MIOPEN_GPU_CHECK','at':now(),'pid':os.getpid(),
        'trainingUpdates':0,'newNeuralCalls':0,'qualityQualified':False,'saleQualified':False,
        'backend':'GPU native convolution with PyTorch cudnn_enabled=False; no MIOpen convolution selection',
        'fixedInputFrames':input_frames,'fullOriginalClip':full_clip,
        'predecessorProofSha256':sha(prior) if full_clip else None,
        'allocatorFraction':0.25,'allocatorIsNotWholeGpuPowerOrDriverCap':True,
        'workerSha256':sha(__file__),'originalProtocolSha256':sha(J/'frcrn-front-end-r1/protocol-r2.json'),
        'currentOperationBudgetSeconds':120,'referencesRead':False}
    pressure=SystemRamPressure()
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query());atomic_json(run/'state.json',state,progress=True)
    def stop():
        require(not pressure.low() and available_ram()>=P['minimumAvailableBytes'],'Original system RAM protection')
        require(not(run/'stop.request').exists(),'Owned stop requested')
    def memory():
        free,total=torch.cuda.mem_get_info()
        return {'allocatedBytes':torch.cuda.memory_allocated(),'reservedBytes':torch.cuda.memory_reserved(),
            'peakAllocatedBytes':torch.cuda.max_memory_allocated(),'peakReservedBytes':torch.cuda.max_memory_reserved(),
            'driverFreeBytes':free,'driverTotalBytes':total,'systemAvailableBytes':available_ram()}
    with exclusive_run(run),exclusive_file(Path(P['neuralLock'])):
        try:
            save();present_discrete_gpu();began=time.monotonic()
            while time.monotonic()-began<60:stop();time.sleep(1)
            import torch
            import numpy as np
            require(torch.__version__==P['runtime']['torch'] and torch.version.hip,'Frozen AMD runtime differs')
            torch.set_num_threads(4);torch.set_num_interop_threads(1)
            devices=[]
            for i in range(torch.cuda.device_count()):
                p=torch.cuda.get_device_properties(i);devices.append({'index':i,'name':p.name,'architecture':p.gcnArchName})
            chosen=select_gpu(devices);torch.cuda.set_device(chosen['index']);device='cuda:'+str(chosen['index'])
            torch.cuda.set_per_process_memory_fraction(.25,chosen['index'])
            torch.backends.cudnn.enabled=False;torch.backends.cudnn.benchmark=False
            require(not torch.backends.cudnn.enabled,'Alternative GPU convolution backend not selected')
            from companion_community1_adapter_20261115 import pin_rocm_blas
            pin_rocm_blas(P['blas']['file'],P['blas']['sha256'])
            require(memory()['driverFreeBytes']>=8*1024**3,'Less than8GiB driver free before diagnostic; no neural call')
            save(state='LOADING_FROZEN_SMALL_ENHANCER',device=chosen,memory=memory())
            sys.path.insert(0,P['upstreamRoot'])
            import official_functions as author
            author.torch=torch
            from frcrn_se.frcrn import FRCRN_SE_16K
            args=SimpleNamespace(win_len=640,win_inc=320,fft_len=640,win_type='hanning',
                sampling_rate=16000,decode_window=1,one_time_decode_length=120)
            model=FRCRN_SE_16K(args).model
            saved=torch.load(P['enhancer']['file'],map_location='cpu',weights_only=True,mmap=True)
            weights=saved['model'] if 'model' in saved else saved
            if all(k.startswith('module.') for k in weights):weights={k.removeprefix('module.'):v for k,v in weights.items()}
            require(set(model.state_dict())==set(weights),'No partial enhancer loading')
            model.load_state_dict(weights,strict=True);model=model.to(device).eval().requires_grad_(False)
            for k,t in model.state_dict().items():require(torch.equal(t.cpu(),weights[k]),'Weight mismatch '+k)
            del saved,weights;gc.collect()
            require(all(p.device.type=='cuda' and not p.requires_grad for p in model.parameters()),'GPU-only frozen model required')
            # Exact source-selected alternative: use_miopen is gated by cudnn_enabled
            # in PyTorchv2.11 Convolution.cpp. Per-module synchronization logs
            # provide operator timing; no unbounded whole-model profiler trace.
            operations=[];active={};hooks=[]
            log=(run/'operators.jsonl').open('w',encoding='utf-8')
            selected=(torch.nn.Conv1d,torch.nn.Conv2d,torch.nn.ConvTranspose1d,
                torch.nn.ConvTranspose2d,torch.nn.Linear,torch.nn.BatchNorm2d)
            def before(name,module,inputs):
                stop();require(memory()['driverFreeBytes']>=6*1024**3,'Driver free memory below diagnostic margin')
                row={'event':'enter','module':name,'type':type(module).__name__,
                    'inputs':[list(x.shape) for x in inputs if isinstance(x,torch.Tensor)],'memory':memory(),'at':now()}
                log.write(json.dumps(row)+'\n');log.flush();active[name]=time.perf_counter()
                save(state='BOUNDED_GPU_OPERATOR',currentOperation=name,currentOperationBudgetSeconds=30,memory=row['memory'])
            def after(name,module,inputs,output):
                torch.cuda.synchronize();seconds=time.perf_counter()-active.pop(name)
                row={'event':'exit','module':name,'type':type(module).__name__,'seconds':seconds,'memory':memory(),'at':now()}
                log.write(json.dumps(row)+'\n');log.flush();operations.append(row)
                require(seconds<30,'An individual GPU operator exceeded diagnostic budget')
            for name,module in model.named_modules():
                if isinstance(module,selected):
                    hooks.append(module.register_forward_pre_hook(lambda m,x,n=name:before(n,m,x)))
                    hooks.append(module.register_forward_hook(lambda m,x,y,n=name:after(n,m,x,y)))
            results=[]
            for frames in input_frames:
                seconds=frames/16000
                stop();torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
                with wave.open(case['audio'],'rb') as w:raw=w.readframes(frames)
                require(len(raw)==frames*2,'Diagnostic waveform truncated')
                x=np.frombuffer(raw,dtype='<i2').astype(np.float64)/32768;norm,inverse=author.audio_norm(x)
                tensor=torch.from_numpy(norm.astype(np.float32)[None,:]).to(device)
                save(state='RUNNING_FIXED_PREFIX_NO_MIOPEN',currentPrefixSeconds=seconds,currentOperationBudgetSeconds=30,memory=memory())
                tick=time.perf_counter()
                with torch.inference_mode():
                    y=author.decode_one_audio_frcrn_se_16k(model,device,norm[None,:],args) if full_clip else model.inference(tensor)
                torch.cuda.synchronize();elapsed=time.perf_counter()-tick
                if full_clip:
                    require(y.ndim==1 and len(y)>=frames and np.isfinite(y).all(),'Invalid complete enhancer result')
                    output=np.asarray(y[:frames]*inverse,dtype=np.float32)
                    (run/'results').mkdir(exist_ok=True)
                    np.save(run/'results'/(case['id']+'.npy'),output,allow_pickle=False)
                else:
                    require(y.shape==(frames,) and torch.isfinite(y).all(),'Invalid diagnostic enhancer result')
                    output=y.cpu().numpy()
                state['newNeuralCalls']+=1
                results.append({'seconds':seconds,'inferenceSeconds':elapsed,'outputFrames':len(output),
                    'outputSha256':hashlib.sha256(output.tobytes()).hexdigest(),'outputAbsolutePeak':float(np.max(np.abs(output))),
                    'memory':memory(),'weightsUpdated':False,'accuracyScored':False,
                    'originalAudioSha256':case['audioSha256'],'originalAllFramesAndGainRestored':full_clip})
                save(state='FIXED_PREFIX_COMPLETE_NO_QUALITY_CLAIM',results=results,currentOperationBudgetSeconds=30)
                del tensor,y,output,x,norm;gc.collect();torch.cuda.empty_cache();time.sleep(2)
            log.close()
            for h in hooks:h.remove()
            save(state='PASS_ORIGINAL27S_GPU_NATIVE_CONV_COMPATIBILITY_ONLY' if full_clip else 'PASS_BOUNDED2S6S_GPU_NATIVE_CONV_COMPATIBILITY_ONLY',results=results,
                completedOperatorCalls=len(operations),maximumOperatorSeconds=max(r['seconds'] for r in operations),
                currentOperation=None,currentOperationBudgetSeconds=30,
                originalDefaultMiopen27sFailureReproduced=False,originalRestartRootCauseProven=False,
                wholeMeetingOrTrainingStabilityProven=False,systemDriverOrPowerSettingsChanged=False)
            atomic_json(run/'completed.json',state)
        except BaseException as e:
            import traceback
            save(state='FAILED_BOUNDED_GPU_CHECK_RETAIN_NO_RETRY',error=repr(e),traceback=traceback.format_exc());raise
        finally:pressure.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--child',action='store_true');p.add_argument('--full-clip',action='store_true');a=p.parse_args()
    limits=own_limits(25);run=a.run.resolve()
    if a.child:return child(run,limits,a.full_clip)
    run.mkdir(parents=True,exist_ok=False)
    with (run/'stdout.log').open('w',encoding='utf-8') as stream:
        command=[str(GPU_PY),str(Path(__file__).resolve()),'--child','--run',str(run)]+(['--full-clip'] if a.full_clip else [])
        proc=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        import psutil
        owned=psutil.Process(proc.pid);created=owned.create_time();start=time.monotonic();reason=None
        atomic_json(run/'parent.json',{'pid':os.getpid(),'childPid':proc.pid,'childCreatedAt':created,'at':now(),
            'scope':'Only this created child family; maximum360s overall/30s logged operator. A process watchdog cannot guarantee GPU-driver recovery.'})
        while proc.poll() is None:
            time.sleep(.5)
            state=read(run/'state.json') if (run/'state.json').exists() else None
            if time.monotonic()-start>360:reason='Overall360s diagnostic budget'
            if state:
                age=time.time()-datetime.fromisoformat(state['observedAt']).timestamp()
                if age>state['currentOperationBudgetSeconds']+2:reason='No GPU operation progress within bounded budget'
            if reason:
                require(abs(owned.create_time()-created)<.01,'PID identity changed; do not stop')
                children=owned.children(recursive=True)
                for c in reversed(children):
                    try:c.kill()
                    except psutil.NoSuchProcess:pass
                try:owned.kill()
                except psutil.NoSuchProcess:pass
                break
        code=proc.wait(timeout=15)
    result={'state':'BOUNDED_GPU_CHECK_RETURNED' if code==0 else 'BOUNDED_GPU_CHECK_FAILED_NO_AUTOMATIC_RETRY',
        'at':now(),'exitCode':code,'watchdogReason':reason,'childPid':proc.pid,'childCreatedAt':created,
        'run':str(run),'newTrainingUpdates':0,'driverOrSystemSettingsChanged':False}
    atomic_json(run/'parent-completed.json',result);print(json.dumps(result));sys.exit(0 if code==0 else 1)

if __name__=='__main__':main()
