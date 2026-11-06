"""One affected short execution control, never a new accuracy benchmark."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, os, psutil, subprocess, sys

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
M = R / 'model-research'
H = R / 'docs/handoffs/20261105-model-resume'
control = H / 'acoustic-retirement-short-20261106-r23'
read = lambda p: json.loads(Path(p).read_text(encoding='utf8'))
for p in psutil.process_iter(['name', 'cmdline']):
    try:
        if (p.info['name'] or '').lower().startswith('python'):
            assert not any(Path(a).name == 'moss_night_gpu_worker_20261104.py' for a in p.info['cmdline'] or []), 'One model at a time'
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
control.mkdir(exist_ok=False)
prior = H / 'post-reboot-short-20261106'
protocol = read(prior / 'frozen-protocol.json')
protocol['at'] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
protocol['runtime']['retireAcousticModulesAfterEncoding'] = True
protocol['scope'] = 'Affected execution control only: retire the completed acoustic encoder/adaptor storage after producing exactly the original projected audio features. All input/context/language weights/attention/generation and CPU5%/private2GiB/GPUidle/duty.1/low-RAM guards unchanged. Compare all generated token IDs to the already completed original same30s output. No training or reference text.'
for name, value in [('frozen-protocol.json', protocol), ('audio-only.json', read(prior / 'audio-only.json'))]:
    (control / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
(control / 'frozen-source-sha256.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (M / 'src').glob('*.py')}, indent=2) + '\n', encoding='utf8')
cmd = [sys.executable, str(M / 'src/run_night_moss_gpu_20261104.py'), '--inputs', str(control / 'audio-only.json'), '--run-name', 'acoustic-retirement-short', '--protocol', str(control / 'frozen-protocol.json'), '--control-root', str(control), '--output-suffix=-retirement-r23']
with (control / 'supervisor.log').open('xb') as stream:
    child = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    print(json.dumps({'state': 'AFFECTED_CONTROL_RUNNING', 'supervisorPid': child.pid, 'control': str(control), 'automaticFullRunAfterwards': False}), flush=True)
    code = child.wait()
summary = read(control / 'acoustic-retirement-short.json')
result = {'supervisorExitCode': code, 'state': summary['state'], 'sameGeneratedIds': False, 'qualityEvidence': False}
if summary['state'] == 'COMPLETE_GPU_INFERENCE_SCORING_REQUIRED':
    output = Path(summary['results'][0]['receipt']).parent
    previous = next((prior / 'results').glob('*/generated-ids.json'))
    current = read(output / 'generated-ids.json')
    original = read(previous)
    result.update(sameGeneratedIds=current == original, generatedTokenCount=len(current), previousTokenCount=len(original), acousticRetirement=read(output / 'completed-state.json').get('acousticRetirement'), baseline=str(previous))
(control / 'equivalence-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps(result, ensure_ascii=False), flush=True)
