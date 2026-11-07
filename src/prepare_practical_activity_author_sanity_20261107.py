"""Author fixtures check packaging vs meeting-domain mismatch; not qualification."""
from pathlib import Path
from datetime import datetime
import hashlib,json,urllib.request,wave
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';parent=B/'practical-target-activity-r1';C=parent/'author-sanity';C.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert (parent/'review.json').exists() and not (C/'protocol.json').exists()
tree=read(B/'practical-ps4-local-presence-r1/published-nomo-tree.json');files={r['path']:r for r in tree['tree']};E=Path('E:/CodexData/Companion/.model-cache/nomo-target-activity-20261107/author-examples');E.mkdir(exist_ok=True);receipts=[]
for name in ['enroll.wav','test.wav','README.md']:
    item=files['examples/'+name];url='https://raw.githubusercontent.com/tuya/nomo-pvad/cb828468d183424fd574984f00b3ffbcce0be9bc/examples/'+name
    file=(C/'author-examples-README.md') if name.endswith('.md') else E/name
    if not file.exists():
        with urllib.request.urlopen(url,timeout=15) as response:raw=response.read()
        assert len(raw)==item['size'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['sha'];file.write_bytes(raw)
    raw=file.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['sha'];receipts.append({'file':str(file),'gitBlobSha1':item['sha'],'sha256':sha(file),'size':len(raw)})
metadata={}
for name in ['enroll','test']:
    file=E/(name+'.wav')
    with wave.open(str(file),'rb') as stream:
        assert stream.getframerate()==16000 and stream.getnchannels()==1 and stream.getsampwidth()==2;metadata[name]={'file':str(file),'samples':stream.getnframes(),'seconds':stream.getnframes()/16000}
anchors=[{'meeting':'AUTHOR_COMPATIBILITY_ONLY','speaker':0,'audio':str(E/'enroll.wav'),'audioSha256':sha(E/'enroll.wav'),'audioSeconds':metadata['enroll']['seconds']}]
cases=[]
for name in ['enroll','test']:
    m=metadata[name];cases.append({'id':'author-'+name,'meeting':'AUTHOR_COMPATIBILITY_ONLY','audio':m['file'],'audioSha256':sha(m['file']),'startSample':0,'endSample':m['samples'],'audioSeconds':m['seconds'],'allAnonymousTargets':[0]})
for name in ['model-ready.json','gpu-feature-numeric-proof.json']:(C/name).write_bytes((parent/name).read_bytes())
atomic_json(C/'audio-only.json',cases);atomic_json(C/'automatic-enrollments.json',anchors)
source=R/'model-research/src/practical_target_activity_worker_20261107.py';assert sha(source)==read(parent/'protocol.json')['workerSourceSha256']
text=source.read_text(encoding='utf8');old="C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1')";new="C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1/author-sanity')";assert text.count(old)==1
worker=source.with_name('practical_activity_author_sanity_worker_20261107.py');assert not worker.exists();worker.write_text(text.replace(old,new),encoding='utf8')
P=read(parent/'protocol.json');P.update(state='AUTHOR_FACTORY_COMPATIBILITY_ONLY_NOT_MEETING_QUALIFICATION',workerSourceSha256=sha(worker),audioOnlySha256=sha(C/'audio-only.json'),enrollmentPlanSha256=sha(C/'automatic-enrollments.json'),modelReadySha256=sha(C/'model-ready.json'),gpuFeatureProofSha256=sha(C/'gpu-feature-numeric-proof.json'),
    scope='Same candidate after frozen real-meeting rejection. Check author-provided self-enrollment and mixed test fixture to distinguish gross packaging/semantic failure from meeting-domain mismatch. No threshold or model tuning; do not count this as new meeting evidence or erase the failed13-clip result.',
    generatedWorkerFrom={'sourceSha256':sha(source),'onlySourceChange':'Dedicated fixture control directory; model/loader/frontend and inference code identical.'})
atomic_json(C/'protocol.json',P);atomic_json(C/'fixture-source.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'files':receipts,'metadata':metadata,'authorFixtureIsNotRealMeetingAcceptance':True})
print(json.dumps({'state':'AUTHOR_FIXTURES_PREPARED','metadata':metadata,'description':(C/'author-examples-README.md').read_text(encoding='utf8')},ensure_ascii=False))
