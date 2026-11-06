from pathlib import Path
import json,re,shlex,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059')
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';pre=[str(A),'-s','6LCAPVHE9PBE45DU']
lease=''.join(x for x in (R/'docs/board_operations.md').open(encoding='utf-8-sig') if x.startswith('- **占用中**'))
assert 'Companion第1-2项059控制与公开资料导出验收' in lease
display=json.loads((C/'virtual-session.json').read_text())['displayId'];assert display==2
def adb(args):
    args=list(map(str,args))
    if args and args[0]=='shell':args=['shell',' '.join(shlex.quote(x) for x in args[1:])]
    p=subprocess.run(pre+list(map(str,args)),capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30);assert p.returncode==0,p.stderr;return p.stdout
state=adb(['shell','dumpsys','activity','activities'])
sections=state.split('Display #');main=next(s for s in sections if s.startswith('0 (activities from top to bottom):'))
physical=next((s for s in main.splitlines() if 'topResumedActivity=' in s),'')
assert not re.search(r'com\.denzic\.companion|documentsui|ChooserActivity',physical),'Test window on main screen; no input'
# An empty resumed main activity is normal after the owner locks the physical
# phone. This driver still retrieves roots and injects input only on display2.
action=sys.argv[1] if len(sys.argv)>1 else 'dump'
extra=['-e','display',str(display),'-e','action','dump' if action=='tap' else action]
if len(sys.argv)>2:extra+=['-e','id' if sys.argv[2].startswith('id:') else 'label',sys.argv[2].removeprefix('id:')]
if action=='setText':extra+=['-e','value',sys.argv[3]]
elif len(sys.argv)>3:extra+=['-e','index',sys.argv[3]]
text=adb(['shell','am','instrument','-w',*extra,'com.denzic.companion.uidriver059/.NativeUi059'])
(C/('native-virtual-'+str(time.time_ns())+'.log')).write_text(text,encoding='utf8')
assert 'INSTRUMENTATION_CODE: -1' in text,text
line=next(x for x in text.splitlines() if x.startswith('INSTRUMENTATION_RESULT: result='))
result=json.loads(line.split('result=',1)[1])
if action=='tap':
    label=sys.argv[2];matches=[n for n in result['nodes'] if (n.get('id')==label[3:] if label.startswith('id:') else label in [n.get('text'),n.get('desc')])]
    index=int(sys.argv[3]) if len(sys.argv)>3 else 0;assert len(matches)>index,'Observed target missing'
    n=matches[index];b=list(map(int,re.findall(r'\d+',n['bounds'])));assert len(b)==4 and 0<=b[0]<b[2]<=1080 and 0<=b[1]<b[3]<=1920
    assert n['enabled'],'Disabled target';adb(['shell','input','-d',str(display),'tap',str((b[0]+b[2])//2),str((b[1]+b[3])//2)])
    print(json.dumps({'display':display,'action':'tap','observedLabel':label,'result':'SCOPED_VIRTUAL_DISPLAY_TAP'},ensure_ascii=False))
elif action!='dump':print(json.dumps({'display':result['display'],'action':result['action'],'result':'ORDINARY_UI_ACTION_SUCCEEDED'},ensure_ascii=False))
else:
    visible=[]
    for n in result['nodes']:
        b=list(map(int,re.findall(r'\d+',n.get('bounds',''))))
        if not(n.get('text') or n.get('desc')) or len(b)!=4 or b[2]<=b[0] or b[3]<=b[1] or b[0]>=1080 or b[1]>=1920:continue
        visible.append({'text':n.get('text') or n.get('desc'),'id':n.get('id'),'class':n.get('class','').split('.')[-1],'bounds':n.get('bounds')})
    print(json.dumps({'display':result['display'],'action':result['action'],'nodes':visible},ensure_ascii=False))
