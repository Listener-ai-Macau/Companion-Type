from pathlib import Path
import ctypes,hashlib,json,os,psutil,socket,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');W=Path(__file__).parent
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-word062'
exe=F/'windows-bin/companion-type.exe';assert exe.exists()
C=Path('E:/CodexData/Companion/.build-cache/windows051')/('native060-word062-'+str(time.time_ns()));C.mkdir()
O=F/'native-ui';O.mkdir(exist_ok=False)
prior=R/'docs/handoffs/20261105-windows-content051'
fixture=max((p for p in prior.glob('native-files-*') if (p/'public-session.json').exists()),key=lambda p:p.stat().st_mtime)
row=json.loads((fixture/'public-session.json').read_text(encoding='utf8'))[0]
for name in ['audioPath','deviceRecordingId','deviceRecordingKey','deviceTotalLength','deviceSha256','sourceDeviceId','recorderControl','meetingTracks']:row[name]=None
row.update(audioStored=False,audioBytes=0,chunks=[],status='minutesReady',source='importedTranscript',pendingReason=None,captureIncomplete=False,recorderControlUncertain=False)
row['retention']['audioCached']=False;row['recovery'].update(intent='none',stage='idle',nextRetryAtUnixMs=None)
state=C/'sessions.json';state.write_text(json.dumps([row],ensure_ascii=False),encoding='utf8');before=hashlib.sha256(state.read_bytes()).hexdigest()
settings=C/'product-settings.json';settings.write_text('{}',encoding='utf8');(C/'recordings').mkdir()
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(state),'COMPANION_TYPE_RECORDING_DIR':str(C/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(settings),
 'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1','COMPANION_TYPE_BACKGROUND_WINDOW':'1',
 'COMPANION_TYPE_WEBVIEW_ARGS':f'--remote-debugging-port={port}','WEBVIEW2_USER_DATA_FOLDER':str(C/'webview2')}
source=json.loads((F/'source-frozen.json').read_text(encoding='utf8'))
config={'port':port,'output':str(O),'assets':source['windowsWebAssets'],'expectedText':'## 录音文字\n\n'+row['transcriptText'],'skipCopy':True}
(C/'config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf8')
js=(W/'windows051_native_gui.cjs').read_text(encoding='utf8')
js=js.replace("['txt','markdown','docx','pdf','xlsx','mindmap']","['txt','markdown','docx','pdf','xlsx','mindmap','pptx','png']")
js=js.replace('allSixFormatsNativePreview:true','allEightFormatsNativePreview:true')
(W/'windows060_native_gui.cjs').write_text(js,encoding='utf8')
user=ctypes.WinDLL('user32');user.GetClipboardSequenceNumber.restype=ctypes.c_uint
sequence=user.GetClipboardSequenceNumber()
result={'sourceCommit':source['sourceCommit'],'exeSha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'windowHidden':True,'ownerDataUsed':False,'modelsRun':False,'deviceIo':False,'clipboardTouched':False,'systemSaveAsOrShareOpened':False,'installed':False}
stream=(O/'app.log').open('wb');process=subprocess.Popen([str(exe)],cwd=exe.parent,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
created=psutil.Process(process.pid).create_time()
try:
    import urllib.request
    end=time.monotonic()+45
    while True:
        assert process.poll() is None,'Native test instance exited'
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=1) as response:
                if json.load(response):break
        except Exception:pass
        assert time.monotonic()<end,'Test WebView not available';time.sleep(.2)
    with (O/'ui.log').open('wb') as log:
        test=subprocess.run(['C:/Program Files/nodejs/node.exe',str(W/'windows060_native_gui.cjs'),str(C/'config.json')],stdout=log,stderr=subprocess.STDOUT,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    assert test.returncode==0,(O/'ui.log').read_text(encoding='utf8',errors='replace')[-3500:]
    result.update(status='ACTUAL_PRIVATE_NATIVE060_EIGHT_FORMAT_PREVIEW_PASSED',isolatedPublicSourceUnchanged=hashlib.sha256(state.read_bytes()).hexdigest()==before,clipboardSequenceUnchanged=user.GetClipboardSequenceNumber()==sequence)
    # The loader may omit known optional null fields from this synthetic seed.
    # Keep a byte change as a diagnostic fact and compare actual values before
    # attributing it to content loss; do not assert byte identity for a seed
    # that was not serialized by the production writer.
    if not result['isolatedPublicSourceUnchanged']:
        result['persistenceRequiresScopedComparison']=True
finally:
    if process.poll() is None:
        own=psutil.Process(process.pid);assert own.create_time()==created and Path(own.exe()).resolve()==exe.resolve()
        for child in own.children(recursive=True):
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        process.terminate();process.wait(timeout=15)
    stream.close();(O/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
