"""Actual acknowledged/cancelled/restarted task results: public sources only."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,re,shlex,subprocess,time,xml.etree.ElementTree as ET
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent.parent;O=C/'android131'
P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone131')
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app';QA='0a2cc0ac-149a-4688-8ff8-3180d987144a'
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
source=(R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8');tree=ast.parse(source)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['adb','version','hashes']],type_ignores=[]),'retained-phone-read-primitives','exec'))
assert version()==131
assert json.loads(adb(['shell','run-as',PKG,'cat','files/companion-library-index.json']))['activeId']==QA
final=json.loads((O/'editing-control-final.json').read_text(encoding='utf8'));assert final['completedUniqueNewKeys']==64
keys=json.loads((O/'editing-new-keys.json').read_text())['keys'];assert len(keys)==len(set(keys))==64
base=json.loads((O/'editing-public-baseline.json').read_text(encoding='utf8'));originals={r['key'] for r in base['sourceRows']};old=hashes((P/'before-install.sha256').read_text());cache={}
def audio(key):
 assert key in originals or key in keys;assert re.fullmatch('[0-9a-f]{64}:1:1',key)
 if key in cache:return cache[key]
 folder='files/companion-recordings-'+QA+'/import-'+hashlib.sha256(key.encode()).hexdigest()
 def get(leaf):return adb(['exec-out','run-as',PKG,'cat',folder+'/'+leaf],binary=True)
 raw=get('import.json');meta=json.loads(raw);assert meta['key']==key;pcm=b''
 for i,part in enumerate(meta['parts']):
  wav=get(f'part-{i:08d}.wav');assert len(wav)==44+part['samples']*2 and hashlib.sha256(wav).hexdigest()==part['sha256'];assert int.from_bytes(wav[40:44],'little')==part['samples']*2
  if folder+f'/part-{i:08d}.wav' in old:assert hashlib.sha256(wav).hexdigest()==old[folder+f'/part-{i:08d}.wav']
  pcm+=wav[44:]
 original=get('original.audio');assert hashlib.sha256(original).hexdigest()==meta['originalSha256'] and len(original)==meta['originalBytes']
 for leaf,value in [('import.json',raw),('original.audio',original)]:
  if folder+'/'+leaf in old:assert hashlib.sha256(value).hexdigest()==old[folder+'/'+leaf]
 binding=hashlib.sha256(hashlib.sha256(raw).digest()).hexdigest();identity='Companion canonical edit source v1\n'+key+'\n'+binding+'\n16000\n'+str(meta['samples'])+'\n'+''.join(p['sha256']+':'+str(p['samples'])+'\n' for p in meta['parts']);identity=hashlib.sha256(identity.encode()).hexdigest()
 assert len(pcm)==meta['samples']*2;cache[key]=(meta,pcm,identity);return cache[key]
verified=[]
for key in keys:
 meta,pcm,_=audio(key);provenance=meta['derivation'];plan=provenance['plan'];assert plan['frames']==meta['samples'];expected=b'';offset=0
 for clip in plan['slices']:
  source,raw,identity=audio(clip['sourceKey']);assert clip['sourceKey'] in originals and clip['sourceIdentity']==identity
  a,b=clip['startFrame'],clip['endFrame'];assert 0<=a<b<=source['samples'] and clip['outputStartFrame']==offset;offset+=b-a;assert clip['outputEndFrame']==offset;expected+=raw[a*2:b*2]
 assert pcm==expected and len(pcm)==offset*2;verified.append({'key':key,'frames':offset,'pcmSha256':hashlib.sha256(pcm).hexdigest()})
preferences=ET.fromstring(adb(['exec-out','run-as',PKG,'cat','shared_prefs/companion-file-import.xml'],binary=True));record=json.loads(next(n.text for n in preferences if n.tag=='string' and n.attrib.get('name')=='job'))
last=json.loads((O/'editing-crash-retried.json').read_text())['status'];assert record['id']==last['id'] and record['state']=='complete' and not record['running'];assert re.fullmatch(r'\.companion-audio-import-[0-9a-f-]{36}',record['stage']);adb(['shell','run-as',PKG,'test','!','-e','files/'+record['stage']])
assert [r['key'] for r in record['request']['outputs']]==[r['key'] for r in last['outputs']]
receipt=O/'editing-control-pcm.json';assert not receipt.exists();save(receipt,{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ACTUAL_PHONE_ALL_64_CANCEL_AND_RESTART_RETRIED_OUTPUTS_PCM_SOURCE_IDENTITY_EXACT','outputs':verified,'acknowledgedJobAndSameKeysDurablyRetained':True,'knownLastOwnedStageRetired':True,'existingPublicSourceFilesMatchPreinstallHashes':True,'ownerPrivateRecordingContentRead':False,'modelsRun':False,'qualificationLimit':'Ordinary cancellation was observed before any piece committed; exact commit-phase click timing was not captured. Process interruption recovered three committed pieces and completed only pending keys.'});print(json.dumps({'state':'ALL64_RETRIED_PCM_AND_SOURCE_IDENTITIES_EXACT','knownLastStageRetired':True,'originalPublicSourcesUnchanged':True}))
