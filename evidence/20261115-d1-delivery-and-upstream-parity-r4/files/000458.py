"""One bounded, model-free isolated-dGPU arithmetic probe; no DLL patches."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ctypes, hashlib, json, os, psutil, subprocess, sys, time
from ctypes import wintypes as w
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
C = R / 'docs/handoffs/20261107-model-generation-recovery'
PY = 'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
if sys.argv[-1:] == ['--child']:
    limits = WorkerLimits(cpu_percent=5)
    psutil.Process().cpu_affinity([14, 15])
    state = {'at': now(), 'state': 'IMPORTING_TORCH_ONLY', 'pid': os.getpid(), 'limits': limits.query(), 'hipVisibleDevices': os.environ.get('HIP_VISIBLE_DEVICES'), 'modelLoaded': False}
    target = C / 'single-visible-gpu-worker.json'
    def save():
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(state, indent=2) + '\n', encoding='utf8')
        os.replace(temp, target)
    save()
    import torch
    torch.set_num_threads(2)
    assert torch.version.hip and torch.cuda.device_count() == 1, 'Only the declared external GPU may be visible'
    info = torch.cuda.get_device_properties(0)
    assert 'RX 6800 XT' in info.name and info.gcnArchName.startswith('gfx1030'), 'Wrong visible GPU; refuse integrated fallback'
    torch.cuda.set_device(0)
    expected = [[sum((i * 4 + k + 1) * (k * 4 + j + 1) for k in range(4)) for j in range(4)] for i in range(4)]
    state.update(state='CHECKING_NONZERO_ARITHMETIC', actualGpu=info.name, architecture=info.gcnArchName, visibleGpuIndex=0, visibleDeviceCount=1, torchVersion=torch.__version__)
    save()
    value = torch.arange(1, 17, device='cuda:0', dtype=torch.float32).reshape(4, 4)
    for _ in range(8):
        actual = (value @ value).cpu().tolist()
        assert actual == expected and any(n != 0 for row in actual for n in row), 'Incorrect GPU arithmetic'
        time.sleep(.025)
    bf16 = value.to(torch.bfloat16)
    assert torch.equal((bf16 @ bf16).cpu(), torch.tensor(expected, dtype=torch.bfloat16))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]; kernel.GetModuleHandleW.restype = w.HMODULE
    kernel.GetModuleFileNameW.argtypes = [w.HMODULE, w.LPWSTR, w.DWORD]; kernel.GetModuleFileNameW.restype = w.DWORD
    module = kernel.GetModuleHandleW('amdhip64_7.dll'); assert module
    path = ctypes.create_unicode_buffer(32768)
    assert kernel.GetModuleFileNameW(module, path, len(path))
    dll = Path(path.value)
    expected_dll = Path(PY).parents[1] / 'Lib/site-packages/_rocm_sdk_core/bin/amdhip64_7.dll'
    assert dll.resolve() == expected_dll.resolve(), 'Unexpected HIP runtime DLL loaded'
    with dll.open('rb') as stream: checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    state.update(state='PASS_SINGLE_VISIBLE_RX6800XT_NATIVE_ARITHMETIC_ONLY', finishedAt=now(), fp32ExactNonzeroMatmul=True, bf16RoundedReferenceEqual=True, loadedHipDll=str(dll), loadedHipDllSha256=checksum, dllPatched=False, limits=limits.query(), fullModelStabilityProven=False)
    save()
    print(json.dumps(state), flush=True)
else:
    C.mkdir(exist_ok=False)
    pressure = SystemRamPressure()
    state = {'at': now(), 'state': 'PREFLIGHT', 'modelLoaded': False, 'automaticRetries': 0}
    if pressure.low():
        state['state'] = 'DEFERRED_ACTUAL_WINDOWS_LOW_SYSTEM_RAM_BEFORE_WORKER'
    else:
        env = {k: v for k, v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES', 'ROCR_VISIBLE_DEVICES', 'GPU_DEVICE_ORDINAL', 'PYTHONPATH'] and not k.startswith(('OPENAI_', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN', 'COMPANION_'))}
        env.update(HIP_VISIBLE_DEVICES='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        tick = time.perf_counter()
        with (C / 'single-visible-gpu.log').open('xb') as log:
            child = subprocess.Popen([PY, str(Path(__file__)), '--child'], env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            process = psutil.Process(child.pid)
            peak = 0
            while child.poll() is None:
                stop = pressure.low() or time.perf_counter() - tick > 90
                if stop:
                    try: owned = [process] + process.children(recursive=True)
                    except psutil.NoSuchProcess: owned = []
                    for member in reversed(owned):
                        try: member.terminate()
                        except psutil.NoSuchProcess: pass
                    psutil.wait_procs(owned, timeout=3)
                    child.wait(timeout=5)
                    state['state'] = 'STOPPED_OWN_PROBE_LOW_RAM_OR_DEADLINE'
                    break
                try: peak = max(peak, sum(member.memory_info().private for member in [process] + process.children(recursive=True)))
                except psutil.NoSuchProcess: pass
                time.sleep(.25)
        state.update(exitCode=child.returncode, seconds=time.perf_counter() - tick, observedProcessFamilyPrivatePeakBytes=peak)
        if state['state'] == 'PREFLIGHT':
            state['state'] = 'PASS_MODEL_FREE_SINGLE_GPU_VISIBILITY_AND_ARITHMETIC' if child.returncode == 0 else 'NATIVE_PROBE_FAILED_NO_AUTOMATIC_RETRY'
    pressure.close()
    state.update(finishedAt=now(), noModelInferenceRun=True, systemDriverChanged=False, dllPatched=False, limitation='A successful small kernel probe does not establish hours-long model stability or a fixed crash root cause.')
    (C / 'single-visible-gpu-result.json').write_text(json.dumps(state, indent=2) + '\n', encoding='utf8')
    print(json.dumps(state), flush=True)
