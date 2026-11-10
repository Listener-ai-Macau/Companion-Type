"""Read only declared public QA source/derived files; verify actual phone PCM.
No recording export, cloud, model, microphone or device access.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent.parent;O=C/'android130'
P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone130')
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
def save(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
s=(R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8');t=ast.parse(s)
exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name in ['adb','version','hashes']],type_ignores=[]),'retained-phone-read-primitives','exec'))
assert version()==130
baseline=json.loads((O/'editing-public-baseline.json').read_text(encoding='utf8'));QA=baseline['libraryId'];assert QA=='0a2cc0ac-149a-4688-8ff8-3180d987144a'
index=json.loads(adb(['shell','run-as',PKG,'cat','files/companion-library-index.json']));assert index['activeId']==QA
receipts={name:json.loads((O/('editing-'+name+'.json')).read_text(encoding='utf8')) for name in ['trim','split','merge','cancel-splits']}
allowed={r['key'] for r in baseline['sourceRows']};allowed.update(o['key'] for r in receipts.values() for o in r['status']['outputs'])
old=hashes((P/'before-install.sha256').read_text());cache={};verified=[]
def audio(key):
 assert key in allowed and re.fullmatch('[0-9a-f]{64}:1:1',key)
 if key in cache:return cache[key]
 folder='files/companion-recordings-'+QA+'/import-'+hashlib.sha256(key.encode()).hexdigest()
 def get(leaf):return adb(['exec-out','run-as',PKG,'cat',folder+'/'+leaf],binary=True)
 raw=get('import.json');meta=json.loads(raw);assert meta['key']==key
 data=b''
 for i,part in enumerate(meta['parts']):
  wav=get(f'part-{i:08d}.wav');assert len(wav)==44+part['samples']*2 and hashlib.sha256(wav).hexdigest()==part['sha256'];assert wav[:4]==b'RIFF' and wav[8:12]==b'WAVE' and int.from_bytes(wav[40:44],'little')==part['samples']*2
  leaf=folder+f'/part-{i:08d}.wav'
  if leaf in old:assert hashlib.sha256(wav).hexdigest()==old[leaf]
  data+=wav[44:]
 assert len(data)==meta['samples']*2
 original=get('original.audio');assert len(original)==meta['originalBytes'] and hashlib.sha256(original).hexdigest()==meta['originalSha256']
 for leaf,value in [('import.json',raw),('original.audio',original)]:
  if folder+'/'+leaf in old:assert hashlib.sha256(value).hexdigest()==old[folder+'/'+leaf]
 cache[key]=(meta,data);return meta,data
def check_output(key):
 meta,pcm=audio(key);provenance=meta['derivation'];plan=provenance['plan'];assert plan['schema']==1 and plan['sampleRate']==16000 and plan['frames']==meta['samples']
 expected=b'';end=0
 for clip in plan['slices']:
  source,raw=audio(clip['sourceKey']);a,b=clip['startFrame'],clip['endFrame'];assert 0<=a<b<=source['samples'] and clip['outputStartFrame']==end
  expected+=raw[a*2:b*2];end+=b-a;assert clip['outputEndFrame']==end
 assert pcm==expected and end==plan['frames'];verified.append({'key':key,'frames':end,'pcmSha256':hashlib.sha256(pcm).hexdigest(),'slices':plan['slices']})
 return plan
split=receipts['split'];source,pcm=audio(split['sourceKey']);plans=[check_output(o['key']) for o in split['status']['outputs']];assert sum(p['frames'] for p in plans)==source['samples'];assert plans[-1]['slices'][-1]['endFrame']==source['samples'];assert b''.join(audio(o['key'])[1] for o in split['status']['outputs'])==pcm
merge=receipts['merge'];plan=check_output(merge['status']['outputs'][0]['key']);assert plan['frames']==128000 and [s['sourceKey'] for s in plan['slices']]==[s['key'] for s in merge['sources']]
cancel=receipts['cancel-splits'];assert cancel['status']['state']=='complete' and len(cancel['status']['outputs'])==32
for out in cancel['status']['outputs']:check_output(out['key'])
assert len({v['key'] for v in verified})==len(verified)
result=O/'editing-split-merge-pcm.json';assert not result.exists()
save(result,{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ACTUAL_PHONE_SPLIT_TAIL_AND_ORDERED_MULTI_SOURCE_PCM_BYTE_EXACT','splitOriginalFrames':source['samples'],'splitOutputFrames':[p['frames'] for p in plans],'allActualOutputs':verified,'existingPublicOriginalMetadataMediaAndPcmComparedWithPreinstallHashes':True,'cancelAttemptDidNotEstablishCancellationQualification':True,'readScope':'Declared existing public QA source files and newly created outputs only; no Owner recording content.','modelsRun':False})
print(json.dumps({'state':'PHONE_NATIVE_PCM_AND_PROVENANCE_EXACT','verifiedOutputs':len(verified),'splitOutputFrames':[p['frames'] for p in plans],'mergeFrames':plan['frames']}))
