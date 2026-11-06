from pathlib import Path
import subprocess,xml.etree.ElementTree as ET,re,json,sys,time
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');c=Path('E:/CodexData/Companion/.build-cache/device-phone055');a=str(r/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe');prefix=[a,'-s','6LCAPVHE9PBE45DU'];seq=str(time.time_ns())
def run(args,binary=False):
 p=subprocess.run(prefix+args,capture_output=True,timeout=30);assert p.returncode==0,p.stderr.decode('utf8',errors='replace');return p.stdout if binary else p.stdout.decode('utf8',errors='replace')
def guard():
 t=run(['shell','dumpsys','activity','activities']);active=[x for x in t.splitlines() if 'topResumedActivity=' in x];assert len(active)==1,active
 allowed=['com.denzic.companion.app/','com.android.permissioncontroller/','com.google.android.permissioncontroller/','com.android.settings/','com.android.documentsui/','com.google.android.documentsui/','com.miui.securitycenter/','com.android.intentresolver/','android/com.android.internal.app.ChooserActivity','com.denzic.companion.shareqa']
 assert any(x in active[0] for x in allowed),'Unrelated foreground; no input: '+active[0];return active[0].strip()
def dump():
 active=guard();run(['shell','uiautomator','dump','/sdcard/companion055-ui.xml']);raw=run(['exec-out','cat','/sdcard/companion055-ui.xml'],True);(c/('phone-ui-'+seq+'.xml')).write_bytes(raw);nodes=list(ET.fromstring(raw).iter('node'));return active,nodes
def compact(active,nodes):
 print(json.dumps({'foreground':active,'nodes':[{'text':n.get('text'),'desc':n.get('content-desc'),'id':n.get('resource-id'),'class':n.get('class').split('.')[-1],'enabled':n.get('enabled'),'bounds':n.get('bounds')} for n in nodes if n.get('text') or n.get('content-desc')]},ensure_ascii=False,indent=2))
verb=sys.argv[1] if len(sys.argv)>1 else 'read'
if verb=='read':compact(*dump())
elif verb=='tap':
 active,nodes=dump();label=sys.argv[2];found=[n for n in nodes if n.get('text')==label or n.get('content-desc')==label];assert found,'Control missing: '+label
 if len(sys.argv)<=3:found.sort(key=lambda n:0 if n.get('class','').endswith('Button') else 1)
 n=found[int(sys.argv[3]) if len(sys.argv)>3 else 0];assert n.get('enabled')=='true','Control disabled';bounds=list(map(int,re.findall(r'\d+',n.get('bounds'))));assert bounds[2]>bounds[0] and bounds[3]>bounds[1],bounds;guard();run(['shell','input','tap',str((bounds[0]+bounds[2])//2),str((bounds[1]+bounds[3])//2)]);print('Tapped '+label)
elif verb=='scroll':
 guard();direction=sys.argv[2] if len(sys.argv)>2 else 'down';run(['shell','input','swipe','640','2190' if direction=='down' else '700','640','700' if direction=='down' else '2190','400']);print('Scrolled '+direction)
elif verb=='screenshot':
 guard();dest=c/(sys.argv[2]+'.png');dest.write_bytes(run(['exec-out','screencap','-p'],True));print(str(dest))
elif verb=='back':guard();run(['shell','input','keyevent','4']);print('Back')
else:raise ValueError(verb)
