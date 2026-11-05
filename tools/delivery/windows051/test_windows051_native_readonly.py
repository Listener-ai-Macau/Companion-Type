from pathlib import Path
import subprocess,os,json,socket,time,urllib.request,hashlib,psutil
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');out=root/'docs/handoffs/20261105-windows-content051';exe=out/'windows-bin/companion-type.exe'
run=Path('E:/CodexData/Companion/.build-cache/windows051')/('readonly-ui-'+str(time.time_ns()));run.mkdir(parents=True)
evidence=out/('readonly-ui-'+str(time.time_ns()));evidence.mkdir()
fixture=max((p for p in out.glob('native-files-*') if (p/'public-session.json').exists()),key=lambda p:p.stat().st_mtime)
rows=json.loads((fixture/'public-session.json').read_text(encoding='utf8'));row=rows[0]
for name in ['audioPath','deviceRecordingId','deviceRecordingKey','deviceTotalLength','deviceSha256','sourceDeviceId','recorderControl','meetingTracks']:row[name]=None
row.update(audioStored=False,audioBytes=0,chunks=[],status='minutesReady',source='importedTranscript',pendingReason=None,captureIncomplete=False,recorderControlUncertain=False)
row['retention']['audioCached']=False;row['recovery'].update(intent='none',stage='idle',nextRetryAtUnixMs=None)
state=run/'sessions.json';state.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8');(run/'recordings').mkdir();settings=run/'settings.json';settings.write_text('{}',encoding='utf8')
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env=os.environ.copy();env.update(COMPANION_TYPE_STATE_PATH=str(state),COMPANION_TYPE_RECORDING_DIR=str(run/'recordings'),COMPANION_TYPE_PRODUCT_SETTINGS_PATH=str(settings),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1',COMPANION_TYPE_BACKGROUND_WINDOW='1',COMPANION_TYPE_WEBVIEW_ARGS=f'--remote-debugging-port={port}',WEBVIEW2_USER_DATA_FOLDER=str(run/'webview2'))
frozen=json.loads((out/'source-frozen.json').read_text(encoding='utf8'));config={'port':port,'output':str(evidence),'expectedText':'## 录音文字\n\n'+row['transcriptText'],'assets':frozen['windowsWebAssets'],'skipCopy':True};(run/'config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf8')
record={'state':'RUNNING','ownerDataUsed':False,'clipboardNotTouched':True,'windowHiddenRequested':True,'modelsRun':False,'deviceIo':False,'exeSha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
with (evidence/'app.log').open('wb') as log:
 proc=subprocess.Popen([str(exe)],cwd=exe.parent,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);created=psutil.Process(proc.pid).create_time()
 try:
  end=time.monotonic()+45
  while True:
   assert proc.poll() is None,'Native test app exited'
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=1) as response:tabs=json.load(response)
    if tabs:break
   except Exception:pass
   assert time.monotonic()<end,'CDP unavailable';time.sleep(.2)
  with (evidence/'ui.log').open('wb') as stream:r=subprocess.run(['C:/Program Files/nodejs/node.exe',str(Path(__file__).parent/'windows051_native_gui.cjs'),str(run/'config.json')],stdout=stream,stderr=subprocess.STDOUT,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
  assert r.returncode==0,(evidence/'ui.log').read_text(encoding='utf8',errors='replace')
  current=json.loads(state.read_text(encoding='utf8'))[0];keys=['transcriptText','utterances','transcriptReview','meetingNotes','noteRevision','minutes','minutesByMode','bookmarks','bookmarkRevision']
  assert all(row.get(k)==current.get(k) for k in keys)
  record.update(state='ACTUAL_NATIVE_UI_ASSETS_LIGHT_DARK_AND_PROTECTED_SOURCES_PASSED',publicSourceContentUnchanged=True)
 except BaseException as error:record.update(state='NATIVE_READONLY_UI_TEST_FAILED',error=repr(error));raise
 finally:
  if proc.poll() is None:
   owned=psutil.Process(proc.pid);assert owned.create_time()==created and Path(owned.exe()).resolve()==exe.resolve()
   for child in owned.children(recursive=True):
    try:child.terminate()
    except psutil.NoSuchProcess:pass
   proc.terminate();proc.wait(timeout=15)
  (evidence/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(out/'native-readonly-ui-result.json').write_text(json.dumps({'evidence':str(evidence),**record},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'evidence':str(evidence),**record},ensure_ascii=False))
