"""Upgrade only the authorized app, preserving every pre-update app file."""
from pathlib import Path
import json,subprocess,time,argparse
parser=argparse.ArgumentParser();parser.add_argument('--from-code',type=int,default=110);parser.add_argument('--to-code',type=int,default=111);args=parser.parse_args();oldCode=args.from_code;newCode=args.to_code;assert (oldCode,newCode) in [(110,111),(111,112),(112,113),(113,114),(114,115)]
C=Path(__file__).parent;_scriptFolder=C
source=(C/'phone_session.py').read_text(encoding='utf8').split('action=sys.argv[1]')[0]
exec(compile(source,str(C/'phone_session.py'),'exec'))
C=_scriptFolder
assert version()==oldCode
assert 'RecordingSyncService' not in adb(['shell','dumpsys','activity','services',PKG]),'Recording sync active; do not interrupt'
before=primary();adb(['shell','am','force-stop',PKG])
snapshot=files();save(P/('before'+str(newCode)+'-manifest.private.json'),hashes(snapshot))
proof=json.loads((C.parent/('android'+str(newCode))/'build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256']
result=adb(['install','-r','-t',apk],timeout=120);assert 'Success' in result and version()==newCode
after=hashes(files());old=hashes(snapshot);assert all(after.get(name)==digest for name,digest in old.items())
code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]==proof['apkSha256']
record={'at':now(),'state':'ANDROID'+str(newCode)+'_EXACT_TRUSTED_APK_INSTALLED_ALL_PREUPDATE_FILES_IDENTICAL','versionCode':newCode,'sourceCommit':proof['sourceCommit'],'apkSha256':proof['apkSha256'],'preservedFileCount':len(old),'primaryUnchanged':primary()==before,'nativeBackendUnchanged':True,'physicalBoardAccessed':False}
save(C/('phone-d6/installation'+str(newCode)+'.json'),record)
display=json.loads((P/'virtual.json').read_text())['displayId'];assert display>0
oldPort=json.loads((P/'cdp.json').read_text())['cdpPort'];adb(['forward','--remove','tcp:'+str(oldPort)],required=False)
adb(['shell','am','start','-W','--display',display,'-n',PKG+'/.MainActivity'])
pid=adb(['shell','pidof',PKG]).strip();assert pid.isdigit()
port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit()
save(P/'cdp.json',{'at':now(),'state':'ANDROID'+str(newCode)+'_WEBVIEW_ON_NON_MAIN_DISPLAY','displayId':display,'pid':int(pid),'cdpPort':int(port),'primaryUnchanged':before==primary()})
print(json.dumps(record))
