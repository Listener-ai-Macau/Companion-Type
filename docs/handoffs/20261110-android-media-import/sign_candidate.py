"""Verify CI payload, then sign it with the already trusted local app key."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,re,subprocess,zipfile
parser=argparse.ArgumentParser();parser.add_argument('--code',type=int,default=111);parser.add_argument('--run',type=int,default=42627556502);parser.add_argument('--source',default='491b967b5fd78b089bb45fee3e07e4fbee15db46');args=parser.parse_args()
code=args.code;run=args.run;source=args.source;assert code in [122,123,124,125,126,127,128,129,130] and re.fullmatch('[a-f0-9]{40}',source)
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/('android'+str(code));O.mkdir(exist_ok=True)
D=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110')/('candidate125' if code==125 else 'android'+str(code)+'-ci')
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def command(args):
    result=subprocess.run(list(map(str,args)),capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr[-2000:]
    return result.stdout
if not D.exists():
    from release_readback import download
    repo='Listener-ai-Macau/Companion-Type';response=json.loads(command(['gh','api',f'repos/{repo}/actions/runs/{run}/artifacts']));artifacts=[item for item in response['artifacts'] if item['name']=='companion-android-core-ui-'+source and not item['expired']];assert len(artifacts)==1;artifact=artifacts[0];digest=artifact.get('digest','');assert re.fullmatch('sha256:[0-9a-f]{64}',digest)
    archive=D.parent/('android'+str(code)+'-ci-artifact.zip');transfer=download(repo,artifact['id'],archive,artifact['size_in_bytes'],digest.split(':',1)[1],kind='artifact')
    with zipfile.ZipFile(archive) as package:
        names=package.namelist();assert len(names)==len(set(names)) and len(names)<20000 and sum(item.file_size for item in package.infolist())<1024**3
        for name in names:
            parts=Path(name).parts;assert not Path(name).is_absolute() and ':' not in name and '\\' not in name and all(part not in ['.','..'] for part in parts)
        D.mkdir()
        for item in package.infolist():
            target=D/item.filename
            if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with package.open(item) as source_file,target.open('wb') as output:
                while data:=source_file.read(128*1024):output.write(data)
    (D/'artifact-transfer.json').write_text(json.dumps({'artifactId':artifact['id'],'sha256':digest,'transfer':transfer},indent=2)+'\n')
meta=next(D.rglob('build.json'));record=json.loads(meta.read_text());assert record['sourceCommit']==source and record['versionCode']==code
raw=meta.parent/('Companion-Android-0.1.'+str(code)+'-remote-debug.apk');assert sha(raw)==record['sha256']
bt=Path('E:/CodexData/Companion/.build-cache/android-sdk/build-tools/36.0.0')
java=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin/java.exe')
base=[java,'-Xmx160m','-XX:ActiveProcessorCount=1','-jar',bt/'lib/apksigner.jar']
apk=O/('Companion-Android-0.1.'+str(code)+'-core-candidate.apk')
command(base+['sign','--ks','C:/Users/Billy/.android/debug.keystore','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,raw])
signature=command(base+['verify','--print-certs',apk]);certificate=re.search(r'certificate SHA-256 digest: ([0-9a-f]+)',signature)[1]
assert certificate=='ecebce83705d3336731610451cd1685cadb2d87fba29e41a471b2b44d46c45da'
command([bt/'zipalign.exe','-c','-P','16','4',apk])
with zipfile.ZipFile(raw) as original,zipfile.ZipFile(apk) as signed:
    for name in original.namelist():
        if not name.startswith('META-INF/'):assert original.read(name)==signed.read(name),name
    for resource in record['pinnedModelResources']['resources']:
        assert hashlib.sha256(signed.read('com/denzic/companion/mobile/'+resource['name'])).hexdigest()==resource['sha256']
identity=command([bt/'aapt2.exe','dump','badging',apk]);assert ("versionCode='"+str(code)+"'") in identity
record.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ANDROID'+str(code)+'_CI_PAYLOAD_TRUSTED_SIGNER_AND_MODEL_RESOURCES_VERIFIED',apk=str(apk),apkSha256=sha(apk),apkBytes=apk.stat().st_size,signerSha256=certificate,signerMatchesPreviouslyTrustedApp=True,zip16KiBAligned=True,localTrustedResigningRequired=False,installed=False)
(O/'build-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:record[k] for k in ['state','sourceCommit','apk','apkSha256','signerMatchesPreviouslyTrustedApp']}))
