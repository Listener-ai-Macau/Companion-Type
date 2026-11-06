from pathlib import Path
import copy,hashlib,json,re,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path('E:/CodexData/Companion/.build-cache/device-phone055');F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/word062'
s=(R/'companion-android-device-closure055/apps/windows/src-tauri/src/backend/meeting_document_export.rs').read_text(encoding='utf8');footer=re.search(r'let footer=r#"(.*?)"#;',s,re.S).group(1).encode('utf8')
native=json.loads((F/'native-word062.json').read_text());lib=Path(native['library']).read_bytes();assert footer in lib
old=b'<w:rPr><w:sz w:val="18"/><w:color w:val="777777"/>';assert old not in lib
output=C/'word062/HOST_ONLY_EXPECTED_FOOTER_DIAGNOSTIC.docx'
with zipfile.ZipFile(C/'acceptance059/saved/QA061-all.docx') as before,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as after:
    for entry in before.infolist():after.writestr(copy.copy(entry),footer if entry.filename=='word/footer1.xml' else before.read(entry.filename))
p=subprocess.run(['E:/CodexData/Companion/.build-cache/exports052-qa/ValidateDocuments059.exe',str(output)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stdout+p.stderr
record={'scope':'CONTROLLED_HOST_DIAGNOSTIC_NOT_ACTUAL_ANDROID062_OUTPUT','nativeFooterBytesMatchCorrectedSource':True,'oldIncorrectFooterOrderAbsentFromNativeBinary':True,'microsoftOpenXml':json.loads(p.stdout),'actualPhoneWord062Acceptance':False,'diagnosticSha256':hashlib.sha256(output.read_bytes()).hexdigest()}
(F/'footer-source-check.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(record,ensure_ascii=False))
