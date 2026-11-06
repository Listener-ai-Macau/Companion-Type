from pathlib import Path
import hashlib,json,subprocess,sys,time
W=Path(__file__).parent
F=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff')
m=json.loads((F/'session.json').read_text(encoding='utf8'));C=Path(m['isolation'])
def call(*args):
 p=subprocess.run([sys.executable,str(W/'windows067_system_native.py'),*args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
 assert p.returncode==0,p.stdout+p.stderr
 return json.loads(p.stdout)
def dialog():
 end=time.monotonic()+20
 while time.monotonic()<end:
  record=call('inspect')
  if any(w['class']=='#32770' for w in record['ownWindows']):
   if any(w['title']=='位置不可用' for w in record['ownWindows']):call('ack-location');continue
   return record
  time.sleep(.15)
 raise RuntimeError('Own native Save As did not appear')
receipt=F/'actual-save-progress.json'
results=json.loads(receipt.read_text(encoding='utf8')) if receipt.exists() else []
for label,extension in [('Word','docx'),('PDF','pdf'),('PowerPoint','pptx'),('TXT','txt'),('Markdown','md'),('Excel','xlsx'),('思维导图（可编辑）','mm'),('思维导图 PNG','png')]:
 if any(row['format']==extension for row in results):continue
 controls=call('app-controls')['exportControls'];assert next(n['checked'] for n in controls if n['name']=='录音文字')==1
 assert next(n['checked'] for n in controls if n['name']=='整理结果')==0
 call('app-expand','所选内容文件格式');call('app-select',label)
 end=time.monotonic()+4
 while True:
  controls=call('app-controls')['exportControls'];save=[n['name'] for n in controls if n['name'].startswith('保存 ')];assert len(save)==1
  if label in save[0] or (extension=='mm' and '思维导图' in save[0]):break
  assert time.monotonic()<end,(label,save);time.sleep(.1)
 started=time.perf_counter();call('app-invoke',save[0]);dialog()
 target=C/'saved'/('Windows067-public-transcript.'+extension)
 actual=call('save-path',str(target))
 row={'format':extension,'ordinaryNativeSaveAs':True,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'wallSeconds':round(time.perf_counter()-started,3),'publicFixture':True,'modelsRun':False,'receipt':actual}
 results.append(row);receipt.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in row.items() if k!='receipt'},ensure_ascii=False),flush=True)
controls=call('app-controls')['exportControls'];save=next(n['name'] for n in controls if n['name'].startswith('保存 '))
before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (C/'saved').iterdir()}
call('app-invoke',save);dialog();cancel=call('cancel')
after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (C/'saved').iterdir()};assert before==after
(F/'actual-cancel.json').write_text(json.dumps({'actualCancel':cancel,'savedFilesIdentical':True,'modelRun':False},ensure_ascii=False,indent=2),encoding='utf8')
print('Eight actual native Save As operations and cancel finished.',flush=True)
