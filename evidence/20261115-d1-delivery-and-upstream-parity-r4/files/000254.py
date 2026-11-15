"""Real Windows readback in a tiny child, without importing a model/runtime."""
import ctypes, json, os, subprocess, sys
from ctypes import wintypes as w
from pathlib import Path
from moss_windows_resource_limits_20261104 import MemoryPriority

def own_priority():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.GetProcessInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.GetProcessInformation.restype = w.BOOL
    value = MemoryPriority()
    if not kernel.GetProcessInformation(kernel.GetCurrentProcess(), 0, ctypes.byref(value), ctypes.sizeof(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value.MemoryPriority

if len(sys.argv) == 2 and sys.argv[1] == '--child':
    from moss_windows_resource_limits_20261104 import WorkerLimits
    limits = WorkerLimits(cpu_percent=5, memory_bytes=96 * 1024**2)
    receipt = limits.query()
    assert receipt['memoryPagePriority'] == own_priority() == 1
    assert receipt['cpuRate'] == 500 and receipt['jobPrivateCommitLimitBytes'] == 96 * 1024**2
    assert receipt['gpuPriorityClass'] == 0 and 'torch' not in sys.modules
    print(json.dumps(receipt))
else:
    before = own_priority()
    child = subprocess.run([sys.executable, str(Path(__file__)), '--child'], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    after = own_priority()
    assert before == after
    report = {'state': 'PASS_SELF_WORKER_MEMORY_PAGE_PRIORITY_READBACK', 'worker': json.loads(child.stdout), 'parentMemoryPriorityBefore': before, 'parentMemoryPriorityAfter': after, 'parentUnchanged': True, 'modelOrTorchImported': False, 'globalOrOtherProcessSettingChanged': False, 'limitations': 'OS reclaim hint only; not a fixed working-set/RAM guarantee or a measured improvement in the full meeting.'}
    target = Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261105-model-resume/worker-memory-priority-check-20261106.json')
    assert not target.exists(), 'Preserve prior check evidence'
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report))
