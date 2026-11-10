from pathlib import Path
from datetime import datetime
import hashlib,json,re,shlex,subprocess,zipfile,xml.etree.ElementTree as ET
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone122');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
def shell(*args):return subprocess.check_output([str(A),'-s','d6bd213d','shell',' '.join(shlex.quote(str(a)) for a in args)],text=True,encoding='utf8')
def inventory(identity):
 roots=['files/companion-'+kind+'-'+identity for kind in ['recordings','meetings']];raw=shell('run-as','com.denzic.companion.app','sh','-c','find '+' '.join(shlex.quote(r) for r in roots)+' -type f -print0 | xargs -0 -r sha256sum');found={}
 for line in raw.splitlines():
  digest,name=line.split(None,1)
  for kind,base in zip(['recordings','meetings'],roots):
   if name.startswith(base+'/'):found[kind+'/'+name[len(base)+1:]]=digest
 return found
proof=json.loads((C/'android123/restored-ui-result.json').read_text());original=inventory('0a2cc0ac-149a-4688-8ff8-3180d987144a');restored=inventory(proof['restoredLibraryId']);assert original==restored,'Restored imported originals/results differ'
archive=P/'Companion-public-import-backup-123.zip'
with zipfile.ZipFile(archive) as z:
 for name,digest in original.items():
  with z.open(name) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==digest,name
 names=z.namelist();assert not any(any(part in name for part in ['shared_prefs/','companion-models/','keystore']) for name in names)
fixtures={f['name']:f for f in json.loads((C/'public-media.json').read_text())['fixtures']};matches=[]
for row in proof['imports']:
 folder='import-'+hashlib.sha256(row['key'].encode()).hexdigest();base='files/companion-recordings-'+proof['restoredLibraryId']+'/'+folder;manifest=json.loads(shell('run-as','com.denzic.companion.app','cat',base+'/import.json'));fixture=fixtures[manifest['name']];assert original['recordings/'+folder+'/original.audio']==fixture['sha256']==manifest['originalSha256'];assert fixture['bytes']==manifest['originalBytes'];matches.append({'file':manifest['name'],'bytes':manifest['originalBytes'],'sha256':manifest['originalSha256']})
source=json.loads((P/'public-export-source.json').read_text());word=P/'Companion-public-import-123.docx'
with zipfile.ZipFile(word) as z:xml=ET.fromstring(z.read('word/document.xml'));text=''.join(xml.itertext())
normal=lambda t:re.sub(r'\s+','',t)
assert normal(source['transcript']) in normal(text),'Word lost imported transcript text'
srt=P/'Companion-public-import-123.srt';body=srt.read_text(encoding='utf-8-sig');blocks=re.split(r'\r?\n\s*\r?\n',body.strip());times=[];spoken=[]
for block in blocks:
 lines=block.splitlines();assert len(lines)>=3 and re.fullmatch(r'\d+',lines[0]);m=re.fullmatch(r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})',lines[1]);assert m;v=list(map(int,m.groups()));start=((v[0]*60+v[1])*60+v[2])*1000+v[3];end=((v[4]*60+v[5])*60+v[6])*1000+v[7];assert 0<=start<end<=90001;times.append((start,end));spoken.append(''.join(lines[2:]))
assert len(times)==6 and normal(''.join(spoken))==normal(source['transcript']),'SRT lost recognized text or time windows'
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PUBLIC_IMPORTED_ORIGINALS_RESULTS_BACKUP_RESTORE_AND_DOCUMENT_BYTES_VERIFIED','savedAndRestoredFilesIdentical':len(original),'originalMediaByteIdentical':matches,'backupSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'backupBytes':archive.stat().st_size,'wordSha256':hashlib.sha256(word.read_bytes()).hexdigest(),'wordRetainsWholeImportedTranscript':True,'srtSha256':hashlib.sha256(srt.read_bytes()).hexdigest(),'srtWindows':len(times),'srtRetainsWholeRecognizedText':True,'credentialsOrModelsInBackup':False,'ownerDataUsed':False};(C/'android123/content-bytes-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record,ensure_ascii=False))
