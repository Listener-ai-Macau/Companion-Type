from pathlib import Path
import subprocess,os,json,socket,time,urllib.request,ctypes,hashlib,shutil,psutil
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');out=root/'docs/handoffs/20261105-windows-content051'
exe=out/'windows-bin/companion-type.exe';assert exe.exists()
run=Path('E:/CodexData/Companion/.build-cache/windows051')/('native-ui-'+str(time.time_ns()));run.mkdir(parents=True)
evidence=out/('native-ui-'+str(time.time_ns()));evidence.mkdir()
fixture=max((p for p in out.glob('native-files-*') if (p/'public-session.json').exists()),key=lambda p:p.stat().st_mtime)
rows=json.loads((fixture/'public-session.json').read_text(encoding='utf8'));row=rows[0]
for name in ['audioPath','deviceRecordingId','deviceRecordingKey','deviceTotalLength','deviceSha256','sourceDeviceId','recorderControl','meetingTracks']:
    row[name]=None
row.update(audioStored=False,audioBytes=0,chunks=[],status='minutesReady',source='importedTranscript',pendingReason=None,captureIncomplete=False,recorderControlUncertain=False)
row['retention']['audioCached']=False
row['recovery'].update(intent='none',stage='idle',nextRetryAtUnixMs=None)
state=run/'sessions.json';state.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8');before=hashlib.sha256(state.read_bytes()).hexdigest()
settings=run/'product-settings.json';settings.write_text('{}',encoding='utf8');(run/'recordings').mkdir()
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env=os.environ.copy();env.update(COMPANION_TYPE_STATE_PATH=str(state),COMPANION_TYPE_RECORDING_DIR=str(run/'recordings'),COMPANION_TYPE_PRODUCT_SETTINGS_PATH=str(settings),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1',COMPANION_TYPE_BACKGROUND_WINDOW='1',COMPANION_TYPE_WEBVIEW_ARGS=f'--remote-debugging-port={port}',WEBVIEW2_USER_DATA_FOLDER=str(run/'webview2'))
frozen=json.loads((out/'source-frozen.json').read_text(encoding='utf8'))
config={'port':port,'output':str(evidence),'expectedText':'## 录音文字\n\n'+row['transcriptText'],'assets':frozen['windowsWebAssets']};(run/'config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf8')
ole=ctypes.OleDLL('ole32');user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
ole.OleGetClipboard.argtypes=[ctypes.POINTER(ctypes.c_void_p)];ole.OleGetClipboard.restype=ctypes.c_long
ole.OleSetClipboard.argtypes=[ctypes.c_void_p];ole.OleSetClipboard.restype=ctypes.c_long
ole.OleFlushClipboard.restype=ctypes.c_long
user.GetClipboardData.argtypes=[ctypes.c_uint];user.GetClipboardData.restype=ctypes.c_void_p
user.GetClipboardSequenceNumber.restype=ctypes.c_uint
kernel.GlobalLock.argtypes=[ctypes.c_void_p];kernel.GlobalLock.restype=ctypes.c_void_p
kernel.GlobalUnlock.argtypes=[ctypes.c_void_p];kernel.GlobalSize.argtypes=[ctypes.c_void_p];kernel.GlobalSize.restype=ctypes.c_size_t
def read_clipboard():
    if not user.OpenClipboard(None):raise RuntimeError('Clipboard busy during check')
    try:
        handle=user.GetClipboardData(13);assert handle
        size=kernel.GlobalSize(handle);assert 0<size<1024*1024
        data=kernel.GlobalLock(handle);assert data
        try:return ctypes.wstring_at(data,size//2).split('\0',1)[0]
        finally:kernel.GlobalUnlock(handle)
    finally:user.CloseClipboard()
record={'state':'RUNNING','ownerDataUsed':False,'windowHidden':True,'deviceIo':False,'modelsRun':False,'exeSha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
backup=ctypes.c_void_p();backup_taken=False;changed=False
log=(evidence/'app.log').open('wb');proc=subprocess.Popen([str(exe)],cwd=exe.parent,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);created=psutil.Process(proc.pid).create_time()
try:
    end=time.monotonic()+45
    while True:
        assert proc.poll() is None,'Native app exited: '+(evidence/'app.log').read_text(encoding='utf8',errors='replace')[-1800:]
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=1) as response:tabs=json.load(response)
            if tabs:break
        except Exception:pass
        assert time.monotonic()<end,'CDP unavailable';time.sleep(.2)
    # Preserve an opaque OLE data object. Never log, persist or inspect the
    # user's previous clipboard contents or formats.
    assert ole.OleInitialize(None)>=0
    assert ole.OleGetClipboard(ctypes.byref(backup))>=0
    backup_taken=True;prior_sequence=user.GetClipboardSequenceNumber()
    with (evidence/'ui.log').open('wb') as stream:
        result=subprocess.run(['C:/Program Files/nodejs/node.exe',str(Path(__file__).parent/'windows051_native_gui.cjs'),str(run/'config.json')],stdout=stream,stderr=subprocess.STDOUT,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    assert result.returncode==0,(evidence/'ui.log').read_text(encoding='utf8',errors='replace')
    actual=read_clipboard();changed=user.GetClipboardSequenceNumber()!=prior_sequence
    assert actual==config['expectedText'],'OS clipboard differs from the selected native source'
    record.update(state='ACTUAL_NATIVE_UI_AND_WINDOWS_CLIPBOARD_PASSED',osClipboardExact=True,originalStateUnchanged=hashlib.sha256(state.read_bytes()).hexdigest()==before)
    assert record['originalStateUnchanged']
finally:
    if backup_taken:
        try:
            # Preserve a newer user copy if they used the clipboard in parallel.
            if user.GetClipboardSequenceNumber()!=prior_sequence and read_clipboard()==config['expectedText']:
                assert ole.OleSetClipboard(backup)>=0;assert ole.OleFlushClipboard()>=0;record['previousClipboardRestored']=True
            else:record['previousClipboardRestored']='untouched or newer copy retained'
        finally:
            if backup:
                table=ctypes.cast(backup,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(table[2])(backup)
            ole.OleUninitialize()
    if proc.poll() is None:
        owned=psutil.Process(proc.pid);assert owned.create_time()==created and Path(owned.exe()).resolve()==exe.resolve()
        # Only this isolated, nonrecording test instance and its WebView children.
        for child in owned.children(recursive=True):
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        proc.terminate();proc.wait(timeout=15)
    log.close();(evidence/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(out/'native-ui-result.json').write_text(json.dumps({'evidence':str(evidence),**record},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'evidence':str(evidence),**record},ensure_ascii=False))
