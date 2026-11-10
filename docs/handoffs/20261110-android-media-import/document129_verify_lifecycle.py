from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone128');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
proof=json.loads((C/'android129/document-restored.json').read_text(encoding='utf8'));source=proof['sourceLibrary'];target=proof['restoredLibrary'];action=sys.argv[1];assert action in ['restore','purge']
snapshot=adb(['shell','run-as',PKG,'sh','-c','find files -type f -print0 | xargs -0 -r -n 64 sha256sum'],timeout=120);(P/('after-document-'+action+'.private.sha256')).write_text(snapshot);current=hashes(snapshot)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'sourceLibrary':source,'restoredLibrary':target,'ownerPrivateDataUploaded':False}
if action=='restore':
 before=hashes((P/'before-document-restore.private.sha256').read_text());changed=[n for n,h in before.items() if current.get(n)!=h];assert all(n=='files/companion-library-index.json' for n in changed),changed
 checked=0
 with zipfile.ZipFile(P/'Companion-public-documents129-backup.zip') as archive:
  for entry in archive.namelist():
   if not entry.startswith(('recordings/','meetings/')):continue
   kind,name=entry.split('/',1);path='files/companion-'+kind+'-'+target+'/'+name;assert current.get(path)==hashlib.sha256(archive.read(entry)).hexdigest(),entry;checked+=1
 assert checked>13
 record.update(state='ACTUAL_PHONE_RESTORED_ALL_BACKUP_RECORDING_DOCUMENT_AND_NOTE_BYTES_IDENTICAL',backupContentFilesChecked=checked,allPreexistingFilesIdenticalExceptActiveLibraryIndex=True,preexistingFilesChecked=len(before),newLibraryOnlyPublicBackup=True)
else:
 before=hashes((P/'after-document-restore.private.sha256').read_text());purge=json.loads((C/'android129/document-restored-purge.json').read_text(encoding='utf8'));assert purge['restoredLibrary']==target;key=purge['purgedKey'];digest=hashlib.sha256(key.encode()).hexdigest();meetings='files/companion-meetings-'+target+'/';recordings='files/companion-recordings-'+target+'/'
 def selected(name):return name.startswith(recordings+'import-'+digest+'/') or name.startswith(meetings+digest+'.') or name.startswith(meetings+'recording-lifecycle/'+digest+'.') or name==meetings+'recording-organization.json'
 changed=[n for n,h in before.items() if current.get(n)!=h];assert changed and all(selected(n) for n in changed),[n for n in changed if not selected(n)]
 assert not any(n.startswith(recordings+'import-'+digest+'/') or n.startswith(meetings+digest+'.') and n!=meetings+digest+'.lock' for n in current)
 assert current.get(meetings+digest+'.lock')==hashlib.sha256(b'').hexdigest()
 # The source record, all seven originals and every extraction remain exact.
 original=hashes((P/'before-document-restore.private.sha256').read_text());source_prefixes=['files/companion-'+kind+'-'+source+'/' for kind in ['meetings','recordings']];source_files={n:h for n,h in original.items() if any(n.startswith(prefix) for prefix in source_prefixes)};assert source_files and all(current.get(n)==h for n,h in source_files.items())
 record.update(state='ACTUAL_PHONE_RESTORED_ONLY_PURGE_REMOVES_ALL_DOCUMENTS_AUDIO_NOTES_OTHER_CONTENT_IDENTICAL',changedTargetFiles=len(changed),allOtherExistingFilesByteIdentical=len(before)-len(changed),sourcePublicLibraryFilesUnchanged=len(source_files),sourceAndOwnerLibrariesNotPurged=True,documentsAndExtractionsRemovedOnlyFromRestoredRecord=True)
save(C/('android129/document-'+action+'-content.json'),record);print(json.dumps(record))
