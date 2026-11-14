"""Run a predeclared audio-only case list with the existing native adapter.

One model worker at a time, original resource guards, no automatic retries.
Completed outputs are reusable only under exact audio and model-pack bindings.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, json, os, subprocess, sys, time, wave
from practical_io_20261107 import atomic_json, stop_owned_family
from run_paired_fixed_asr_20261109 import sha, resume_resources
import psutil

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')

def main():
    parser = argparse.ArgumentParser()
    for name in ['manifest', 'model-pack', 'work-root', 'inventory']:
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    manifest = Path(args.manifest).resolve(); pack_path = Path(args.model_pack).resolve()
    root = Path(args.work_root).resolve(); inventory = read(args.inventory); pack = read(pack_path)
    assert inventory['state'] == 'PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
    assert abs((datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()) < 1800
    bound_gpu = read(Path(pack['sourceControl'])/'hip-inventory.json')['selected']
    assert all(inventory['selected'][k] == bound_gpu[k] for k in ['ordinal', 'name', 'architecture'])
    assert bound_gpu['name'] == 'AMD Radeon RX 6800 XT' and bound_gpu['architecture'] == 'gfx1030'
    cases = read(manifest); assert cases
    ids = [c['id'] for c in cases]; assert len(ids) == len(set(ids))
    for case in cases:
        assert not any('reference' in key.lower() for key in case), 'References belong only in the scorer'
        assert sha(case['audio']) == case['audioSha256']
        with wave.open(case['audio'], 'rb') as audio:
            assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) == (1, 2, 16000, 'NONE')
            assert audio.getnframes()/16000 == case['audioSeconds']
    binding = {'manifestSha256': sha(manifest), 'modelPackSha256': sha(pack_path)}
    root.mkdir(parents=True, exist_ok=True); state_path = root/'batch.json'
    if state_path.exists():
        assert args.resume and read(state_path)['binding'] == binding
        atomic_json(root/('batch-before-'+str(time.time_ns())+'.json'), read(state_path))
    else: assert not args.resume
    state = {'state': 'PREPARING_BOUND_NATIVE_CASES', 'at': now(), 'pid': os.getpid(), 'binding': binding,
             'currentDeviceCheck': inventory['selected'], 'completed': [], 'automaticRetries': 0, 'qualityQualified': False}
    for case in cases:
        task_dir = root/'tasks'/case['id']; task_path = task_dir/'task.json'
        task = read(task_path) if task_path.exists() else None
        if task:
            assert task['binding'] == {'audioSha256': case['audioSha256'], 'audioSeconds': case['audioSeconds'], 'modelPackSha256': sha(pack_path)}
            if task['state'] == 'COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED':
                assert sha(task['output']) == task['outputSha256']; state['completed'].append(case['id']); continue
            assert args.resume, 'An interrupted case needs explicit continuation'
        resources = resume_resources(task_path)
        if not resources['ready']:
            state.update(state='PAUSED_RESOURCES_NO_AUTOMATIC_RETRY', resources=resources, finishedAt=now())
            atomic_json(state_path, state); print(json.dumps(state, ensure_ascii=False)); return 1
        state.update(state='RUNNING_BOUND_NATIVE_CASES', activeCase=case['id']); atomic_json(state_path, state)
        logs = root/'console'; logs.mkdir(exist_ok=True)
        log = logs/(case['id']+'-'+str(time.time_ns())+'.log')
        command = [sys.executable, str(Path(__file__).with_name('companion_native_asr_20261107.py')),
                   '--audio', case['audio'], '--model-pack', str(pack_path), '--work-dir', str(task_dir)]
        if task: command.append('--resume')
        started = time.perf_counter(); child = None
        with log.open('xb') as handle:
            try:
                child = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                state['activeAdapterPid'] = child.pid; atomic_json(state_path, state)
                code = child.wait()
            except BaseException:
                if child is not None and child.poll() is None:
                    (task_dir/'stop.request').write_text('Owned batch interrupted; retain all results.\n', encoding='utf-8')
                    try: child.wait(timeout=15)
                    except subprocess.TimeoutExpired: stop_owned_family(child, psutil.Process(child.pid))
                state.pop('activeAdapterPid', None)
                state.update(state='INTERRUPTED_BOUND_NATIVE_CASES', finishedAt=now()); atomic_json(state_path, state)
                raise
        state.pop('activeAdapterPid', None)
        task = read(task_path) if task_path.exists() else {}
        state['lastAttempt'] = {'id': case['id'], 'exitCode': code, 'adapterSeconds': time.perf_counter()-started, 'taskState': task.get('state'), 'log': str(log)}
        if code or task.get('state') != 'COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED':
            state.update(state='PAUSED_BOUND_NATIVE_CASES_NO_AUTOMATIC_RETRY', finishedAt=now(), taskError=task.get('error'))
            atomic_json(state_path, state); print(json.dumps(state, ensure_ascii=False)); return 1
        state['completed'].append(case['id']); atomic_json(state_path, state)
    state.pop('activeCase', None)
    state.update(state='COMPLETE_BOUND_NATIVE_CASES_UNSCORED', finishedAt=now()); atomic_json(state_path, state)
    print(json.dumps(state, ensure_ascii=False)); return 0

if __name__ == '__main__':
    raise SystemExit(main())
