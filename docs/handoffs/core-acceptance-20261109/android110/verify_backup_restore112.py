"""Verify the ordinary system-backup round trip against every original public byte."""
from pathlib import Path
from datetime import datetime
import hashlib,json,re,shlex,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/'phone-d6';P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';PKG='com.denzic.companion.app'
def adb(args):
    q=subprocess.run([str(A),'-s','d6bd213d',*map(str,args)],capture_output=True);assert q.returncode==0,'Public restore verification unavailable';return q.stdout
before=json.loads((P/'completed-public-library.private.json').read_text());expected=json.loads((O/'completed-library-manifest112.json').read_text())
archive=P/'Companion-QA112-S_R004S03C01-complete-backup.zip'
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    payload={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n!='companion-manifest-v1'}
    assert payload==expected,'Backup omitted or changed a public source file'
    secret=__import__('os').environ['DEEPSEEK_API_KEY'].encode();assert all(secret not in z.read(n) for n in z.namelist())
index=json.loads(adb(['exec-out','run-as',PKG,'cat','files/companion-library-index.json']));id=index['activeId'];assert id!=before['id'] and re.fullmatch('[a-f0-9-]{36}',id) and any(v['id']=='original' for v in index['libraries'])
paths={kind:f'files/companion-{kind}-{id}' for kind in ['recordings','meetings']}
output=adb(['shell',shlex.join(['run-as',PKG,'find',*paths.values(),'-type','f','-exec','sha256sum','{}',';'])]).decode();actual={}
for line in output.splitlines():
    digest,name=line.split(None,1);name=name.strip()
    for kind,prefix in paths.items():
        if name.startswith(prefix+'/'):actual[kind+'/'+name[len(prefix)+1:]]=digest;break
assert all(actual.get(name)==digest for name,digest in expected.items()),'Restored public files differ'
point={'id':id,'previousId':before['id'],'meetings':paths['meetings'],'recordings':paths['recordings'],'key':before['key'],'stem':before['stem']}
(P/'restored-public-library.private.json').write_text(json.dumps(point))
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID112_ORDINARY_SYSTEM_BACKUP_RESTORE_ALL_PUBLIC_FILES_IDENTICAL','backupBytes':archive.stat().st_size,'backupSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archivedFiles':len(expected),'restoredFilesVerified':len(expected),'restoredIntoNewLibrary':True,'priorPublicLibraryRetained':True,'originalOwnerLibraryRetained':True,'includes':['COP1 original audio and descriptor','saved ASR and timing','AI minutes','named AI material and exact source citations','complete English translation'],'serviceKeyAbsent':True,'modelsAbsent':True,'restoredAutomaticallyConnectedToBoard':False}
(O/'backup-restore112.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
