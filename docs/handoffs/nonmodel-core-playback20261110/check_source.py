from pathlib import Path
import hashlib,json,os,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110');P.mkdir(exist_ok=True)
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');jsonjar=Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar');classes=P/'checkpoint-classes';classes.mkdir(exist_ok=True);case=P/'checkpoint-case';case.mkdir(exist_ok=False)
results=[]
def run(name,args):
 with (P/(name+'.log')).open('wb') as log:child=subprocess.run(list(map(str,args)),cwd=S,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 results.append({'name':name,'exitCode':child.returncode});assert child.returncode==0,(P/(name+'.log')).read_text(errors='replace')[-1800:]
main=S/'apps/android/app/src/main/java/com/denzic/companion/app/PlaybackProgress.java';test=S/'apps/android/app/src/test/java/com/denzic/companion/app/PlaybackProgressTest.java'
run('checkpoint-compile',[J/'javac.exe','-J-Xmx128m','-J-XX:ActiveProcessorCount=1','--release','8','-encoding','UTF-8','-cp',jsonjar,'-d',classes,main,test])
run('checkpoint-behavior',[J/'java.exe','-Xmx96m','-XX:ActiveProcessorCount=1','-cp',os.pathsep.join(map(str,[classes,jsonjar])),'com.denzic.companion.app.PlaybackProgressTest',case])
run('mobile-typecheck',['node','--max-old-space-size=256',S/'node_modules/typescript/bin/tsc','--project',S/'apps/mobile/tsconfig.json','--noEmit'])
record={'state':'PLAYBACK_CHECKPOINT_BEHAVIOR_AND_MOBILE_SOURCE_PASSED','results':results,'checkpointSourceSha256':hashlib.sha256(main.read_bytes()).hexdigest(),'testOnlyJsonJarSha256':hashlib.sha256(jsonjar.read_bytes()).hexdigest(),'nativePackaged':False,'actualPlaybackQualified':False,'modelsRun':False}
(C/'source-check.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
