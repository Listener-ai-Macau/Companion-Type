from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;D=Path('E:/CodexData/Companion/.build-cache/document-context20261110/format-fixtures');P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone128');ADB=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';folder='/sdcard/Download/Companion-public-documents128'
def adb(args,required=True):
 q=subprocess.run([str(ADB),'-s','d6bd213d',*map(str,args)],capture_output=True,timeout=30)
 if required:assert q.returncode==0,q.stderr.decode(errors='replace')[-1200:]
 return q
assert json.loads((R/'docs/product_backlog.json').read_text(encoding='utf-8'))['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold']['active']
assert adb(['shell','test','-e',folder],False).returncode!=0,'Only a fresh explicitly named public QA folder is allowed'
adb(['shell','mkdir',folder]);source=json.loads((D/'manifest.json').read_text());files=[]
for original,name in [('material.docx','Companion-public-公开补充材料128.docx'),('material.xlsx','Companion-public-公开预算草案128.xlsx'),('material.pptx','Companion-public-公开方案128.pptx'),('chinese.pdf','Companion-public-公开中文128.pdf'),('protected.pdf','Companion-public-有密码128.pdf'),('no-text.pdf','Companion-public-无文字128.pdf'),('material-gb.txt','Companion-public-中文编码128.txt')]:
 file=D/original;digest=hashlib.sha256(file.read_bytes()).hexdigest();assert digest==source[original]['sha256'];remote=folder+'/'+name;adb(['push',file,remote]);assert adb(['shell','sha256sum',remote]).stdout.decode().split()[0]==digest;files.append({'name':name,'original':original,'path':remote,'bytes':file.stat().st_size,'sha256':digest})
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ONLY_DECLARED_PUBLIC_DOCUMENT_FIXTURES_STAGED_ON_PHONE','folder':folder,'files':files,'ownerFilesOverwritten':False};(C/'android128/phone-document-fixtures.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Staged '+str(len(files))+' explicit public documents; all source and phone hashes match.')
