from pathlib import Path
import subprocess,os,json,time
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'recovered-software050';b=r/'docs/handoffs/20261106-android-material-exports054';c=Path('E:/CodexData/Companion/.build-cache/android054-materials')
j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin')
prod=c/'build/app/intermediates/javac/debug/compileDebugJavaWithJavac/classes'
assert (prod/'com/denzic/companion/app/MaterialLayout.class').exists()
classes=c/'qa-classes';classes.mkdir(exist_ok=True)
cp=os.pathsep.join(str(p) for p in [classes,c/'json-20240303.jar',prod,c/'backend-classes.jar'])
cmd=[str(j/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(classes),str(s/'apps/android/app/src/test/java/com/denzic/companion/app/MaterialFormatsTest.java')]
stamp=str(time.time_ns());log=b/('java-formats-'+stamp+'.log');out=b/('jvm-native-files-'+stamp);out.mkdir()
with log.open('wb') as f:
 p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 if p.returncode==0:p=subprocess.run([str(j/'java.exe'),'-Xmx256m','-XX:ActiveProcessorCount=2','-cp',cp,'com.denzic.companion.app.MaterialFormatsTest',str(out)],stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
result={'exitCode':p.returncode,'productionClassDirectory':str(prod),'output':str(out),'log':str(log),'scope':'Actual compiled app Java exporters on JVM. Android Canvas pixel rendering, OS Save As/share UI and phone not exercised.','modelsRun':False}
(b/'java-formats-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False));print(log.read_text(encoding='utf8',errors='replace'));assert p.returncode==0
