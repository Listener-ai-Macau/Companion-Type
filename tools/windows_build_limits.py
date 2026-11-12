"""Limits for one native compiler family; no model or other-app limits change."""
import ctypes,os
from ctypes import wintypes as w
class CpuRate(ctypes.Structure):_fields_=[('ControlFlags',w.DWORD),('CpuRate',w.DWORD)]
class BasicLimits(ctypes.Structure):
 _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class IoCounters(ctypes.Structure):_fields_=[(n,ctypes.c_ulonglong) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class ExtendedLimits(ctypes.Structure):_fields_=[('BasicLimitInformation',BasicLimits),('IoInfo',IoCounters),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
class NativeBuildLimits:
 def __init__(self):
  assert os.name=='nt';self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
  for name,args,result in [('CreateJobObjectW',[ctypes.c_void_p,w.LPCWSTR],w.HANDLE),('GetCurrentProcess',[],w.HANDLE),('SetInformationJobObject',[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),('QueryInformationJobObject',[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p],w.BOOL),('AssignProcessToJobObject',[w.HANDLE,w.HANDLE],w.BOOL),('SetPriorityClass',[w.HANDLE,w.DWORD],w.BOOL)]:
   fn=getattr(self.kernel,name);fn.argtypes=args;fn.restype=result
  self.job=self.kernel.CreateJobObjectW(None,None);self.check(self.job)
  memory=ExtendedLimits();memory.BasicLimitInformation.LimitFlags=0x2000|0x200;memory.JobMemoryLimit=6*1024**3
  self.check(self.kernel.SetInformationJobObject(self.job,9,ctypes.byref(memory),ctypes.sizeof(memory)))
  rate=CpuRate(5,1000);self.check(self.kernel.SetInformationJobObject(self.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
  process=self.kernel.GetCurrentProcess();self.check(self.kernel.SetPriorityClass(process,0x40));self.check(self.kernel.AssignProcessToJobObject(self.job,process))
  observed=self.query();assert observed['jobPrivateCommitLimitBytes']==6*1024**3 and observed['cpuRate']==1000 and observed['cpuControlFlags']==5
 @staticmethod
 def check(ok):
  if not ok:raise ctypes.WinError(ctypes.get_last_error())
 def query(self):
  memory=ExtendedLimits();rate=CpuRate();self.check(self.kernel.QueryInformationJobObject(self.job,9,ctypes.byref(memory),ctypes.sizeof(memory),None));self.check(self.kernel.QueryInformationJobObject(self.job,15,ctypes.byref(rate),ctypes.sizeof(rate),None))
  return {'jobPrivateCommitLimitBytes':memory.JobMemoryLimit,'jobPeakPrivateCommitBytes':memory.PeakJobMemoryUsed,'cpuRate':rate.CpuRate,'cpuControlFlags':rate.ControlFlags,'scope':'This native compiler family only; model limits and Owner processes unchanged'}
