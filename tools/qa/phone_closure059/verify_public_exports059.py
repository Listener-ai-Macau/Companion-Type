from pathlib import Path
import json,subprocess,zipfile,xml.etree.ElementTree as ET,re
import pypdf
from PIL import Image
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059');D=C/'saved';W=Path(__file__).parent
def norm(value):return ''.join(value.split())
required=['追加20%的费用尚未批准。','小陈在11月8日前核对报价','公开虚构补充','公开虚构跟进材料','保存时的原文依据','未完成','<A&B>','😀','# literal **keep**']
word_version=next(version for version in [62,61,59] if (D/f'QA{version:03d}-all.docx').exists())
word_path=D/f'QA{word_version:03d}-all.docx'
texts={'txt':(D/'QA059-all.txt').read_text(encoding='utf8'),'markdown':(D/'QA059-all.md').read_text(encoding='utf8'),
    'pdf':'\n'.join(p.extract_text() for p in pypdf.PdfReader(D/'QA059-all.pdf').pages)}
for extension,kind,pattern in [('docx','word',r'word/document.xml'),('pptx','pptx',r'ppt/slides/slide\d+.xml'),('xlsx','xlsx',r'xl/worksheets/sheet\d+.xml')]:
    path=word_path if extension=='docx' else D/('QA059-all.'+extension)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        roots=[ET.fromstring(z.read(n)) for n in z.namelist() if re.fullmatch(pattern,n)]
        assert roots
        if kind=='xlsx':assert not any(e.tag.endswith('}f') for root in roots for e in root.iter()),'Literal transcript formula was activated'
        texts[kind]='\n'.join(e.text or '' for root in roots for e in root.iter() if e.tag.endswith('}t'))
mm=ET.parse(D/'QA059-all.mm');texts['mindmap']='\n'.join(n.get('TEXT','') for n in mm.iter('node'))
rows=[]
for kind,text in texts.items():
    for token in required:assert norm(token) in norm(text),(kind,token)
    rows.append({'format':kind,'requiredContentPreserved':True,'normalizedTextCharacters':len(norm(text))})
png=D/'QA059-all.png'
with Image.open(png) as im:size=im.size;im.verify()
rows.append({'format':'png','pixels':size,'fullFileDecodes':True,'visualReview':'Full public map inspected; no clipped final node or unreadable/missing glyph observed. Not OCR-based accuracy.'})
framework=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319');qa=Path('E:/CodexData/Companion/.build-cache/exports052-qa')
cmd=[str(framework/'csc.exe'),'/nologo','/target:exe','/out:'+str(qa/'ValidateDocuments059.exe'),'/reference:'+str(qa/'DocumentFormat.OpenXml.dll'),'/reference:'+str(framework/'WPF/WindowsBase.dll'),'/reference:'+str(framework/'System.Web.Extensions.dll'),str(W/'ValidateDocuments059.cs')]
p=subprocess.run(cmd,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stdout+p.stderr
p=subprocess.run([str(qa/'ValidateDocuments059.exe'),*[str(word_path if x=='docx' else D/('QA059-all.'+x)) for x in ['docx','xlsx','pptx']]],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
(C/'openxml-validation.json').write_text(p.stdout,encoding='utf8');assert p.returncode==0,p.stdout+p.stderr
record={'result':'PASS_ACTUAL_PUBLIC_CONTENT_AND_OPENXML_SCHEMA','wordAndroidVersion':word_version,'otherFormatsAndroidVersion':59,'formats':rows,'microsoftOpenXml':json.loads(p.stdout),
    'pdfPages':len(pypdf.PdfReader(D/'QA059-all.pdf').pages),'pdfVisualReview':'Both rendered pages inspected: headings, negation, source notices, Unicode, page breaks/footer legible; no clipping/overlap observed.',
    'realMeeting':False,'modelQualityClaim':False,'actualExternalOfficeViewerOpened':False}
(C/'content-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(record,ensure_ascii=False))
