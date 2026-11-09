"""Release only this batch's app, virtual display and forwarded CDP port."""
from pathlib import Path
import json,psutil,time
_folder=Path(__file__).parent
exec(compile((_folder/'phone_session.py').read_text().split('action=sys.argv[1]')[0],'phone helpers','exec'))
C=_folder/'phone-d6';owner=json.loads((C/'owner-return.json').read_text());view=json.loads((P/'owner-view.private.json').read_text())
assert owner['originalActive'] and view['rows']==104 and not adb(['shell','pidof',PKG],required=False).strip()
index=json.loads(adb(['exec-out','run-as',PKG,'cat','files/companion-library-index.json'],binary=True));assert index['activeId']=='original' and len(index['libraries'])==2
session=json.loads((P/'cdp.json').read_text());port=session['cdpPort'];adb(['forward','--remove','tcp:'+str(port)],required=False)
assert ('tcp:'+str(port)+' ') not in adb(['forward','--list'])
state=json.loads((P/'virtual.json').read_text());assert state['displayId']==5
adb(['shell','wm','size','reset','-d',5],required=False);adb(['shell','wm','density','reset','-d',5],required=False)
try:
    process=psutil.Process(state['pid']);assert abs(process.create_time()-state['processCreatedAt'])<.01 and process.name().lower()=='scrcpy.exe' and '--new-display=1080x1920/360' in process.cmdline()
    process.terminate()
    try:process.wait(timeout=8)
    except psutil.TimeoutExpired:process.kill();process.wait(timeout=5)
except psutil.NoSuchProcess:pass
for _ in range(10):
    displays=adb(['shell','dumpsys','activity','activities'])
    if 'Display #5 (activities from top to bottom):' not in displays:break
    time.sleep(.3)
assert 'Display #5 (activities from top to bottom):' not in displays
adb(['shell','rm','-f','/data/local/tmp/companion-ui-standard110.jar'])
assert not adb(['shell','pidof',PKG],required=False).strip()
physicalSize=adb(['shell','wm','size','-d',0]);physicalDensity=adb(['shell','wm','density','-d',0])
record={'at':now(),'state':'OWNED_PHONE_ACCEPTANCE_SESSION_CLOSED_OWNER_LIBRARY_RESTORED','installedVersionCode':version(),'ownerOriginalRows':view['rows'],'retainedLibraries':2,'ownAppStopped':True,'ownVirtualDisplayStopped':True,'ownForwardRemoved':True,'temporaryVirtualMetricsReset':True,'physicalSizeUnchanged':'Physical size: 1440x3200' in physicalSize,'physicalDensityUnchanged':'Override density: 589' in physicalDensity,'boardAccessed':False,'computerUseUsed':False,'ownerPrivateFilesUploaded':False}
save(C/'session-ended.json',record);print(json.dumps(record,ensure_ascii=False))
