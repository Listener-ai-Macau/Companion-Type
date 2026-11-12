from pathlib import Path
import os,json,subprocess,sys,time,re,hashlib
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');c=r/'docs/handoffs/20261110-android-media-import';p=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/customer-edit142-20261112');o=c/'customer-edit142';a=r/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';env={**os.environ,'COMPANION_PHONE_QA_CODE':'142','COMPANION_PHONE_QA_SESSION':'customer-edit142-20261112'};display=json.loads((p/'virtual.json').read_bytes())['displayId'];assert display==40
def adb(args):return subprocess.check_output([str(a),'-s','d6bd213d',*map(str,args)],text=True,encoding='utf-8')
def primary():
 text=adb(['shell','dumpsys','activity','activities']);block=next(x for x in text.split('Display #') if x.startswith('0 (activities from top to bottom):'));return hashlib.sha256(next((x.strip() for x in block.splitlines() if 'topResumedActivity=' in x),'').encode()).hexdigest()
def native(*args):
 result=subprocess.run(['python',str(c/'organization_native.py'),*args],env=env,capture_output=True,text=True,encoding='utf-8');assert result.returncode==0,result.stderr[-1200:]
def nodes():
 native('dump');f=max((p/'ui-standard').glob('result-*.private.txt'),key=lambda q:q.stat().st_mtime);text=f.read_text(encoding='utf-8');return json.loads(next(x for x in text.splitlines() if x.startswith('COMPANION_UI=')).split('=',1)[1])['nodes']
def observe():
 rows=nodes();allowed={'WPS Office','笔记','取消','打开','同意','不同意','跳过','继续','仅此一次','始终','保存','不保存','完成','返回','开始使用','立即登录','稍后再说'}
 # Do not expose share contacts, unrelated documents or account information.
 public=json.loads((o/'share-before.json').read_bytes())['selected']['text']
 safe=[{k:n.get(k) for k in ['text','desc','id','class','bounds']} for n in rows if n.get('text') in allowed or n.get('desc') in allowed or ('需求接续便签' in n.get('text',''))]
 print(json.dumps({'ownedDisplay':display,'safeControls':safe,'exactPublicTextVisible':public in '\n'.join(n.get('text','') for n in rows)},ensure_ascii=False))
action=sys.argv[1]
if action in ['expand','backscroll']:
 before=primary();adb(['shell','input','-d',display,'swipe',720,2000 if action=='backscroll' else 2850,720,2600 if action=='backscroll' else 1300,650]);time.sleep(1);assert primary()==before;observe()
elif action=='open':
 assert not subprocess.run([str(a),'-s','d6bd213d','shell','pidof','cn.wps.moffice_eng'],capture_output=True).stdout.strip()
 before=primary();native('tap','WPS Office');time.sleep(1);assert primary()==before;state=adb(['shell','dumpsys','activity','activities']);block=next(x for x in state.split('Display #') if x.startswith(str(display)+' '));assert 'cn.wps.moffice_eng' in block
 (p/'local-receiver-started.json').write_text(json.dumps({'mainBefore':before,'mainUnchangedDuringLaunch':True,'display':display,'ownRecipientPid':adb(['shell','pidof','cn.wps.moffice_eng']).strip(),'recipientInitiallyClosed':True}),encoding='utf-8');observe()
elif action=='observe':observe()
elif action=='view':
 before=primary();native('click','使用WPS Office查看');time.sleep(1);assert primary()==before
 state=adb(['shell','dumpsys','activity','activities']);block=next(x for x in state.split('Display #') if x.startswith(str(display)+' '));assert 'cn.wps.moffice_eng' in block
 (p/'local-receiver-started.json').write_text(json.dumps({'mainBefore':before,'mainUnchangedDuringLaunch':True,'display':display,'ownRecipientPid':adb(['shell','pidof','cn.wps.moffice_eng']).strip(),'recipientInitiallyClosed':True,'ordinarySystemSubchoice':'使用WPS Office查看'}),encoding='utf-8');observe()
elif action=='open-and-view':
 assert not subprocess.run([str(a),'-s','d6bd213d','shell','pidof','cn.wps.moffice_eng'],capture_output=True).stdout.strip();before=primary()
 native('tap','WPS Office');assert any(n.get('text')=='使用WPS Office查看' for n in nodes());native('tap','使用WPS Office查看')
 for _ in range(20):
  state=adb(['shell','dumpsys','activity','activities']);block=next(x for x in state.split('Display #') if x.startswith(str(display)+' '))
  if 'cn.wps.moffice_eng' in block:break
  time.sleep(.25)
 assert 'cn.wps.moffice_eng' in block and primary()==before
 (p/'local-receiver-started.json').write_text(json.dumps({'mainBefore':before,'mainUnchangedDuringLaunch':True,'display':display,'ownRecipientPid':adb(['shell','pidof','cn.wps.moffice_eng']).strip(),'recipientInitiallyClosed':True,'ordinarySystemSubchoice':'使用WPS Office查看'}),encoding='utf-8');observe()
elif action=='back':native('back');observe()
else:raise ValueError(action)
