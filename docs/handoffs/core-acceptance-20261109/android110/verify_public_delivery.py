"""Verify actual system-saved and pasted public output, without backend substitutes."""
from pathlib import Path
from datetime import datetime
import hashlib,json,re,subprocess,zipfile,xml.etree.ElementTree as ET
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6')
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';PKG='com.denzic.companion.app'
def adb(args):
    r=subprocess.run([str(A),'-s','d6bd213d',*map(str,args)],capture_output=True);assert r.returncode==0,'Public output readback failed';return r.stdout
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
names=['Companion-QA111-shared-minutes.pdf','Companion-QA111-minutes.docx','Companion-QA111-minutes-and-transcript.txt']
files=[]
for name in names:
    target=P/name;adb(['pull','/sdcard/Download/'+name,target]);files.append({'filename':name,'bytes':target.stat().st_size,'sha256':sha(target)})
copied=adb(['shell','run-as',PKG,'ls','-t','cache/companion-shared']).decode().splitlines()[0].strip();assert re.fullmatch('[0-9a-f-]{36}',copied)
prefix='cache/companion-shared/'+copied+'/'
meta=json.loads(adb(['exec-out','run-as',PKG,'cat',prefix+'manifest.json']));assert meta['key']=='5055423131304d324d455421:f0110a:1100901'
expected=adb(['exec-out','run-as',PKG,'cat',prefix+'copy.txt']);assert hashlib.sha256(expected).hexdigest()==meta['copySha256']
received=(P/'pasted-public-text.txt').read_text(encoding='utf8').encode();assert received==expected,'Actual Android paste differs from product copy'
transcript=(C/'phone-d6/phone111-raw-transcript.txt').read_text(encoding='utf8')
saved=(P/names[2]).read_text(encoding='utf8');assert transcript in saved and transcript in received.decode()
with zipfile.ZipFile(P/names[1]) as doc:
    parsed=ET.fromstring(doc.read('word/document.xml'));text=''.join(parsed.itertext());assert '超市' in text and '待核对' in text and '洗衣液' in text
before=json.loads((C/'phone-d6/phone111-result-readback.json').read_text());active=json.loads((P/'active-public-library.private.json').read_text());raw=adb(['exec-out','run-as',PKG,'cat',active['prefix']+'.meeting'])
assert hashlib.sha256(raw).hexdigest()==before['meetingFileSha256'],'Paste verification altered saved transcript'
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'SYSTEM_SAVED_WORD_TXT_AND_LOCAL_PDF_SHARE_READBACK_ACTUAL_CLIPBOARD_PASTE_IDENTICAL','files':files,'clipboard':{'actualOrdinaryAndroidPaste':True,'bytes':len(received),'characters':len(received.decode()),'sha256':hashlib.sha256(received).hexdigest(),'matchesPreparedCopyBytes':True,'savedTranscriptUnchanged':True},'txtIncludesEntireSavedRawTranscript':True,'wordDocumentXmlReadable':True,'pdfShareRecipient':'Android system print spooler, Save as PDF; no printer job or contact message','pdfReprintedBytesMayDiffer':True,'qaRecipientInstallRejected':True,'systemSecuritySettingsChanged':False,'phonePhysicalAudioQualityQualified':False}
(C/'phone-d6/content-delivery111.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
