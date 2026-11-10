"""Protect the exact candidate in the existing private draft and read bytes back."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys
C=Path(__file__).parent;kind=sys.argv[1];assert kind in ['android121']
O=C/kind;P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110/remote-readback');P.mkdir(exist_ok=True)
repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
def run(args):
    p=subprocess.run(args,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr.decode(errors='replace')[-1200:];return p.stdout
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
proof=json.loads((O/('build-result.json' if kind.startswith('android') else 'windows-verification.json')).read_text())
key='apk' if kind.startswith('android') else 'msi';binary=Path(proof[key]);digest=proof[key+'Sha256'];assert sha(binary)==digest
release=json.loads(run(['gh','release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft']
found=[a for a in release['assets'] if a['name']==binary.name]
if not found:
    run(['gh','release','upload',tag,str(binary),'--repo',repo])
    release=json.loads(run(['gh','release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft']
    found=[a for a in release['assets'] if a['name']==binary.name]
assert len(found)==1 and found[0]['digest']=='sha256:'+digest
asset=found[0];destination=P/binary.name;identity=asset['apiUrl'].rsplit('/',1)[1];assert identity.isdigit()
with destination.open('wb') as out:
    p=subprocess.run(['gh','api','repos/'+repo+'/releases/assets/'+identity,'-H','Accept: application/octet-stream'],stdout=out,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
assert p.returncode==0 and sha(destination)==digest
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'EXACT_PRIVATE_DRAFT_INSTALLER_READBACK_VERIFIED','sourceCommit':proof['sourceCommit'],'repo':repo,'tag':tag,'draft':True,'assetId':int(identity),'fileName':binary.name,key+'Sha256':digest,'bytes':binary.stat().st_size,'readbackByteIdentical':True,'published':False,'ownerPrivateDataUploaded':False}
(O/'remote-candidate-backup.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
