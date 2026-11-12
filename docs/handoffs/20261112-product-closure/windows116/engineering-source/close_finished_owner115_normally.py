from pathlib import Path
from datetime import datetime
from ctypes import wintypes
import ctypes
import json
import psutil

run=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/owner-guided-windows115-step-issues-fw66828-20261112')
receipt=run/'engineering-normal-close-request.json'
assert not receipt.exists(), 'Do not repeat the normal close request'
progress=json.loads((run/'progress.json').read_bytes())
events=[json.loads(line) for line in (run/'events.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
assert any(e.get('event')=='review_submitted' and e.get('selected')=='结束本轮' and e.get('processId')==progress['promptPid'] for e in events)
app=psutil.Process(progress['appPid'])
assert app.name().lower()=='companion-type.exe'
assert app.exe().replace('\\','/').lower().endswith('/companion type/companion-type.exe')
user=ctypes.WinDLL('user32',use_last_error=True)
user.EnumWindows.argtypes=[ctypes.c_void_p,wintypes.LPARAM]
user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
windows=[]
@ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
def visit(hwnd,param):
    pid=wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if pid.value==app.pid and user.IsWindowVisible(hwnd):
        title=ctypes.create_unicode_buffer(256)
        name=ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(hwnd,title,256)
        user.GetClassNameW(hwnd,name,256)
        windows.append(dict(hwnd=int(hwnd),title=title.value,windowClass=name.value))
    return True
user.EnumWindows(visit,0)
main=[window for window in windows if window['title']=='Companion Type' and window['windowClass'].startswith('Tauri')]
assert len(main)==1, f'Preserve ambiguous app windows: {windows}'
accepted=bool(user.PostMessageW(main[0]['hwnd'],0x0010,0,0))
result=dict(at=datetime.now().astimezone().isoformat(timespec='milliseconds'),appPid=app.pid,appCreatedAt=app.create_time(),window=main[0],normalWmClosePosted=accepted,reason='Owner explicitly selected end round and delegated technical checking; request ordinary close without accepting any discard dialog.',forcedTermination=False,foregroundChanged=False,microphoneCommandSent=False,unsavedEditsDiscarded=False,leaseReleasedByThisScript=False)
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
