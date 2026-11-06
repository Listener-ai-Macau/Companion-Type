from pathlib import Path
import json,re,subprocess,sys,time,xml.etree.ElementTree as ET
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059');C.mkdir(exist_ok=True)
ADB=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
SERIAL='6LCAPVHE9PBE45DU'
LEASE='Companion第1-2项059控制与公开资料导出验收'
def run(args,binary=False):
    p=subprocess.run([str(ADB),'-s',SERIAL,*map(str,args)],capture_output=True,timeout=35)
    assert p.returncode==0,p.stderr.decode('utf8',errors='replace')
    return p.stdout if binary else p.stdout.decode('utf8',errors='replace')
def guard():
    line=''.join(x for x in (R/'docs/board_operations.md').open(encoding='utf-8-sig') if x.startswith('- **占用中**'))
    assert LEASE in line,'Our exact shared phone/board item is not held; no input'
    policy=run(['shell','dumpsys','window','policy'])
    start=policy.find('KeyguardServiceDelegate');assert start>=0,'Unknown lock state; no input'
    keyguard=policy[start:]
    assert 'screenState=SCREEN_STATE_ON' in keyguard and not re.search(r'\b(?:showing|mIsShowing|inputRestricted|mInputRestricted)=true\b',keyguard),'Phone locked or screen off; no input'
    activity=run(['shell','dumpsys','activity','activities'])
    active=[s for s in activity.splitlines() if 'topResumedActivity=' in s]
    assert len(active)==1,'Unknown foreground; no input'
    allowed=['com.denzic.companion.app/','com.android.permissioncontroller/','com.google.android.permissioncontroller/',
        'com.android.settings/','com.android.documentsui/','com.google.android.documentsui/',
        'com.miui.securitycenter/','com.android.intentresolver/','android/com.android.internal.app.ChooserActivity',
        'com.denzic.companion.shareqa056/']
    assert any(a in active[0] for a in allowed),'Unrelated foreground; no input'
    return active[0].strip()
def dump():
    active=guard();remote='/sdcard/companion059-ui.xml'
    run(['shell','uiautomator','dump',remote])
    raw=run(['exec-out','cat',remote],True)
    nodes=list(ET.fromstring(raw).iter('node'))
    return active,nodes
def public(node):
    text=node.get('text','');desc=node.get('content-desc','')
    # Do not persist unrelated paired-device identities in inspection receipts.
    if re.search(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}',text,re.I) and 'C8:ED:45:EB:95:B4' not in text:return None
    if not text and not desc:return None
    return {'text':text,'desc':desc,'id':node.get('resource-id'),'class':node.get('class','').split('.')[-1],
        'enabled':node.get('enabled'),'bounds':node.get('bounds')}
def point(node):
    b=list(map(int,re.findall(r'\d+',node.get('bounds',''))))
    assert len(b)==4 and b[2]>b[0] and b[3]>b[1],b
    assert node.get('enabled')=='true','Disabled control'
    return (b[0]+b[2])//2,(b[1]+b[3])//2
verb=sys.argv[1] if len(sys.argv)>1 else 'read'
if verb in ['read','tap','tap-id']:
    active,nodes=dump()
    if verb=='read':
        result={'foreground':active,'nodes':[v for n in nodes if (v:=public(n))]}
        # Native picker/own recipient only. Product library is inspected via
        # selected public/new recording DOM instead of saving all owner titles.
        if 'com.denzic.companion.app/' not in active:
            (C/('native-ui-'+str(time.time_ns())+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        label=sys.argv[2]
        found=[n for n in nodes if n.get('resource-id')==label] if verb=='tap-id' else [n for n in nodes if label in [n.get('text'),n.get('content-desc')]]
        found.sort(key=lambda n:0 if n.get('class','').endswith('Button') else 1)
        n=found[int(sys.argv[3]) if len(sys.argv)>3 else 0] if found else None
        assert n is not None,'Control missing: '+label
        x,y=point(n);guard();run(['shell','input','tap',x,y]);print('Tapped '+label)
elif verb=='back':guard();run(['shell','input','keyevent','4']);print('Back')
elif verb=='scroll':
    guard();size=run(['shell','wm','size']);match=re.findall(r'(\d+)x(\d+)',size);assert match
    width,height=map(int,match[-1]);down=len(sys.argv)<3 or sys.argv[2]=='down'
    run(['shell','input','swipe',width//2,int(height*(.80 if down else .3)),width//2,int(height*(.3 if down else .80)),400]);print('Scrolled')
elif verb=='screenshot':
    guard();name=sys.argv[2];assert re.fullmatch(r'[a-zA-Z0-9_-]+',name)
    path=C/(name+'.png');path.write_bytes(run(['exec-out','screencap','-p'],True));print(str(path))
else:raise ValueError(verb)
