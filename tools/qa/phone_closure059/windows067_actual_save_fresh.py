from pathlib import Path
import hashlib,json,subprocess,sys,time,psutil
W=Path(__file__).parent
F=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff')
(F/'sessions').mkdir(exist_ok=True);(F/'saved').mkdir(exist_ok=True)
receipt=F/'actual-save-progress.json';results=json.loads(receipt.read_text(encoding='utf8'))
def call(*args):
 p=subprocess.run([sys.executable,str(W/'windows067_system_native.py'),*args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
 assert p.returncode==0,p.stdout+p.stderr
 return json.loads(p.stdout)
def save_copies(meta):
 C=Path(meta['isolation']);(F/'sessions'/(C.name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
 for file in (C/'saved').glob('Windows067-public-*'):
  destination=F/'saved'/file.name
  if destination.exists():assert destination.read_bytes()==file.read_bytes()
  else:destination.write_bytes(file.read_bytes())
previous=json.loads((F/'session.json').read_text(encoding='utf8'));save_copies(previous)
assert not psutil.pid_exists(previous['pid']),'Own previous QA still running'
for label,extension in [('PDF','pdf'),('PowerPoint','pptx'),('TXT','txt'),('Markdown','md'),('Excel','xlsx'),('思维导图（可编辑）','mm'),('思维导图 PNG','png')]:
 if any(row['format']==extension for row in results):continue
 old=(F/'session.json').stat().st_mtime_ns
 log=(F/'sessions'/(extension+'-launcher.log')).open('w',encoding='utf8')
 launcher=subprocess.Popen([sys.executable,str(W/'windows067_system_session.py')],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 meta=None
 try:
  end=time.monotonic()+20
  while (F/'session.json').stat().st_mtime_ns==old and launcher.poll() is None and time.monotonic()<end:time.sleep(.2)
  assert (F/'session.json').stat().st_mtime_ns!=old,'New own session failed'
  meta=json.loads((F/'session.json').read_text(encoding='utf8'));C=Path(meta['isolation'])
  end=time.monotonic()+20
  while True:
   check=subprocess.run([sys.executable,str(W/'windows067_system_native.py'),'app-invoke','打开清单'],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
   if check.returncode==0:break
   assert time.monotonic()<end,check.stdout+check.stderr;time.sleep(.2)
  call('app-disclose','导出、复制与分享');call('app-toggle','整理结果','false');call('app-toggle','录音文字','true')
  if extension!='pdf':
   call('app-expand','所选内容文件格式');call('app-select',label)
  controls=call('app-controls')['exportControls'];save=next(n['name'] for n in controls if n['name'].startswith('保存 '));assert label in save or (extension=='mm' and '思维导图' in save),(label,save)
  started=time.perf_counter();call('app-invoke',save)
  end=time.monotonic()+20
  while True:
   record=call('inspect')
   if any(w['class']=='#32770' for w in record['ownWindows']):
    if any(w['title']=='位置不可用' for w in record['ownWindows']):call('ack-location');continue
    break
   assert time.monotonic()<end,'Own Save As did not appear';time.sleep(.1)
  target=C/'saved'/('Windows067-public-transcript.'+extension);actual=call('save-path',str(target))
  row={'format':extension,'ordinaryNativeSaveAs':True,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'wallSeconds':round(time.perf_counter()-started,3),'publicFixture':True,'modelsRun':False,'receipt':actual,'freshPrivateDesktopBecauseSelectAfterModalNotObservable':True}
  results.append(row);receipt.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8');save_copies(meta)
  print(json.dumps({k:v for k,v in row.items() if k!='receipt'},ensure_ascii=False),flush=True)
  if extension=='png':
   before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (C/'saved').iterdir()};call('app-invoke',save)
   end=time.monotonic()+20
   while not any(w['class']=='#32770' for w in call('inspect')['ownWindows']):assert time.monotonic()<end;time.sleep(.1)
   cancel=call('cancel');after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (C/'saved').iterdir()};assert before==after
   (F/'actual-cancel.json').write_text(json.dumps({'actualCancel':cancel,'savedFilesIdentical':True,'modelsRun':False},ensure_ascii=False,indent=2),encoding='utf8')
 finally:
  if meta:(Path(meta['isolation'])/'stop-requested').write_text('own public QA finished',encoding='utf8')
  launcher.wait(timeout=25);log.close()
  assert launcher.returncode==0,'Own cleanup incomplete; inspect retained launcher log'
print('Eight ordinary native saves and cancellation reached; every run isolated without input desktop switch.',flush=True)
