"""Compile the actual backend and verify only the new range persistence path."""
from pathlib import Path
import hashlib,json,os,subprocess,sys

root=Path(__file__).resolve().parents[1]
base=root/'apps/android-backend/src'
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
classes=out/'classes';classes.mkdir()
java=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin')
api=Path('E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar')
sources=sorted((base/'main/java').rglob('*.java'))
test=base/'test/java/com/denzic/companion/mobile/RangeCheckpointJvmTest.java'
env=dict(os.environ,JAVA_TOOL_OPTIONS='-XX:ActiveProcessorCount=2 -Xmx384m')
for name,cmd in [('compile',[str(java/'javac.exe'),'--release','8','-encoding','UTF-8','-cp',str(api),'-d',str(classes),*map(str,sources),str(test)]),
                 ('range-checkpoint',[str(java/'java.exe'),'-cp',str(classes)+os.pathsep+str(api),'com.denzic.companion.mobile.RangeCheckpointJvmTest'])]:
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90)
    (out/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');print(name,p.returncode,p.stdout,p.stderr,flush=True);p.check_returncode()
changed=[base/'main/java/com/denzic/companion/mobile'/n for n in ['RangeCheckpoint.java','SegmentReceiver.java']]+[test,Path(__file__)]
(out/'result.json').write_text(json.dumps({'result':'PASS_RANGE_HOST_PERSISTENCE_AND_ACTUAL_RECEIVER_RECOVERY','sourceSha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in changed},'deviceAccessed':False,'installed':False,'speedQualified':False,'negotiatedRangeWireEnabled':False},indent=2)+'\n')
