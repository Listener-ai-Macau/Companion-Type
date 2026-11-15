"""Reproduce a real Windows exclusive file lock and verify safe observation."""
from pathlib import Path
import ctypes as ct,json
from ctypes import wintypes as w
from practical_io_20261107 import atomic_json
from independent_progress_reader_20261108 import read_progress
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-independent-meetings');root=C/'observer-lock-control';root.mkdir(exist_ok=True);path=root/'progress.json';atomic_json(path,{'state':'NEW_REAL_PROGRESS','completedInputs':2});previous={'state':'PRIOR_OBSERVATION','completedInputs':1}
kernel=ct.WinDLL('kernel32',use_last_error=True);kernel.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ct.c_void_p,w.DWORD,w.DWORD,w.HANDLE];kernel.CreateFileW.restype=w.HANDLE;kernel.CloseHandle.argtypes=[w.HANDLE]
handle=kernel.CreateFileW(str(path),0x80000000,0,None,3,0x80,None);assert handle not in (None,ct.c_void_p(-1).value),ct.get_last_error()
try:
    try:path.read_bytes()
    except PermissionError:actual_exclusive_lock_reproduced=True
    else:raise AssertionError('Control did not really block file access')
    result,reason=read_progress(path,previous);assert result==previous and reason=='transient_windows_share_lock'
finally:assert kernel.CloseHandle(handle)
result,reason=read_progress(path,previous);assert result['completedInputs']==2 and reason is None
bad=root/'malformed.json';bad.write_text('{not valid json',encoding='utf8')
try:read_progress(bad,previous)
except json.JSONDecodeError:malformed_not_hidden=True
else:raise AssertionError('Do not conceal malformed configuration/JSON')
atomic_json(C/'observer-lock-proof.json',{'state':'PASS_REAL_WINDOWS_EXCLUSIVE_LOCK_OBSERVER_CONTINUES_AND_RECOVERS','actualExclusiveFileLockReproduced':actual_exclusive_lock_reproduced,'cachedObservationReturnedOnlyDuringLock':True,'freshProgressObservedAfterRelease':True,'malformedJsonStillFails':malformed_not_hidden,'noProgressDeadlineBypassed':False,'newModelCalls':0})
print('PASS_REAL_WINDOWS_EXCLUSIVE_LOCK_OBSERVER_CONTINUES_AND_RECOVERS',flush=True)
