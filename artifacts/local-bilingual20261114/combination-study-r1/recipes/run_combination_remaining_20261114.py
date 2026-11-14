"""Finish this one predeclared comparison, serially, without neural retries."""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys
import time
import traceback

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
WORK = Path(__file__).resolve().parent
CACHE = Path('E:/CodexData/Companion/.model-cache/ordinary-combination-study-20261114')
sys.path.insert(0, str(SRC))
from practical_io_20261107 import atomic_json

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')
target = CONTROL / 'remaining-run.json'
assert not target.exists()
state = {'state': 'WAITING_CURRENT_BOUND_QWEN_CASE', 'startedAt': now(), 'stages': [],
         'automaticRetries': 0, 'newWeightUpdates': 0, 'qualityQualified': False}
atomic_json(target, state)


def run(name, command):
    state.update(state='RUNNING_'+name.upper())
    atomic_json(target, state)
    with (CONTROL / (name+'-console.log')).open('xb') as log:
        began = time.perf_counter()
        code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS).returncode
    state['stages'].append({'stage': name, 'exitCode': code, 'seconds': time.perf_counter()-began})
    atomic_json(target, state)
    assert code == 0, name+' failed; preserve outputs without automatic retry'


try:
    deadline = time.perf_counter()+5400
    qwen_batch = CACHE / 'qwen/batch.json'
    while True:
        batch = read(qwen_batch)
        if batch['state'] == 'COMPLETE_BOUND_NATIVE_CASES_UNSCORED':
            break
        assert batch['state'] in {'PREPARING_BOUND_NATIVE_CASES', 'RUNNING_BOUND_NATIVE_CASES'}, batch['state']
        assert time.perf_counter() < deadline, 'Existing Qwen case not terminal within bounded wait'
        time.sleep(5)
    run('paraformer', [sys.executable, str(SRC / 'run_paraformer_matched_spans_20261114.py'),
                       '--control', str(CONTROL / 'paraformer')])
    assert read(CONTROL / 'paraformer/run.json')['state'] == 'COMPLETE_PARAFORMER_COMPARATOR'
    run('prepare-alignment', [sys.executable, str(WORK / 'prepare_combination_alignment_20261114.py')])
    run('fresh-aligner-inventory', [sys.executable, str(SRC / 'run_practical_qwen_native_20261107.py'),
                                   '--phase', 'inventory', '--control', str(CONTROL / 'hip-aligner-current')])
    run('shared-alignment', [sys.executable, str(WORK / 'run_normal_turn_alignment_20261114.py'),
                             '--control', str(CONTROL / 'alignment'), '--inventory',
                             str(CONTROL / 'hip-aligner-current/hip-inventory.json')])
    assert read(CONTROL / 'alignment/run.json')['state'] == 'COMPLETE_NORMAL_TURN_ALIGNMENT_JOIN_PENDING'
    run('join-and-score', [sys.executable, str(WORK / 'join_combination_study_20261114.py')])
    assert read(CONTROL / 'result.json')['state'] == 'COMPLETE_TWO_FROZEN_COMBINATIONS_QUALITY_NOT_QUALIFIED'
    state['state'] = 'COMPLETE_FROZEN_COMBINATION_BATCH_REVIEW_PENDING'
except BaseException as error:
    state.update(state='INCOMPLETE_COMBINATION_BATCH_RETAINED_NO_AUTOMATIC_RETRY',
                 error=repr(error), traceback=traceback.format_exc())
    raise
finally:
    state['finishedAt'] = now()
    atomic_json(target, state)
    print(json.dumps(state, ensure_ascii=False), flush=True)
