from pathlib import Path
import subprocess,os,json,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110');J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');jsonjar=Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar');tests=A/'apps/android/app/src/test/java/com/denzic/companion/app';cp=os.pathsep.join(map(str,[P/'app-classes',P/'backend-classes',jsonjar,P/'base-classes.jar']))
names=['ImportedAudioIntegrationTest','SpeechPcmConverterTest','PlaybackLifecycleTest'];results=[];case=P/('software-cases-'+str(time.time_ns()));case.mkdir()
jobs=[('compile',[J/'javac.exe','-J-Xmx128m','-J-XX:ActiveProcessorCount=1','--release','8','-encoding','UTF-8','-cp',cp,'-d',P/'app-classes',*[tests/(n+'.java') for n in names]])]+[(n,[J/'java.exe','-Xmx128m','-XX:ActiveProcessorCount=1','-cp',cp,'com.denzic.companion.app.'+n,case/n]) for n in names]
for name,args in jobs:
 q=subprocess.run(list(map(str,args)),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90);raw=q.stdout+q.stderr;(case/(name+'.log')).write_bytes(raw);results.append({'name':name,'exit':q.returncode});print(name,q.returncode,raw.decode(errors='replace')[-3000:])
 if q.returncode:break
record={'at':__import__('datetime').datetime.now().astimezone().isoformat(),'state':'PASSED' if len(results)==4 and all(x['exit']==0 for x in results) else 'FAILED','results':results,'fixtureDataOnly':True,'nativePhoneTested':False,'modelsRun':False,'logs':str(case)};(C/('software-result-'+str(time.time_ns())+'.json')).write_text(json.dumps(record,indent=2)+'\n');assert record['state']=='PASSED'
