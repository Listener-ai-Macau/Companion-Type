from pathlib import Path
import hashlib,json,os,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110');O=P/'backup-compatibility';O.mkdir(exist_ok=False)
aar=S/'apps/android/app/libs/companion-android-backend.aar';assert hashlib.sha256(aar.read_bytes()).hexdigest()=='af498b880338aa5b8036cbfa97ad26588fdc784ee5eaf92e15df50c06e9aaadf'
with zipfile.ZipFile(aar) as z:(O/'frozen-backend-classes.jar').write_bytes(z.read('classes.jar'))
jar=Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar');J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');classes=P/'checkpoint-classes';cp=os.pathsep.join(map(str,[classes,jar,O/'frozen-backend-classes.jar']))
test=S/'apps/android/app/src/test/java/com/denzic/companion/app/PlaybackBackupCompatibilityTest.java'
for name,args in [('compile',[J/'javac.exe','-J-Xmx128m','-J-XX:ActiveProcessorCount=1','--release','8','-encoding','UTF-8','-cp',cp,'-d',classes,test]),('roundtrip',[J/'java.exe','-Xmx96m','-XX:ActiveProcessorCount=1','-cp',cp,'com.denzic.companion.app.PlaybackBackupCompatibilityTest',O/'case'])]:
 with (O/(name+'.log')).open('wb') as out:p=subprocess.run(list(map(str,args)),stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 assert p.returncode==0,(O/(name+'.log')).read_text(errors='replace')[-1800:]
record={'state':'FROZEN_BACKEND_BACKUP_RESTORE_RETAINS_PLAYBACK_CHECKPOINT','backendSource':'608790132701ede93fa24a00b687874cb7e70c6b','playbackSourceSha256':hashlib.sha256((S/'apps/android/app/src/main/java/com/denzic/companion/app/PlaybackProgress.java').read_bytes()).hexdigest(),'ownerDataUsed':False,'phoneTested':False,'modelsRun':False}
(C/'backup-compatibility.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
