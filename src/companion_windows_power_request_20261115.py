"""Owned long-task power request. No display request or global plan changes.

Windows clears the request when this handle/process exits. Explicit user sleep
and battery Modern Standby policy still take precedence.
"""
import ctypes as ct
from ctypes import wintypes as w
import os


class Detailed(ct.Structure):
    _fields_ = [('module', w.HMODULE), ('reason_id', w.ULONG),
                ('count', w.ULONG), ('strings', ct.POINTER(w.LPWSTR))]


class Reason(ct.Union):
    _fields_ = [('detailed', Detailed), ('simple', w.LPWSTR)]


class Context(ct.Structure):
    _fields_ = [('version', w.ULONG), ('flags', w.DWORD), ('reason', Reason)]


class PowerLease:
    def __init__(self, reason='Companion 本地会议处理正在进行'):
        if os.name != 'nt':
            raise RuntimeError('Windows task power request required')
        self.kernel = ct.WinDLL('kernel32', use_last_error=True)
        for name, args, result in [
            ('PowerCreateRequest', [ct.POINTER(Context)], w.HANDLE),
            ('PowerSetRequest', [w.HANDLE, ct.c_int], w.BOOL),
            ('PowerClearRequest', [w.HANDLE, ct.c_int], w.BOOL),
            ('CloseHandle', [w.HANDLE], w.BOOL)]:
            fn = getattr(self.kernel, name)
            fn.argtypes, fn.restype = args, result
        self.reason = reason
        self.handle = None
        self.requests = []

    def __enter__(self):
        context = Context(0, 1, Reason(simple=self.reason))
        self.handle = self.kernel.PowerCreateRequest(ct.byref(context))
        if self.handle in {None, ct.c_void_p(-1).value}:
            self.handle = None
            raise ct.WinError(ct.get_last_error())
        try:
            for kind in [1, 3]:  # SystemRequired, ExecutionRequired
                if not self.kernel.PowerSetRequest(self.handle, kind):
                    raise ct.WinError(ct.get_last_error())
                self.requests.append(kind)
        except BaseException:
            self.close()
            raise
        return self

    def audit(self):
        return {'active': bool(self.handle), 'requestTypes': self.requests[:],
                'displayRequired': False, 'globalPowerSettingsChanged': False,
                'automaticReleaseOnProcessExit': True,
                'explicitUserSleepStillTakesPrecedence': True}

    def close(self):
        if self.handle:
            for kind in reversed(self.requests):
                self.kernel.PowerClearRequest(self.handle, kind)
            self.kernel.CloseHandle(self.handle)
        self.handle = None
        self.requests = []

    def __exit__(self, *_):
        self.close()
