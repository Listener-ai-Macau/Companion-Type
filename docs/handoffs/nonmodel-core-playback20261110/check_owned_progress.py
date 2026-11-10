from pathlib import Path
import hashlib,json,os,subprocess,zipfile,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110')/('owned-progress-final'+('-'+sys.argv[1] if len(sys.argv)>1 else ''));P.mkdir(exist_ok=False)
aar=S/'apps/android/app/libs/companion-android-backend.aar';assert hashlib.sha256(aar.read_bytes()).hexdigest()=='af498b880338aa5b8036cbfa97ad26588fdc784ee5eaf92e15df50c06e9aaadf'
with zipfile.ZipFile(aar) as z:(P/'backend.jar').write_bytes(z.read('classes.jar'))
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');jar=Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar');classes=P/'classes';classes.mkdir();cp=os.pathsep.join(map(str,[classes,jar,P/'backend.jar']))
base='apps/android/app/src/';names=[base+'main/java/com/denzic/companion/app/'+name+'.java' for name in ['PlaybackProgress','LocalRecordingLifecycle']]+[base+'test/java/com/denzic/companion/app/'+name+'.java' for name in ['PlaybackProgressTest','PlaybackBackupCompatibilityTest','PlaybackLifecycleTest']]
results=[]
def run(name,args):
 with (P/(name+'.log')).open('wb') as log:p=subprocess.run(list(map(str,args)),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 results.append({'name':name,'exitCode':p.returncode});assert p.returncode==0,(P/(name+'.log')).read_text(errors='replace')[-2000:]
run('compile',[J/'javac.exe','-J-Xmx128m','-J-XX:ActiveProcessorCount=1','--release','8','-encoding','UTF-8','-cp',cp,'-d',classes,*[S/name for name in names]])
for name in ['PlaybackProgressTest','PlaybackBackupCompatibilityTest','PlaybackLifecycleTest']:run(name,[J/'java.exe','-Xmx96m','-XX:ActiveProcessorCount=1','-cp',cp,'com.denzic.companion.app.'+name,P/name])
record={'state':'OWNED_PLAYBACK_REOPEN_BACKUP_RESTORE_TRASH_AND_EXACT_PURGE_PASSED','results':results,'playbackSourceSha256':hashlib.sha256((S/names[0]).read_bytes()).hexdigest(),'nativeMediaPlayerTested':False,'phoneTested':False,'modelsRun':False}
(C/'owned-progress-check.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
