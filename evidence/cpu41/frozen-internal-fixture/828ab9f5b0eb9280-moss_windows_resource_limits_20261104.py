"""Limits for this experiment's worker only; never alter another application.

CPU rate is a Windows job hard cap shared with descendants. GPU idle priority
is a scheduling preference, NOT a GPU utilization/VRAM cap or a driver fix.
Keep the job handle alive for the lifetime of the worker.
"""
import ctypes
from ctypes import wintypes as w
import os


class SystemRamPressure:
    """Windows' actual low-physical-memory signal, not an invented free-RAM gate."""
    def __init__(self):
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateMemoryResourceNotification.argtypes=[ctypes.c_int]
        self.kernel.CreateMemoryResourceNotification.restype=w.HANDLE
        self.kernel.QueryMemoryResourceNotification.argtypes=[w.HANDLE,ctypes.POINTER(w.BOOL)]
        self.kernel.QueryMemoryResourceNotification.restype=w.BOOL
        self.kernel.CloseHandle.argtypes=[w.HANDLE];self.kernel.CloseHandle.restype=w.BOOL
        self.handle=self.kernel.CreateMemoryResourceNotification(0)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())

    def low(self):
        result=w.BOOL()
        if not self.kernel.QueryMemoryResourceNotification(self.handle,ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(result.value)

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


class CpuRate(ctypes.Structure):
    _fields_ = [('ControlFlags', w.DWORD), ('CpuRate', w.DWORD)]


class MemoryPriority(ctypes.Structure):
    _fields_ = [('MemoryPriority', w.ULONG)]


class BasicLimits(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong),
                ('PerJobUserTimeLimit', ctypes.c_longlong), ('LimitFlags', w.DWORD),
                ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', w.DWORD), ('Affinity', ctypes.c_size_t),
                ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IoCounters),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


class WorkerLimits:
    def __init__(self, cpu_percent=10, memory_bytes=2*1024**3):
        if os.name != 'nt':
            raise RuntimeError('This worker requires Windows resource limits')
        if not 1 <= cpu_percent <= 10:
            raise ValueError('Responsive mode permits at most 10% of machine CPU')
        if not 32*1024**2 <= memory_bytes <= 2*1024**3:
            raise ValueError('Model-family private committed memory budget must be at most 2GiB')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            'GetCurrentProcess': ([], w.HANDLE),
            'SetInformationJobObject': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            'QueryInformationJobObject': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p], w.BOOL),
            'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
            'IsProcessInJob': ([w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)], w.BOOL),
            'SetPriorityClass': ([w.HANDLE, w.DWORD], w.BOOL),
            'GetPriorityClass': ([w.HANDLE], w.DWORD),
            'SetProcessInformation': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            'GetProcessInformation': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            'CloseHandle': ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.kernel, name); fn.argtypes = args; fn.restype = result
        for name, args in (
            ('D3DKMTSetProcessSchedulingPriorityClass', [w.HANDLE, ctypes.c_int]),
            ('D3DKMTGetProcessSchedulingPriorityClass', [w.HANDLE, ctypes.POINTER(ctypes.c_int)]),
        ):
            fn = getattr(self.gdi, name); fn.argtypes = args; fn.restype = ctypes.c_long
        self.job = self.kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            # KILL_ON_JOB_CLOSE ensures this worker cannot leave model children.
            # Owner explicitly asks for system-RAM protection. This is a hard
            # limit on this job's committed private memory, not a fixed
            # free-RAM abort and not a limit on another application's memory.
            limits = ExtendedLimits(); limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x200
            limits.JobMemoryLimit=memory_bytes
            self._check(self.kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
            rate = CpuRate(0x1 | 0x4, round(cpu_percent * 100))
            self._check(self.kernel.SetInformationJobObject(self.job, 15, ctypes.byref(rate), ctypes.sizeof(rate)))
            process = self.kernel.GetCurrentProcess()
            self._check(self.kernel.SetPriorityClass(process, 0x40))  # IDLE_PRIORITY_CLASS
            # Only this background worker's pages receive the lowest reclaim
            # priority. Windows decides what to trim; no forced working-set
            # size, empty-working-set call, page-file or other-process change.
            memory_priority = MemoryPriority(1)  # MEMORY_PRIORITY_VERY_LOW
            self._check(self.kernel.SetProcessInformation(process, 0, ctypes.byref(memory_priority), ctypes.sizeof(memory_priority)))
            status = self.gdi.D3DKMTSetProcessSchedulingPriorityClass(process, 0)  # GPU IDLE
            if status != 0:
                raise RuntimeError(f'GPU idle scheduling failed: NTSTATUS 0x{status & 0xffffffff:08x}')
            self._check(self.kernel.AssignProcessToJobObject(self.job, process))
            # The handle now owns this process: do NOT close it explicitly.
            self.receipt = self.query()
            assert self.receipt['cpuControlFlags'] == 5 and self.receipt['cpuRate'] == rate.CpuRate
            assert self.receipt['cpuPriorityClass'] == 0x40 and self.receipt['gpuPriorityClass'] == 0
            assert self.receipt['memoryPagePriority'] == 1
        except BaseException:
            # Before assignment it is safe to release; after assignment this
            # worker exits on failure and Windows closes the handle itself.
            member = w.BOOL()
            self.kernel.IsProcessInJob(self.kernel.GetCurrentProcess(), self.job, ctypes.byref(member))
            if not member.value:
                self.kernel.CloseHandle(self.job)
            raise

    @staticmethod
    def _check(ok):
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    def query(self):
        rate = CpuRate(); priority = ctypes.c_int(-1); member = w.BOOL(); memory=ExtendedLimits()
        self._check(self.kernel.QueryInformationJobObject(self.job, 15, ctypes.byref(rate), ctypes.sizeof(rate), None))
        self._check(self.kernel.QueryInformationJobObject(self.job, 9, ctypes.byref(memory), ctypes.sizeof(memory), None))
        process = self.kernel.GetCurrentProcess()
        memory_priority = MemoryPriority()
        self._check(self.kernel.GetProcessInformation(process, 0, ctypes.byref(memory_priority), ctypes.sizeof(memory_priority)))
        self._check(self.kernel.IsProcessInJob(process, self.job, ctypes.byref(member)))
        status = self.gdi.D3DKMTGetProcessSchedulingPriorityClass(process, ctypes.byref(priority))
        if status != 0:
            raise RuntimeError(f'GPU priority readback failed: 0x{status & 0xffffffff:08x}')
        return {'pid': os.getpid(), 'cpuRate': rate.CpuRate, 'cpuControlFlags': rate.ControlFlags,
                'cpuPercentMaximum': rate.CpuRate / 100, 'inLimitedJob': bool(member.value),
                'jobPrivateCommitLimitBytes':memory.JobMemoryLimit,'jobMemoryLimitEnabled':bool(memory.BasicLimitInformation.LimitFlags & 0x200),
                'jobPeakPrivateCommitBytes':memory.PeakJobMemoryUsed,
                'cpuPriorityClass': self.kernel.GetPriorityClass(process),
                'memoryPagePriority': memory_priority.MemoryPriority,
                'memoryPagePriorityIsReclaimHintNotRamCap': True,
                'gpuPriorityClass': priority.value, 'gpuUtilizationHardCapped': False,
                'scope': 'This worker and its descendants only; no global or other-app changes.'}
