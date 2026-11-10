from pathlib import Path
from datetime import datetime
import subprocess,os,json,time,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110');J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');jar=Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar');tests=A/'apps/android/app/src/test/java/com/denzic/companion/app';src=A/'apps/android/app/src/main/java/com/denzic/companion/app';case=P/('note-reliability-'+str(time.time_ns()));case.mkdir();classes=case/'classes';classes.mkdir();cp=os.pathsep.join(map(str,[classes,P/'app-classes',P/'backend-classes',jar,P/'base-classes.jar',Path('E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar')]));phase=sys.argv[1]
names=['LocalRecordingLifecycleConcurrencyTest'] if phase=='baseline' else ['LocalRecordingLifecycleConcurrencyTest','PlaybackLifecycleTest','RecordingNotesIntegrationTest','RecordingOrganizationIntegrationTest','MeetingLibrarySearchTest']
for name in names:(case/name).mkdir()
jobs=[('compile',[J/'javac.exe','-J-Xmx128m','-J-XX:ActiveProcessorCount=1','--release','8','-encoding','UTF-8','-cp',cp,'-d',classes,*([src/'LocalRecordingLifecycle.java'] if phase=='baseline' else list(src.glob('*.java'))),*[tests/(n+'.java') for n in names]])]+[(name,[J/'java.exe','-Xmx128m','-XX:ActiveProcessorCount=1','-cp',cp,'com.denzic.companion.app.'+name,case/name]) for name in names]
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'phase':phase,'state':'CHECKING','logs':str(case),'results':[],'modelsRun':False,'phoneTested':False}
for name,args in jobs:
 q=subprocess.run(list(map(str,args)),cwd=A,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=45);output=q.stdout+q.stderr;(case/(name+'.log')).write_bytes(output);result['results'].append({'name':name,'exit':q.returncode});print(name,q.returncode,output.decode(errors='replace')[-1800:])
 if q.returncode:break
result['state']='PASSED' if len(result['results'])==len(jobs) and all(x['exit']==0 for x in result['results']) else 'FAILED';(C/('note-reliability-'+phase+'.json')).write_text(json.dumps(result,indent=2)+'\n');assert result['state']=='PASSED'
