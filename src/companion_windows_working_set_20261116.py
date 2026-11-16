"""A physical working-set ceiling for this process only; private/job limits stay separate."""
import ctypes,os
from ctypes import wintypes

class WorkingSetCeiling:
    def __init__(self,maximum_bytes):
        if os.name!='nt':raise RuntimeError('Windows-only working-set control')
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.GetCurrentProcess.restype=wintypes.HANDLE;self.process=self.kernel.GetCurrentProcess()
        self.kernel.GetProcessWorkingSetSizeEx.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetProcessWorkingSetSizeEx.restype=wintypes.BOOL
        self.kernel.SetProcessWorkingSetSizeEx.argtypes=[wintypes.HANDLE,ctypes.c_size_t,ctypes.c_size_t,wintypes.DWORD]
        self.kernel.SetProcessWorkingSetSizeEx.restype=wintypes.BOOL
        self.before=self.query();self.maximum=int(maximum_bytes)
        if not self.kernel.SetProcessWorkingSetSizeEx(self.process,self.before['minimumBytes'],self.maximum,0x2|0x4):raise ctypes.WinError(ctypes.get_last_error())
        after=self.query();assert after['maximumBytes']==self.maximum and after['flags']&4
    def query(self):
        low,high,flags=ctypes.c_size_t(),ctypes.c_size_t(),wintypes.DWORD()
        if not self.kernel.GetProcessWorkingSetSizeEx(self.process,ctypes.byref(low),ctypes.byref(high),ctypes.byref(flags)):raise ctypes.WinError(ctypes.get_last_error())
        return {'minimumBytes':low.value,'maximumBytes':high.value,'flags':flags.value,'maximumEnforced':bool(flags.value&4),'scope':'Current owned worker process only; no global/other-process/registry changes.'}
