from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import psutil

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
sys.path.insert(0, str(SRC))
from practical_io_20261107 import atomic_json, stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
from run_paired_fixed_asr_20261109 import resume_resources
from companion_local_pcm_session_20261114 import exclusive_file

parser = argparse.ArgumentParser()
parser.add_argument('--control', type=Path, required=True)
parser.add_argument('--inventory', type=Path, required=True)
args = parser.parse_args()
control = args.control.resolve()
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
target = control / 'run.json'
assert not target.exists(), 'Preserve prior attempts; continuation must be explicit'
inventory = read(args.inventory)
assert inventory['state'] == 'PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
assert 0 <= (datetime.now().astimezone() - datetime.fromisoformat(inventory['finishedAt'])).total_seconds() < 1800
gpu = inventory['selected']
assert gpu['name'] == 'AMD Radeon RX 6800 XT' and gpu['architecture'] == 'gfx1030'
worker = SRC / 'practical_alignment_session_worker_20261114.py'
assert sha(worker) == read(control / 'protocol.json')['workerSourceSha256']
worker_names = {'practical_alignment_worker_20261107.py', 'practical_alignment_session_worker_20261114.py',
                'companion_local_qwen_worker_20261114.py', 'run_paired_fixed_asr_20261109.py',
                'practical_qwen_boundaries_worker_20261107.py', 'practical_qwen_checkpoint_worker_20261107.py'}
for process in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(arg).name in worker_names for arg in process.info['cmdline'] or []), 'Another model worker is active'
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
env = {k: v for k, v in os.environ.items() if k not in {'CUDA_VISIBLE_DEVICES', 'ROCR_VISIBLE_DEVICES', 'HIP_VISIBLE_DEVICES', 'GPU_DEVICE_ORDINAL', 'PYTHONPATH'}}
env.update(HIP_VISIBLE_DEVICES=str(gpu['ordinal']), OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
           HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
python = 'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
state = {'state': 'PREPARING_NORMAL_TURN_ALIGNMENT', 'startedAt': now(), 'pid': os.getpid(),
         'results': [], 'newAsrCalls': 0, 'newSpeakerCalls': 0, 'automaticRetries': 0,
         'workerSourceSha256': sha(worker), 'inventorySha256': sha(args.inventory), 'currentGpu': gpu,
         'referencePassedToInference': False, 'speakerLabelsPassedToAligner': False, 'qualityQualified': False}
child = owned = None
pressure = SystemRamPressure()
try:
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
        for phase, expected in [('pilot', 'COMPLETE_NATIVE_ALIGNMENT_PILOT_NOT_TIME_QUALIFIED'),
                                ('full', 'COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED')]:
            resources = resume_resources(Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-r2-runs/near-N_SPK8015/task.json'))
            state['resourcesBeforeStage'] = resources
            if not resources['ready']:
                state.update(state='DEFERRED_ACTUAL_WINDOWS_RAM_GATE', finishedAt=now())
                break
            receipt = control / (phase + '-state.json')
            assert not receipt.exists()
            began = last_progress_at = time.perf_counter()
            peak = 0
            last_progress = None
            with (control / (phase + '-worker.log')).open('xb') as log:
                child = subprocess.Popen([python, str(worker), '--control', str(control), '--phase', phase], env=env,
                                         stdout=log, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                owned = psutil.Process(child.pid)
                state.update(state='RUNNING_NORMAL_TURN_ALIGNMENT_' + phase.upper(), activePid=child.pid)
                atomic_json(target, state)
                next_sample = 0
                while child.poll() is None:
                    low = pressure.low()
                    if low or (control / 'stop.request').exists() or time.perf_counter() - last_progress_at > 600:
                        state.update(state='STOPPED_NORMAL_TURN_ALIGNMENT_RETAINED',
                                     stopReason='actual_windows_low_ram' if low else 'explicit_stop_or_progress_deadline',
                                     availableBytesAtStop=psutil.virtual_memory().available)
                        stop_owned_family(child, owned)
                        break
                    try:
                        private = sum(p.memory_info().private for p in [owned] + owned.children(recursive=True))
                        peak = max(peak, private)
                        progress = read(receipt) if receipt.exists() else {}
                        point = (progress.get('state'), progress.get('completedLeaves'), progress.get('newNeuralCalls'))
                        if point != last_progress:
                            last_progress = point
                            last_progress_at = time.perf_counter()
                        if time.perf_counter() >= next_sample:
                            with (control / 'resources.jsonl').open('a', encoding='utf-8') as output:
                                output.write(json.dumps({'at': now(), 'stage': phase, 'availableBytes': psutil.virtual_memory().available,
                                                         'privateBytes': private, 'completedLeaves': progress.get('completedLeaves')}) + '\n')
                            next_sample = time.perf_counter() + 5
                    except psutil.Error:
                        pass
                    time.sleep(.5)
            state.pop('activePid', None)
            state['results'].append({'stage': phase, 'exitCode': child.returncode, 'privatePeakBytes': peak,
                                     'wholeOwnedProcessSeconds': time.perf_counter() - began})
            atomic_json(target, state)
            if child.returncode:
                if not state['state'].startswith('STOPPED_'):
                    state['state'] = 'FAILED_NORMAL_TURN_ALIGNMENT_RETAINED'
                break
            assert read(receipt)['state'] == expected
        else:
            state['state'] = 'COMPLETE_NORMAL_TURN_ALIGNMENT_JOIN_PENDING'
finally:
    if child is not None and child.poll() is None:
        stop_owned_family(child, owned)
    pressure.close()
    state.pop('activePid', None)
    state.update(finishedAt=now())
    atomic_json(target, state)
    print(json.dumps(state, ensure_ascii=False), flush=True)
