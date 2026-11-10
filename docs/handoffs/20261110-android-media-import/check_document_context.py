from pathlib import Path
from datetime import datetime
import os,subprocess,json,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';B=R/'companion-audio-import-backend20261110';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110');D=Path('E:/CodexData/Companion/.build-cache/document-context20261110');J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');case=D/('native-storage-'+str(time.time_ns()));case.mkdir();classes=case/'classes';classes.mkdir()
cp=os.pathsep.join(map(str,[classes,P/'app-classes',P/'backend-classes',Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar'),P/'base-classes.jar',Path('E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar')]))
fixture=[A/'apps/android/app/src/test/java/com/denzic/companion/app/ImportedAudioIntegrationTest.java'];assert fixture[0].exists()
tests=A/'apps/android/app/src/test/java/com/denzic/companion/app';test=tests/'DocumentContextIntegrationTest.java';jobs=[('compile',[J/'javac.exe','-J-Xmx128m','-J-XX:ActiveProcessorCount=1','--release','8','-encoding','UTF-8','-cp',cp,'-d',classes,fixture[0],test]),('owned-document-storage',[J/'java.exe','-Xmx128m','-XX:ActiveProcessorCount=1','-cp',cp,'com.denzic.companion.app.DocumentContextIntegrationTest',case/'library',D/'format-fixtures'])]
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CHECKING','logs':str(case),'results':[],'modelsRun':False,'phoneTested':False}
for name,args in jobs:
 q=subprocess.run(list(map(str,args)),cwd=A,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=45);output=q.stdout+q.stderr;(case/(name+'.log')).write_bytes(output);record['results'].append({'name':name,'exit':q.returncode});print(name,q.returncode,output.decode(errors='replace')[-2500:])
 if q.returncode:break
record['state']='ANDROID_DOCUMENT_CONTEXT_STORAGE_BACKUP_AND_EXACT_PURGE_PASS' if len(record['results'])==len(jobs) and all(x['exit']==0 for x in record['results']) else 'FAILED';(C/'document-native-storage.json').write_text(json.dumps(record,indent=2)+'\n');assert record['state']!='FAILED'
