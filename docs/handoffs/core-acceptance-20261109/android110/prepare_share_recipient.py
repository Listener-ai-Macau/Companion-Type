"""Install the existing local-only recipient; never alter USB security settings."""
from pathlib import Path
import hashlib,json,subprocess,time
C=Path(__file__).parent;_scriptFolder=C
exec(compile((C/'phone_session.py').read_text(encoding='utf8').split('action=sys.argv[1]')[0],str(C/'phone_session.py'),'exec'))
C=_scriptFolder
apk=Path('E:/CodexData/Companion/.build-cache/device-phone055/share-receiver059/Companion-Share-Receiver059-QA.apk')
assert sha(apk)=='99cecef5df125b04451adf8a5ea83557cbd61c1c44f1ebf29ca014778715c3d5'
pkg='com.denzic.companion.shareqa056'
assert not adb(['shell','pm','path',pkg],required=False).strip(),'Do not replace an existing helper'
with (P/'share-install.stdout').open('wb') as out,(P/'share-install.stderr').open('wb') as error:
    process=subprocess.Popen([str(A),'-s',SERIAL,'install','-t',str(apk)],stdout=out,stderr=error,creationflags=subprocess.CREATE_NO_WINDOW)
    installerSeen=False
    for _ in range(40):
        if process.poll() is not None:break
        activity=adb(['shell','dumpsys','activity','activities'])
        main=next((s for s in activity.split('Display #') if s.startswith('0 (activities from top to bottom):')),'')
        resumed=next((s for s in main.splitlines() if 'topResumedActivity=' in s),'')
        if any(name in resumed for name in ['com.miui.packageinstaller','com.android.packageinstaller','com.google.android.packageinstaller']):
            installerSeen=True
            break
        time.sleep(.25)
    if installerSeen:
        print(json.dumps({'state':'OWN_QA_INSTALLER_VISIBLE','installPid':process.pid,'securitySettingsChanged':False}));raise SystemExit(0)
    try:process.wait(timeout=30)
    except subprocess.TimeoutExpired:process.terminate();process.wait();raise RuntimeError('Own QA install did not finish; no security setting changed')
result=(P/'share-install.stdout').read_text(errors='replace')+(P/'share-install.stderr').read_text(errors='replace')
installed=bool(adb(['shell','pm','path',pkg],required=False).strip())
record={'at':now(),'package':pkg,'apkSha256':sha(apk),'installed':installed,'installerSeen':installerSeen,'securitySettingsChanged':False,'internetPermission':False,'contactsPermission':False,'broadStoragePermission':False,'sizeLimitBytes':20*1024**2,'state':'LOCAL_ONLY_SHARE_RECIPIENT_INSTALLED' if installed else 'QA_INSTALL_REJECTED_NO_SYSTEM_SECURITY_CHANGE','installUserRestricted':'INSTALL_FAILED_USER_RESTRICTED' in result}
save(C/'phone-d6/share-recipient.json',record);print(json.dumps(record))
