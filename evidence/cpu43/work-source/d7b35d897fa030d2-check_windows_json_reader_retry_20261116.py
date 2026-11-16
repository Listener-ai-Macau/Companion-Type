from pathlib import Path
import ctypes,hashlib,json,sys,threading,time
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import read_json
root=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/windows-reader-retry-r2');assert not root.exists();root.mkdir();p=root/'published.json';p.write_text('{"source":"unchanged"}\n',encoding='utf-8');original=p.read_bytes()
k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p];k.CreateFileW.restype=ctypes.c_void_p;k.CloseHandle.argtypes=[ctypes.c_void_p]
def lock():
 h=k.CreateFileW(str(p),0x40000000,0,None,3,0,None);assert h not in (None,ctypes.c_void_p(-1).value);return h
h=lock();task=threading.Thread(target=lambda:(time.sleep(.25),k.CloseHandle(h)));task.start();tick=time.monotonic();assert read_json(p)=={'source':'unchanged'};elapsed=time.monotonic()-tick;task.join();assert .2<=elapsed<3
h=lock();tick=time.monotonic()
try:
 try:read_json(p)
 except PermissionError:pass
 else:raise AssertionError('Permanent sharing denial must remain a bounded failure')
 permanent=time.monotonic()-tick;assert 2.9<=permanent<4
finally:k.CloseHandle(h)
bad=root/'invalid.json';bad.write_text('{',encoding='utf-8');tick=time.monotonic()
try:read_json(bad)
except json.JSONDecodeError:pass
else:raise AssertionError('Corrupt JSON must remain a parser failure')
assert time.monotonic()-tick<.1 and p.read_bytes()==original
out={'state':'PASS_WINDOWS_TEMPORARY_READER_DENIAL_BOUNDED_RETRY_PERMANENT_DENIAL_AND_CORRUPT_JSON_STILL_FAIL','temporaryDenialSeconds':elapsed,'permanentDenialSeconds':permanent,'sourceBytesUnchanged':True,'newNeuralCalls':0,'helperSha256':hashlib.sha256((S/'companion_local_pcm_session_20261114.py').read_bytes()).hexdigest()};(root/'result.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out))
