from pathlib import Path
import subprocess,zipfile,os,shlex,json,base64,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone124');O=P/'ui-standard';O.mkdir(exist_ok=True)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
def adb(args,timeout=30):
 q=subprocess.run([str(A),'-s','d6bd213d',*map(str,args)],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout);assert q.returncode==0,(q.stdout+q.stderr)[-1600:];return q.stdout
if sys.argv[1]=='build':
 J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');SDK=Path('E:/CodexData/Companion/.build-cache/android-sdk');API=SDK/'platforms/android-35';classes=O/'classes';classes.mkdir(exist_ok=True);dex=O/'dex';dex.mkdir(exist_ok=True)
 cp=os.pathsep.join(map(str,[API/'android.jar',API/'uiautomator.jar',API/'optional/android.test.base.jar',API/'optional/android.test.runner.jar']))
 for args in [[J/'javac.exe','-J-Xmx128m','--release','8','-cp',cp,'-d',classes,C/'NativeUiStandard110.java']]:
  q=subprocess.run(list(map(str,args)),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert q.returncode==0,q.stderr.decode()[-1600:]
 jar=O/'classes.jar'
 with zipfile.ZipFile(jar,'w') as z:
  for f in classes.rglob('*.class'):z.write(f,f.relative_to(classes).as_posix())
 q=subprocess.run(list(map(str,[J/'java.exe','-Xmx192m','-XX:ActiveProcessorCount=1','-cp',SDK/'build-tools/36.0.0/lib/d8.jar','com.android.tools.r8.D8','--min-api','30','--lib',API/'android.jar','--output',dex,jar])),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert q.returncode==0,q.stderr.decode()[-1600:]
 out=O/'companion-notes124-ui.jar'
 with zipfile.ZipFile(out,'w') as z:z.write(dex/'classes.dex','classes.dex')
 adb(['push',out,'/data/local/tmp/companion-notes124-ui.jar']);print('Built standard UiAutomator driver without installing an APK')
else:
 state=json.loads((P/'virtual.json').read_text(encoding='utf8'));assert state['displayId']>0
 desired=sys.argv[1];request={'display':state['displayId'],'action':'dump' if desired=='tap' else desired}
 if len(sys.argv)>2:request['id' if sys.argv[2].startswith('id:') else 'label']=sys.argv[2].removeprefix('id:')
 if request['action']=='setText':request['value']=sys.argv[3]
 if len(sys.argv)>3 and request['action']=='click':request['index']=int(sys.argv[3])
 encoded=base64.b64encode(json.dumps(request).encode()).decode()
 cmd='uiautomator runtest /data/local/tmp/companion-notes124-ui.jar /system/framework/android.test.base.jar /system/framework/android.test.runner.jar -c com.denzic.companion.qa.NativeUiStandard110 -e requestB64 '+encoded
 output=adb(['shell',cmd]);(O/('result-'+str(time.time_ns())+'.private.txt')).write_text(output,encoding='utf8');row=next((line for line in output.splitlines() if line.startswith('COMPANION_UI=')),None)
 assert row,(output[-1900:]);result=json.loads(row.split('=',1)[1]);assert result['display']==state['displayId']
 if desired=='tap':
  import re
  matches=[node for node in result['nodes'] if (request.get('id') and node.get('id')==request['id']) or (request.get('label') and request['label'] in [node.get('text'),node.get('desc')])]
  index=int(sys.argv[3]) if len(sys.argv)>3 else 0;assert index<len(matches);node=matches[index];bounds=list(map(int,re.findall(r'-?\d+',node['bounds'])));assert len(bounds)==4 and node['enabled']
  left,top,right,bottom=bounds;x=(left+right)//2;y=(top+bottom)//2;assert right>left and bottom>top and 0<=x<1080 and 0<=y<state.get('height',1920)
  adb(['shell','input','-d',state['displayId'],'tap',x,y]);print(json.dumps({'display':state['displayId'],'action':'tap','ordinaryInputAtObservedBounds':True}));sys.exit(0)
 # Until the public library is active, keep record/document names out of model
 # output. The raw tool result is private and never published.
 safe={'打开','保存','取消','返回','更多选项','搜索','Downloads','Download','下载','最近','Recent','录音','设备','设置','所有录音','从备份恢复…','恢复资料备份','整份资料备份','返回录音库','存储设备','显示内部存储设备','内部存储设备','仅此一次','始终'}
 nodes=[]
 for node in result['nodes']:
  item={**node};label=item.get('text','');desc=item.get('desc','')
  if not label.startswith('Companion-public-') and label not in safe and '公开' not in label and 'S_R004S03C01' not in label:item['text']='[private text omitted]' if label else ''
  if not desc.startswith('Companion-public-') and desc not in safe and '公开' not in desc and 'S_R004S03C01' not in desc:item['desc']='[private text omitted]' if desc else ''
  if item['text'] or item['desc'] or item.get('id'):nodes.append(item)
 print(json.dumps({'display':result['display'],'action':result['action'],'nodes':nodes} if request['action']=='dump' else {'display':result['display'],'action':result['action'],'ordinaryUiActionSucceeded':True},ensure_ascii=False))
