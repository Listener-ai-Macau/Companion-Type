from pathlib import Path
import hashlib,json,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059')
VERSION=int(sys.argv[1]) if len(sys.argv)>1 else 59
OLD=int(sys.argv[3]) if len(sys.argv)>3 else 58
F=Path(sys.argv[2]) if len(sys.argv)>2 else R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058'
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';pre=[str(A),'-s','6LCAPVHE9PBE45DU']
def run(args,binary=False,timeout=45):
    p=subprocess.run(pre+args,capture_output=True,timeout=timeout)
    assert p.returncode==0,p.stdout.decode('utf8',errors='replace')+p.stderr.decode('utf8',errors='replace')
    return p.stdout if binary else p.stdout.decode('utf8',errors='replace')
def main():
    text=run(['shell','dumpsys','activity','activities']);sections=text.split('Display #')
    block=next(s for s in sections if s.startswith('0 (activities from top to bottom):'))
    top=next((s.strip() for s in block.splitlines() if 'topResumedActivity=' in s),'PHYSICAL_MAIN_NOT_RESUMED')
    assert 'com.denzic.companion' not in top and 'documentsui' not in top
    return top
lease=''.join(x for x in (R/'docs/board_operations.md').open(encoding='utf-8-sig') if x.startswith('- **占用中**'))
assert 'Companion第1-2项059控制与公开资料导出验收' in lease
version=run(['shell','dumpsys','package','com.denzic.companion.app']);assert f'versionCode={OLD} ' in version,'A newer version may exist; do not downgrade'
before_main=main()
command="run-as com.denzic.companion.app sh -c 'find files -type f -exec sha256sum {} \\;'"
before=run(['shell',command]);(C/f'app-files-before{VERSION:03d}.sha256').write_text(before,encoding='utf8')
v=json.loads((F/(f'apk{VERSION}-verification.json' if VERSION!=59 else 'apk059-verification.json')).read_text(encoding='utf8'));apk=Path(v['apk'])
assert hashlib.sha256(apk.read_bytes()).hexdigest()==v['sha256']
installed=run(['install','-r','-t',str(apk)],timeout=90)
after_main=main();main_same=before_main.split(' u0 ')[-1].split(' t')[0]==after_main.split(' u0 ')[-1].split(' t')[0]
after=run(['shell',command]);(C/f'app-files-after{VERSION:03d}.sha256').write_text(after,encoding='utf8')
def hashes(text):return {line.split(None,1)[1].strip():line.split(None,1)[0] for line in text.splitlines() if len(line.split(None,1))==2}
old=hashes(before);new=hashes(after);assert old and all(new.get(k)==v for k,v in old.items()),'Original app files changed'
package=run(['shell','dumpsys','package','com.denzic.companion.app']);assert f'versionCode={VERSION} ' in package
path=run(['shell','pm','path','com.denzic.companion.app']).strip().removeprefix('package:');actual=run(['shell','sha256sum',path]).split()[0];assert actual==v['sha256']
record={'version':f'0.1.{VERSION}/code{VERSION}','installed':True,'exactInstalledApkSha256':actual,'source':v['frontendSourceCommit'],
    'backendSource':v['backendSourceCommit'],'originalAppFilesByteIdentical':len(old),
    'physicalMainActivityStayedUnchanged':main_same,'installationOutput':installed,'virtualDisplayId':2,
    'ordinaryAppAcceptanceComplete':False,'snapshotFilesLocalOnly':True}
(C/f'installation{VERSION:03d}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(record,ensure_ascii=False))
print(run(['shell','am','start','--display','2','-n','com.denzic.companion.app/.MainActivity']))
