"""Freeze an explicit iGPU inference test, preserving every old dGPU control."""
from pathlib import Path
from datetime import datetime, timedelta
import hashlib, json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
H=R/'docs/handoffs/20261107-model-generation-recovery'
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

old=S/'practical_nemotron_worker_20261107.py'
target=S/'native8_780m_inference_20261117.py'
assert not target.exists()
text=old.read_text(encoding='utf-8')
replacements={
    'from practical_io_20261107 import atomic_json':'''from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure
from model_thermal_guard_20261117 import ThermalGuard
from companion_local_pcm_session_20261114 import exclusive_file
import psutil''',
    "limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);out=":
        "limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();thermal=ThermalGuard(P['thermal']);out=",
    '    save()\n    try:\n':'''    def stop(starting=False):
        assert not pressure.low() and psutil.virtual_memory().available>=P['minimumAvailableBytes'],'Original RAM guard'
        assert datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Bounded iGPU test deadline'
        assert not (C/'stop.request').exists(),'Owned stop requested'
        state['cpuTemperature']=thermal.check(starting=starting)
    save()
    try:
        assert sha(__file__)==P['workerSourceSha256']
        for item in P['helperSources']:assert sha(item['file'])==item['sha256']
        began=time.monotonic()
        while time.monotonic()-began<60:stop();time.sleep(1)
        stop(starting=True)
''',
    "        if P['backend']=='vulkan':": "        if P['backend']=='vulkan-780m':",
    '            from practical_native_devices_20261107 import devices,select_6800xt\n            inventory=devices(folder);selected=select_6800xt(inventory);gpu=selected[\'gpuOrdinal\'];state.update(nativeDeviceInventory=inventory,selectedNativeDevice=selected)':
    '''            from practical_native_devices_20261107 import devices
            inventory=devices(folder)
            matches=[r for r in inventory if r['type'] in (1,2) and 'radeon780mgraphics' in ''.join(r['description'].lower().split())]
            assert len(matches)==1,'A unique explicit Radeon780M is required; no CPU/dGPU fallback'
            selected=matches[0];gpu=selected['gpuOrdinal'];state.update(nativeDeviceInventory=inventory,selectedNativeDevice=selected)
            save()''',
    '            def collect():\n                nonlocal done': '            def collect():\n                nonlocal done\n                stop()',
    '            while submitted<count:\n': '            while submitted<count:\n                stop()\n',
    "'COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED'": "'COMPLETE_780M_SPEAKER_JOURNAL_UNQUALIFIED'",
    '        if directory_cookie is not None:directory_cookie.close()': '        if directory_cookie is not None:directory_cookie.close()\n        pressure.close()',
    "if __name__=='__main__':main()": "if __name__=='__main__':\n    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):main()"
}
for before,after in replacements.items():
    assert text.count(before)==1,(before,text.count(before))
    text=text.replace(before,after)
text=text.replace('LOADING_NATIVE8_CPU','PREPARING_EXPLICIT_780M_INFERENCE')
text=text.replace('Official native8-speaker model via its stable C ABI; no Torch/HIP or references.',
    'Explicit Radeon780M inference fork of the frozen native8 adapter; no training.')
target.write_text(text,encoding='utf-8');compile(text,str(target),'exec')
C=J/'igpu-native8-r1';run=E/C.name;assert not C.exists() and not run.exists();C.mkdir()
P=read(J/'cpu-native8-r1/protocol.json');V=read(H/'native8-f16-smoke-r1/protocol.json')
for key in ['nativeLibrary','nativeLibrarySha256','nativeExe','nativeExeSha256','nativeFiles']:P[key]=V[key]
logger=E/'system-restart-20261116-2315/igpu-native8-thermal-r1'
assert not logger.exists()
thermal=read(J/'context-activity-r1/silero-presence-day-r2/protocol.json')['thermal']
thermal.update(run=str(logger),loggerSources=[{'file':str(Path('work')/name),'sha256':sha(Path('work')/name)}
    for name in ['monitor_thermal_20261117.py','read_laptop_thermal_stream_20261117.ps1']])
for row in thermal['loggerSources']:row['file']=str(Path(row['file']).resolve())
helpers=['practical_native_devices_20261107.py','moss_windows_resource_limits_20261104.py',
    'practical_io_20261107.py','model_thermal_guard_20261117.py','companion_local_pcm_session_20261114.py']
at=datetime.now().astimezone()
P.update(frozenAt=at.isoformat(),backend='vulkan-780m',probabilityCacheRoot=str(run/'probabilities'),
    workerSourceSha256=sha(target),helperSources=[{'file':str(S/n),'sha256':sha(S/n)} for n in helpers],
    cpuPercent=5,thermal=thermal,minimumAvailableBytes=3414499000,stopAt=(at+timedelta(minutes=20)).isoformat(),
    precision='Same published-checkpoint FP16 GGUF as retained CPU61 control; explicit780M Vulkan inference only.',
    ownerIntegratedGpuPermission={'quote':'现在我们有和弦，你可以用和弦。','correction':'核显',
        'scope':'Inference/correctness/performance only; no CPU or integratedGPU training.'})
for name,digest in P['nativeFiles'].items():assert sha(Path(P['nativeLibrary']).parent/name)==digest
assert sha(P['model'])==P['modelSha256']
cases=read(J/'cpu-native8-r1/audio-only.json')
cases=[cases[0],cases[1]]
B={'at':at.isoformat(),'originalWorker':str(old),'originalWorkerSha256':sha(old),'newWorker':str(target),
    'newWorkerSha256':sha(target),'originalStrict6800SelectorUnchanged':True,
    'runtimeOnly':True,'parameterUpdates':0,'referenceLabelsPassedToWorker':False,
    'controlPurpose':'One exact retained61s waveform to compare raw FP16 posteriors/threshold activity with CPU. Not a quality sample.',
    'followupPurpose':'One original full ES2003b only if the61s runtime comparison passes; no new model/threshold grid.',
    'originalAcceptanceMetricsChanged':False,'qualityQualified':False,
    'cpuControlManifest':str(E/'cpu-native8-r1/probabilities/cpu-native8-control61/probabilities.json'),
    'cpuControlManifestSha256':sha(E/'cpu-native8-r1/probabilities/cpu-native8-control61/probabilities.json'),
    'cpuControlState':str(E/'cpu-native8-r1/results/cpu-native8-control61/completed-state.json'),
    'cpuControlStateSha256':sha(E/'cpu-native8-r1/results/cpu-native8-control61/completed-state.json'),
    'posteriorComparison':{'maximumAbsoluteError':0.02,'meanAbsoluteError':0.001,
        'maximumThresholdActivityDisagreementFraction':0.001,
        'scope':'Execution sanity check only, no quality gate replacement or bitwise equivalence claim.'}}
for name,value in [('protocol.json',P),('audio-only.json',cases),('binding.json',B)]:
    (C/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'run':str(run),'logger':str(logger),'worker':str(target),'training':False}))
