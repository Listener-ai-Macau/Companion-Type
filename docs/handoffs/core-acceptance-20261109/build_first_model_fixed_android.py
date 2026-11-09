"""Reuse the successful Android110 builder for the resource-only Android111 fix."""
from pathlib import Path
import subprocess
folder=Path(__file__).parent
source=(folder/'build_unified_android_candidate.py').read_text(encoding='utf8')
start=source.index("p=S/'apps/android/app/build.gradle'")
end=source.index('sys.path.insert')
source=source[:start]+"head=subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD'],text=True).strip()\n"+source[end:]
for before,after in [('android110','android111'),('Android110','Android111'),('ANDROID110','ANDROID111'),('0.1.110','0.1.111'),("'versionCode':110","'versionCode':111"),("versionCode='110'","versionCode='111'")]:
    source=source.replace(before,after)
start=source.index(" run('01-npm-ci'")
end=source.index(" web=S/'apps/mobile/dist'")
source=source[:start]+source[end:]
source=source.replace('  for item in web_manifest:',"  for name in ['metadata.bin','tokens.txt']:\n   expected=(S/'apps/android/app/src/main/resources/com/denzic/companion/mobile'/name).read_bytes();assert package.read('com/denzic/companion/mobile/'+name)==expected\n  for item in web_manifest:")
exec(compile(source,str(folder/'build_unified_android_candidate.py'),'exec'))
