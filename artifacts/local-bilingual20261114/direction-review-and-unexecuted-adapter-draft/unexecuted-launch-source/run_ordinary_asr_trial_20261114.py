from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import psutil

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
C = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/ordinary-asr-adaptation-r1'
RUN = Path('E:/CodexData/Companion/.model-cache/ordinary-asr-adaptation-20261114/run-r1')
sys.path.insert(0, str(SRC))
from practical_io_20261107 import atomic_json, stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
from run_paired_fixed_asr_20261109 import resume_resources
from companion_local_pcm_session_20261114 import exclusive_file
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')
inventory = C / 'hip-current/hip-inventory.json'
device = read(inventory)
assert device['state'] == 'PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
assert 0 <= (datetime.now().astimezone()-datetime.fromisoformat(device['finishedAt'])).total_seconds() < 1800
assert device['selected']['name'] == 'AMD Radeon RX 6800 XT' and device['selected']['architecture'] == 'gfx1030'
assert not RUN.exists()
names = {'ordinary_asr_adapter_worker_20261114.py', 'companion_local_qwen_worker_20261114.py',
         'practical_alignment_session_worker_20261114.py', 'practical_qwen_boundaries_worker_20261107.py',
         'run_paired_fixed_asr_20261109.py'}
for process in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(arg).name in names for arg in process.info['cmdline'] or []), 'Another model stage is active'
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
worker = SRC / 'ordinary_asr_adapter_worker_20261114.py'
helpers = [SRC / name for name in ['companion_local_qwen_worker_20261114.py', 'companion_local_pcm_session_20261114.py',
                                   'practical_qwen_streamed_loader_20261107.py', 'moss_streamed_weights_20261104.py',
                                   'practical_qwen_bounded_decode_20261107.py']]
runtime = Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/transformers/models/qwen3_asr')
helpers += [runtime / 'processing_qwen3_asr.py', runtime / 'modeling_qwen3_asr.py']
binding = {'workerSha256': sha(worker), 'protocolSha256': sha(C / 'protocol.json'),
           'capabilityControlManifestSha256': sha(C / 'capability-controls-audio-only.json'),
           'helpers': {str(p): sha(p) for p in helpers}}
assert not (C / 'worker-binding.json').exists()
atomic_json(C / 'worker-binding.json', binding)
RUN.mkdir()
resources = resume_resources(Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-r2-runs/near-N_SPK8015/task.json'))
state = {'state': 'PREPARING_ONE_BOUNDED_ASR_ADAPTER_TRIAL', 'startedAt': now(), 'pid': os.getpid(),
         'run': str(RUN), 'currentGpu': device['selected'], 'resources': resources,
         'automaticRetries': 0, 'qualityQualified': False, 'trainingDataNotEval': True}
target = C / 'trial-run.json'
assert not target.exists()
atomic_json(target, state)
if not resources['ready']:
    state.update(state='DEFERRED_UNCHANGED_WINDOWS_RAM_GATE', finishedAt=now())
    atomic_json(target, state)
    raise SystemExit(2)
env = {k: v for k, v in os.environ.items() if k not in {'CUDA_VISIBLE_DEVICES', 'ROCR_VISIBLE_DEVICES', 'HIP_VISIBLE_DEVICES', 'GPU_DEVICE_ORDINAL', 'PYTHONPATH'}}
env.update(HIP_VISIBLE_DEVICES=str(device['selected']['ordinal']), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
           HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
python = 'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
child = owned = None
pressure = SystemRamPressure()
began = time.perf_counter()
peak = 0
try:
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
        assert not pressure.low()
        with (C / 'trial-worker.log').open('xb') as log:
            child = subprocess.Popen([python, str(worker), '--control', str(C), '--inventory', str(inventory), '--run', str(RUN)],
                                     env=env, stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned = psutil.Process(child.pid)
            state.update(state='RUNNING_ONE_BOUNDED_ASR_ADAPTER_TRIAL', workerPid=child.pid)
            atomic_json(target, state)
            last_progress = None
            progress_at = next_sample = time.perf_counter()
            while child.poll() is None:
                low = pressure.low()
                if low or (C / 'stop.request').exists() or time.perf_counter()-progress_at > 600 or time.perf_counter()-began > 3600:
                    reason = 'actual_windows_low_ram' if low else 'explicit_stop_or_bounded_deadline'
                    (RUN / 'stop.request').write_text(reason, encoding='ascii')
                    state.update(stopReason=reason, availableBytesAtStop=psutil.virtual_memory().available)
                    stop_owned_family(child, owned)
                    break
                try:
                    private = sum(p.memory_info().private for p in [owned] + owned.children(recursive=True))
                    peak = max(peak, private)
                    progress = read(RUN / 'trial-state.json') if (RUN / 'trial-state.json').exists() else {}
                    point = (progress.get('state'), progress.get('generationCalls'), progress.get('trainingSteps'))
                    if point != last_progress:
                        last_progress = point
                        progress_at = time.perf_counter()
                    if time.perf_counter() >= next_sample:
                        with (C / 'trial-resources.jsonl').open('a', encoding='utf-8') as stream:
                            stream.write(json.dumps({'at': now(), 'availableBytes': psutil.virtual_memory().available,
                                                     'privateBytes': private, 'state': progress.get('state'),
                                                     'trainingSteps': progress.get('trainingSteps'),
                                                     'generationCalls': progress.get('generationCalls')})+'\n')
                        next_sample = time.perf_counter()+5
                except psutil.Error:
                    pass
                time.sleep(.5)
        state.update(state='COMPLETE_ASR_ADAPTER_TRIAL_SCORING_PENDING' if child.returncode == 0 else 'ASR_ADAPTER_TRIAL_FAILED_OR_STOPPED_RETAINED',
                     exitCode=child.returncode)
finally:
    if child is not None and child.poll() is None:
        stop_owned_family(child, owned)
    pressure.close()
    state.pop('workerPid', None)
    state.update(finishedAt=now(), seconds=time.perf_counter()-began, privatePeakBytes=peak)
    atomic_json(target, state)
    print(json.dumps(state, ensure_ascii=False), flush=True)
