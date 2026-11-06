from pathlib import Path
p=Path(__file__).with_name('verify_public_exports059.py')
s=p.read_text(encoding='utf8')
s=s.replace("('docx','word',r'word/document.xml'),",'')
s=s.replace("['docx','xlsx','pptx']","['xlsx','pptx']")
s=s.replace("C/'content-verification.json'","C/'content-triage-other-formats.json'")
s=s.replace('PASS_ACTUAL_ANDROID059_EXPORTED_PUBLIC_CONTENT_AND_OPENXML_SCHEMA','PASS_OTHER_FORMATS_WORD_FAILED_SEPARATELY')
exec(compile(s,str(p),'exec'))
