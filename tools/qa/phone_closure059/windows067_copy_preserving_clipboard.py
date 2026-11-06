"""Verify only the explicit public source; preserve original OLE data without inspecting it."""
# Retained as failure evidence. The first run proved the product copy but failed
# to restore OLE data; never run this method on the owner's clipboard again.
raise SystemExit('Retired after OLE restore failure. No clipboard operation performed.')
from pathlib import Path
from ctypes import wintypes
import ctypes,json,subprocess,sys,time
W=Path(__file__).parent
F=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff')
m=json.loads((F/'session.json').read_text(encoding='utf8'));C=Path(m['isolation']);expected='## 录音文字\n\n'+json.loads((C/'public-seed.json').read_text(encoding='utf8'))['transcriptText']
o=ctypes.OleDLL('ole32');u=ctypes.WinDLL('user32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
o.OleInitialize.argtypes=[ctypes.c_void_p];o.OleInitialize.restype=ctypes.c_long
o.OleGetClipboard.argtypes=[ctypes.POINTER(ctypes.c_void_p)];o.OleGetClipboard.restype=ctypes.c_long
o.OleSetClipboard.argtypes=[ctypes.c_void_p];o.OleSetClipboard.restype=ctypes.c_long
o.OleFlushClipboard.restype=ctypes.c_long
u.GetClipboardSequenceNumber.restype=wintypes.DWORD;u.OpenClipboard.argtypes=[wintypes.HWND];u.OpenClipboard.restype=wintypes.BOOL
u.GetClipboardData.argtypes=[wintypes.UINT];u.GetClipboardData.restype=wintypes.HANDLE
k.GlobalLock.argtypes=[wintypes.HANDLE];k.GlobalLock.restype=ctypes.c_void_p;k.GlobalUnlock.argtypes=[wintypes.HANDLE]
assert o.OleInitialize(None)>=0
original=ctypes.c_void_p();record={'publicFixture':True,'originalClipboardContentsReadOrRecorded':False,'modelsRun':False};matched=False;copied_sequence=None
try:
 initial=u.GetClipboardSequenceNumber();assert o.OleGetClipboard(ctypes.byref(original))>=0,'Could not retain original OLE data; no copy action'
 assert u.GetClipboardSequenceNumber()==initial,'Clipboard changed before operation; no copy action'
 p=subprocess.run([sys.executable,str(W/'windows067_system_native.py'),'app-invoke','复制所选内容'],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
 assert p.returncode==0,p.stdout+p.stderr
 end=time.monotonic()+10
 while time.monotonic()<end:
  seq=u.GetClipboardSequenceNumber()
  if seq!=initial and u.OpenClipboard(None):
   try:
    handle=u.GetClipboardData(13)
    if handle:
     data=k.GlobalLock(handle)
     if data:
      try:matched=ctypes.wstring_at(data)==expected
      finally:k.GlobalUnlock(handle)
   finally:u.CloseClipboard()
   if matched:copied_sequence=seq;break
  time.sleep(.05)
 assert matched,'Public clipboard content did not match; unexpected text was not recorded'
 record.update(actualOrdinaryCopy=True,sourceTextExactlyMatched=True,originalClipboardRestored=False)
finally:
 if matched and u.GetClipboardSequenceNumber()==copied_sequence:
  assert o.OleSetClipboard(original)>=0,'Original clipboard restore failed'
  assert o.OleFlushClipboard()>=0,'Original clipboard persistence failed'
  record['originalClipboardRestored']=True
 elif matched:record['restoreSkippedBecauseClipboardChangedExternally']=True
 if original.value:
  table=ctypes.cast(original,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
  ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(table[2])(original)
 o.OleUninitialize()
 (F/'actual-copy.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
assert record.get('originalClipboardRestored') or record.get('restoreSkippedBecauseClipboardChangedExternally')
print(json.dumps(record,ensure_ascii=False))
