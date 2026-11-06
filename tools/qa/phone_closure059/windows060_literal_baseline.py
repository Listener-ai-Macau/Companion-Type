from pathlib import Path
import hashlib,json,os,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-system-handoff'
m=json.loads((F/'session.json').read_text(encoding='utf8'));C=Path(m['isolation']);exe=Path(m['exe'])
assert hashlib.sha256(exe.read_bytes()).hexdigest()==m['expectedExeSha256']
out=F/'baseline-native';out.mkdir(exist_ok=True);fail=F/'failures';fail.mkdir(exist_ok=True)
actual=C/'saved/Windows060-public-transcript.docx';assert actual.exists()
(fail/'actual-native-save-Word060-literal-heading.docx').write_bytes(actual.read_bytes())
rows=json.loads((C/'sessions.json').read_text(encoding='utf8'));row=rows[0]
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(C/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(C/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(C/'settings.json'),
 'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1'}
receipt=F/'baseline-native-progress.json';results=json.loads(receipt.read_text(encoding='utf8')) if receipt.exists() else []
for format,extension in [('txt','txt'),('markdown','md'),('docx','docx'),('pdf','pdf'),('pptx','pptx'),('xlsx','xlsx'),('mindmap','mm'),('png','png')]:
 if any(item['format']==format for item in results):continue
 request=C/('baseline-'+format+'.json');request.write_text(json.dumps({'sessionId':row['id'],'meetingMode':'offlineStore','format':format,'contentSections':{'minutes':False,'transcript':True,'highlights':False,'timeline':False,'noteIds':[]}}),encoding='utf8')
 target=out/('public-transcript.'+extension);assert not target.exists(),target
 begin=time.perf_counter();run=subprocess.run([str(exe),'--meeting-export-request',str(request),str(target)],cwd=exe.parent,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=210,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 (out/(format+'.log')).write_text(run.stdout+run.stderr,encoding='utf8')
 item={'format':format,'exitCode':run.returncode,'wallSeconds':round(time.perf_counter()-begin,3),'actualSystemSaveAs':False}
 if target.exists():item.update(bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
 results.append(item);(F/'baseline-native-progress.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 if run.returncode!=0:item['retainedError']=(run.stdout+run.stderr)[-2500:]
 receipt.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(item),flush=True)
print('Controlled native files saved; actual ordinary Save As Word retained separately.',flush=True)
