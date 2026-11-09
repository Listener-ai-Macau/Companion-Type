"""Build the frozen Android candidate remotely; local signing preserves trust."""
from pathlib import Path
import hashlib,json,os,subprocess,urllib.request,zipfile
root=Path(__file__).resolve().parents[3];output=root/'android-candidate-output';output.mkdir()
gradle_sha='acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a'
archive=Path(os.environ['RUNNER_TEMP'])/'companion-gradle-9.7.1.zip'
urllib.request.urlretrieve('https://services.gradle.org/distributions/gradle-9.7.1-bin.zip',archive)
assert hashlib.sha256(archive.read_bytes()).hexdigest()==gradle_sha
with zipfile.ZipFile(archive) as package:package.extractall(archive.parent)
env={**os.environ,'JAVA_HOME':os.environ['JAVA_HOME_21_X64']}
env['PATH']=str(Path(env['JAVA_HOME'])/'bin')+os.pathsep+env['PATH']
subprocess.run(['cmd','/d','/c',str(archive.parent/'gradle-9.7.1/bin/gradle.bat'),'--no-daemon','--max-workers=2',':app:assembleDebug'],cwd=root/'apps/android',env=env,check=True)
apk=root/'apps/android/app/build/outputs/apk/debug/app-debug.apk'
resources=json.loads((root/'apps/android/app/src/main/resources/com/denzic/companion/mobile/provenance.json').read_text())
with zipfile.ZipFile(apk) as package:
    for item in resources['resources']:
        raw=package.read('com/denzic/companion/mobile/'+item['name'])
        assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
    with zipfile.ZipFile(root/'apps/android/app/libs/companion-android-backend.aar') as aar:
        for name in aar.namelist():
            if name.startswith('jni/arm64-v8a/') and name.endswith('.so'):
                assert package.read('lib/'+name[4:])==aar.read(name)
        web=root/'apps/mobile/dist'
        for file in web.rglob('*'):
            if file.is_file():assert package.read('assets/www/'+file.relative_to(web).as_posix())==file.read_bytes()
target=output/'Companion-Android-0.1.111-remote-debug.apk';target.write_bytes(apk.read_bytes())
record={'sourceCommit':os.environ['GITHUB_SHA'],'runId':os.environ['GITHUB_RUN_ID'],'versionCode':111,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'pinnedModelResources':resources,'nativeLibrariesUnchanged':True,'webAssetsMatchSourceBuild':True,'localTrustedResigningRequired':True,'phoneTested':False}
(output/'build.json').write_text(json.dumps(record,indent=2)+'\n')
