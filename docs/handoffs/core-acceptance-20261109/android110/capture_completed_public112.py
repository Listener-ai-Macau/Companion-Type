"""Verify durable results from the actual public phone meeting after repair."""
from pathlib import Path
from datetime import datetime
import hashlib,io,json,re,shlex,struct,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/'phone-d6';P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';PKG='com.denzic.companion.app'
def adb(args):
    result=subprocess.run([str(A),'-s','d6bd213d',*map(str,args)],capture_output=True);assert result.returncode==0,'Public result unavailable';return result.stdout
def read(path):return adb(['exec-out','run-as',PKG,'cat',path])
key='5055423131304d324d455421:f0110a:1100901';stem=hashlib.sha256(key.encode()).hexdigest()
index=json.loads(read('files/companion-library-index.json'));id=index['activeId'];assert re.fullmatch('[0-9a-f-]{36}',id)
meet=f'files/companion-meetings-{id}';recordings=f'files/companion-recordings-{id}';prefix=meet+'/'+stem
assert 'S_R004S03C01' in read(prefix+'.title').decode()
prior=json.loads((O/'phone111-result-readback.json').read_text());raw=read(prefix+'.meeting');assert hashlib.sha256(raw).hexdigest()==prior['meetingFileSha256']
minutes=read(prefix+'.minutes');assert hashlib.sha256(minutes).hexdigest()==prior['minutes']['fileSha256']
raw=read(meet+'/translations/'+stem+'.translation');assert hashlib.sha256(raw[:-32]).digest()==raw[-32:];stream=io.BytesIO(raw[:-32])
def integer():return struct.unpack('>i',stream.read(4))[0]
def string():
    size=integer();assert 0<=size<4*1024**2;return stream.read(size).decode('utf8')
assert integer()==0x43545231 and string()==key;language=string();revision=struct.unpack('>q',stream.read(8))[0];source=string();text=string();assert stream.read()==b''
assert language=='en' and revision==1 and hashlib.sha256(source.encode()).hexdigest()==prior['transcriptSha256'] and text.strip()
(O/'phone112-english-translation.txt').write_text(text,encoding='utf8')
materials=[]
for name in adb(['shell','run-as',PKG,'ls',meet+'/ai-materials']).decode().splitlines():
    assert re.fullmatch('[a-f0-9-]{36}\.json',name)
    material=json.loads(read(meet+'/ai-materials/'+name));assert material['ownerKey']==key
    items=material['result']['items'];assert items and not material['result']['incomplete']
    assert all(item['citation']['quote'] in source for item in items)
    materials.append({'id':material['id'],'title':material['title'],'items':len(items),'allQuotesFoundInActualPhoneTranscript':True,'sha256':hashlib.sha256(json.dumps(material,ensure_ascii=False,sort_keys=True).encode()).hexdigest()})
    (O/'phone111-saved-ai-material.json').write_text(json.dumps(material,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
command=['run-as',PKG,'find',recordings,meet,'-type','f','-exec','sha256sum','{}',';']
output=adb(['shell',shlex.join(command)]).decode();manifest={}
for line in output.splitlines():
    digest,path=line.split(None,1);path=path.strip();relative='recordings/'+path[len(recordings)+1:] if path.startswith(recordings+'/') else 'meetings/'+path[len(meet)+1:] if path.startswith(meet+'/') else None
    assert relative is not None and re.fullmatch('[0-9a-f]{64}',digest);manifest[relative]=digest
(O/'completed-library-manifest112.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
(P/'completed-public-library.private.json').write_text(json.dumps({'id':id,'meetings':meet,'recordings':recordings,'key':key,'stem':stem}))
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID112_FULL_PUBLIC_MEETING_TRANSLATED_SAVED_AND_AI_MATERIAL_REOPENED','versionCode':112,'translation':{'language':language,'sourceMatchesActualPhoneTranscript':True,'sourceRevision':revision,'sourceCharacters':len(source),'translationCharacters':len(text),'sha256':hashlib.sha256(text.encode()).hexdigest(),'fileSha256':hashlib.sha256(raw).hexdigest(),'allThreeChunksCompletedBeforeSave':True},'originalTranscriptAndMinutesUnchanged':True,'aiMaterials':materials,'durablePublicFiles':len(manifest),'accuracyDiagnosticReused':prior['chronologicalMixedCerDiagnostic'],'wholeProductQualified':False}
(O/'completed-public-result112.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
