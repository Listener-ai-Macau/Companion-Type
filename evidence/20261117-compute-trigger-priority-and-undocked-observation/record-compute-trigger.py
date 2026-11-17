"""Record the owner's compute-only trigger and read-only stack/undocked evidence."""
from pathlib import Path
from datetime import datetime
import argparse
import base64
import hashlib
import importlib.metadata
import json
import psutil
import subprocess

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
SCENE = E / 'system-restart-20261116-2315'
RUN = SCENE / 'laptop-undocked-r4'
SITE = Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop-owned-observation', action='store_true')
    args = parser.parse_args()
    started = read(RUN / 'started.json')
    if args.stop_owned_observation and not (RUN / 'completed.json').exists():
        proc = psutil.Process(started['pid'])
        assert abs(proc.create_time() - started['createdAt']) < .01
        assert any('monitor_thermal_20261117.py' in s for s in proc.cmdline())
        assert str(RUN).replace('\\', '/').lower() in ' '.join(proc.cmdline()).replace('\\', '/').lower()
        (RUN / 'stop.request').write_text(
            'Undocked high-temperature observation captured; diagnostic focus returned to GPU compute.\n',
            encoding='utf-8')
        print(json.dumps({'ownedStopRequested': True, 'pid': started['pid']}))
        return

    assert (RUN / 'completed.json').exists(), 'Consume owned logger terminal first.'
    completed = read(RUN / 'completed.json')
    assert not psutil.pid_exists(started['pid']), 'Logger must be closed before freezing evidence.'
    samples = [json.loads(line) for line in (RUN / 'samples.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    cpu = [(row['At'], item['Celsius']) for row in samples for item in row['CpuSensors']
           if item['Identifier'] == '/amdcpu/0/temperature/2']
    assert cpu and all(not row['ExternalGpuQueried'] for row in samples)
    command = """
$ErrorActionPreference='Stop'
[ordered]@{
  at=(Get-Date).ToString('o')
  displays=@(Get-PnpDevice -Class Display -PresentOnly | Select-Object FriendlyName,Status)
  videoDrivers=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion)
  battery=@(Get-CimInstance -Namespace root/wmi -Class BatteryStatus | Select-Object PowerOnline,Charging,Discharging)
} | ConvertTo-Json -Depth 5 -Compress
"""
    encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
    result = subprocess.run([
        'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile',
        '-NonInteractive', '-EncodedCommand', encoded], capture_output=True, text=True,
        encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    system = json.loads(result.stdout.lstrip('\ufeff'))
    assert not any('6800' in x['FriendlyName'] for x in system['displays'])
    packages = [{'name': d.metadata['Name'], 'version': d.version}
                for d in importlib.metadata.distributions(path=[str(SITE)])
                if any(term in d.metadata['Name'].lower() for term in ('torch', 'rocm', 'transformers'))]
    at = datetime.now().astimezone().isoformat(timespec='seconds')
    report = {
        'at': at,
        'state': 'GPU_COMPUTE_DOCK_COMBINATION_LEADING_TRIGGER_CPU_HEAT_NOT_ESTABLISHED_AS_CAUSE',
        'ownerQuotes': [
            '主要是接上显卡坞会热, 现在拔掉了',
            '这个死机问题只有接上显卡坞发生, 但是以前打游戏的时候也没有死机, 就是做模型训练的时候死机',
            '笔记本cpu热又不重启, 不相关吧'],
        'connectionType': 'USB4/Thunderbolt, previously confirmed by Owner',
        'undockedSystemSnapshot': system,
        'observation': {
            'run': str(RUN), 'started': started, 'completed': completed,
            'samples': len(samples), 'firstAt': cpu[0][0], 'lastAt': cpu[-1][0],
            'cpuMinCelsius': min(v for _, v in cpu), 'cpuMaxCelsius': max(v for _, v in cpu),
            'samplesAtLeast95C': sum(v >= 95 for _, v in cpu),
            'noRebootDuringObservation': psutil.boot_time() < started['createdAt'],
            'samplesSha256': sha(RUN / 'samples.jsonl'),
            'externalGpuTemperaturePolled': False,
            'controlledIdleOrMatchedGameComparison': False,
            'historicalPowerStateDuringGpuIncidentKnown': False,
            'noModelWorkLaunchedByThisObservation': True},
        'installedPackageMetadataWithoutImportingTorch': packages,
        'torchVersionSource': {'path': str(SITE / 'torch/version.py'),
                               'sha256': sha(SITE / 'torch/version.py'),
                               'text': (SITE / 'torch/version.py').read_text(encoding='utf-8')},
        'driverStoreVersions': {'rx6800xt': '32.0.21043.19003', 'radeon780m': '32.0.31021.5001'},
        'officialFindings': [
            {'url': 'https://github.com/ROCm/TheRock/blob/main/docs/development/windows_support.md',
             'finding': 'Native Windows support is relatively new and not yet mature.'},
            {'url': 'https://github.com/ROCm/TheRock/blob/main/SUPPORTED_GPUS.md',
             'finding': 'The development roadmap currently marks Windows gfx1030 build/sanity/release-ready. The page warns the development project is not production stable; this is not qualification of this installed driver and USB4 dock.'},
            {'url': 'https://www.amd.com/en/resources/support-articles/release-notes/rn-rad-win-26-6-4.html',
             'finding': 'Adrenalin26.6.4 lists BOTH installed driver-store versions. Different numbers alone do not prove an accidentally mixed or broken driver installation.'},
            {'url': 'https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html',
             'finding': 'The current10.1.0 matrix lists a coordinated driver/runtime stack; its Radeon table does not name RX6800XT. PRO W6000/gfx1030 must not be treated as qualification of this consumer card, current10.0 build and external dock.'}],
        'incidentFacts': {
            'retainedIncident': str(J / 'gpu-compatibility-r1/second-restart-20261117.json'),
            'twoRecentOwnedFailuresWereGpuInference': True, 'trainingUpdatesInThoseRuns': 0,
            'secondIncidentLastReservedGiB': 3.755859375,
            'secondIncidentLastDriverFreeGiB': 11.98052978515625,
            'samplesAreNotGuaranteedCrashInstant': True,
            'matchedNewBugcheckOrDump': False,
            'vramExhaustionProven': False,
            'MIOpenBypassAlreadyFailedToEstablishStability': True},
        'decision': 'Return diagnosis priority to GPU compute runtime/driver plus USB4 dock. High CPU temperature alone does not explain the selective reboots. Neither all thermal effects nor dock power/link faults are ruled out.',
        'nextIsolation': [
            'Keep the original compute environment and failed bytes. Do not repeat the same overnight batch or a driver/settings sweep.',
            'Once the GPU is connected, inventory the exact present device/driver/runtime first. Prepare one bounded owned-process compute reproduction from the failed workload, with durable operator entry/exit and resources; no quality or training claim from this diagnostic.',
            'Compare one discriminating backend/runtime condition only after a concrete compatible alternative is verified for RX6800XT. A different framework result can narrow the path, but cannot alone prove a driver or dock hardware defect.',
            'Keep the95C model-task cutoff as protection, not as a laptop shutdown threshold or root-cause diagnosis. Continue data/code work without CPU/iGPU training while the GPU is absent.'],
        'newNeuralCalls': 0, 'newGpuCalls': 0, 'parameterUpdates': 0,
        'driverTdrPowerBiosNetworkChanged': False, 'qualityQualified': False, 'saleQualified': False}
    target = J / 'gpu-compatibility-r1/compute-only-trigger-review-20261117.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    p = Path('work/bilingual_progress.json')
    progress = read(p)
    own = progress['jointArchitecture20261115']['overnightExecution20261116']
    own['computeOnlyTriggerReview20261117'] = {'receipt': str(target), **report}
    own['state'] = 'GPU_UNDOCKED_COMPUTE_COMPATIBILITY_DIAGNOSIS_AND_CPU_DATA_WORK_OPEN'
    progress['next'] = 'Owner澄清CPU高温未重启、接USB4显卡坞做模型才重启，根因未定；重点转回TheRock/驱动/显卡坞计算组合，禁止把95°C任务保护线当硬件关机证据。脱坞观察已终止并留存，高温无重启；独显实际不在场，不CPU/核显训练、不重跑旧失败GPU批次。继续中文跨会议说话人隔离元数据审计；英文119M仍0更新，待独显与单变量兼容性验证后执行原预检，95/98/整源/逐人/事实/盲测门保持。'
    progress['logResult'] += '\n\n' + at + '｜Owner再次澄清只有接显卡坞做模型计算才重启，游戏曾稳定、CPU热不重启；修正诊断优先级为GPU计算栈/驱动/USB4显卡坞组合，CPU高温不再当主因。独显已拔，当前仅780M；脱坞读数最高' + str(report['observation']['cpuMaxCelsius']) + '°C而无重启，非受控空闲/同负载对照，不据此排除所有热/供电/链路因素。只读查包证实Torch2.11+ROCm10.0；官方TheRock仍提示Windows不成熟；AMD26.6.4同时包含两块卡的驱动号，不能凭版本号不同诊断混装。保留原两次推理0更新/显存余量/无匹配dump证据；本轮0神经调用0训练，不改驱动/TDR/BIOS/功耗。原温度采样自有stop收尾，未关闭他人应用。结果' + str(target) + '。\n'
    p.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(target), 'cpuRange': [report['observation']['cpuMinCelsius'], report['observation']['cpuMaxCelsius']], 'samples': len(samples), 'gpuPresent': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
