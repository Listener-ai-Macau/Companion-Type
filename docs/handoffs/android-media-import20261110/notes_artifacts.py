from pathlib import Path
import ast,hashlib,json,os,re,shlex,subprocess,time,zipfile,xml.etree.ElementTree as ET
from datetime import datetime
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone124');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
names=['Companion-public-notes124.zip','Companion-public-notes124.docx','Companion-public-notes-backup124.zip'];paths={}
for name in names:
 remote='/sdcard/Download/'+name;assert name.startswith('Companion-public-notes');digest=adb(['shell','sha256sum',remote]).split()[0];adb(['pull',remote,P/name]);assert sha(P/name)==digest;paths[name]=remote
save(P/'export-paths.json',paths)
with zipfile.ZipFile(P/names[0]) as z:
 images=[name for name in z.namelist() if name.startswith('images/')];assert len(images)==1;assert z.read(images[0])==(P/'Companion-Public-Whiteboard124.png').read_bytes();notes=json.loads(z.read('备注来源.json'));assert len(notes['entries'])==2 and notes['entries'][0]['atMs']==12000 and notes['entries'][1]['atMs']==25000
 html=z.read('打开阅读.html').decode();assert '公开验收已核对：周二复核12000元预算，负责人 Alex。' in html and '公开白板资料' in html and images[0] in html;assert '人类面临的机遇与挑战' not in html # selection contains notes, not hidden transcript
 portable={'originalImageSha256':hashlib.sha256(z.read(images[0])).hexdigest(),'notes':2,'timePointsMs':[12000,25000],'offlineHtml':True,'onlySelectedNotes':True}
with zipfile.ZipFile(P/names[1]) as z:
 xml=ET.fromstring(z.read('word/document.xml'));text=''.join(xml.itertext());assert '公开验收已核对' in text and '12000' in text and '00:00:12' in text and 'Companion-Public-Whiteboard124.png' in text and '人工补充' in text
with zipfile.ZipFile(P/names[2]) as z:
 files=z.namelist();ctx=[name for name in files if name.endswith('.context.json')];images=[name for name in files if '.context-' in name and name.endswith('.png')];assert len(ctx)==1 and len(images)==1;env=json.loads(z.read(ctx[0]));assert hashlib.sha256(env['body'].encode()).hexdigest()==env['sha256'];stored=json.loads(env['body']);assert stored['entries']==notes['entries'];assert z.read(images[0])==(P/'Companion-Public-Whiteboard124.png').read_bytes();assert len([name for name in files if name.endswith('/original.audio')])==4
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'SAVED_PUBLIC_NOTES_ZIP_DOCX_BACKUP_BYTES_VERIFIED','portable':portable,'wordContainsSavedTextTimeImageCaption':True,'backupContainsFourOriginalMediaAndExactNotesImage':True,'files':[{'name':name,'bytes':(P/name).stat().st_size,'sha256':sha(P/name)} for name in names],'ownerPrivateDataUsed':False};save(C/'android124/saved-artifacts.json',record);print(json.dumps(record,ensure_ascii=False))
