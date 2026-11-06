from pathlib import Path
import hashlib,json,re,subprocess,zipfile,xml.etree.ElementTree as ET
import fitz,pypdf
from PIL import Image
G=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering')
F=G/'system-handoff';meta=json.loads((F/'session.json').read_text(encoding='utf8'));C=Path(meta['isolation'])
source=json.loads((C/'public-seed.json').read_text(encoding='utf8'))['transcriptText']
norm=lambda text:''.join(text.split())
items=[]
for folder,prefix,actual in [(G/'release-native','public-transcript',False),(F/'saved','Windows067-public-transcript',True)]:
 office=[folder/(prefix+'.'+ext) for ext in ['docx','xlsx','pptx'] if (folder/(prefix+'.'+ext)).exists()]
 validator=Path('E:/CodexData/Companion/.build-cache/exports052-qa/ValidateDocuments059.exe')
 run=subprocess.run([str(validator),*map(str,office)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
 assert run.returncode==0,run.stdout+run.stderr
 (F/(('actual' if actual else 'release')+'-openxml-schema.json')).write_text(run.stdout,encoding='utf8')
 texts={ext:(folder/(prefix+'.'+ext)).read_text(encoding='utf8') for ext in ['txt','md'] if (folder/(prefix+'.'+ext)).exists()}
 for ext in ['txt','md']:
  if ext in texts:assert texts[ext]=='## 录音文字\n\n'+source
 for ext,pattern in [('docx',r'word/document.xml'),('xlsx',r'xl/worksheets/sheet\d+.xml'),('pptx',r'ppt/slides/slide\d+.xml')]:
  if not (folder/(prefix+'.'+ext)).exists():continue
  with zipfile.ZipFile(folder/(prefix+'.'+ext)) as z:
   roots=[ET.fromstring(z.read(n)) for n in z.namelist() if re.fullmatch(pattern,n)]
   if ext=='xlsx':assert not any(n.tag.endswith('}f') for root in roots for n in root.iter())
   texts[ext]='\n'.join(n.text or '' for root in roots for n in root.iter() if n.tag.endswith('}t'))
 if (folder/(prefix+'.mm')).exists():texts['mm']='\n'.join(n.get('TEXT','') for n in ET.parse(folder/(prefix+'.mm')).iter('node'))
 pdf=folder/(prefix+'.pdf');texts['pdf']='\n'.join(p.extract_text() for p in pypdf.PdfReader(pdf).pages)
 for ext,text in texts.items():
  for token in ['11月8日前核对20%差额，尚未确认采购。','追加20%的费用尚未批准。','小陈在11月8日前核对报价。','# literal **keep** <A&B>','=HYPERLINK("https://example.invalid","literal")']:
   assert norm(token) in norm(text),(actual,ext,token)
  assert 'UNSELECTED_PRIVATE_MATERIAL' not in text
  p=folder/(prefix+'.'+ext);items.append({'actualSaveAs':actual,'format':ext,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'literalAndNegationPreserved':True})
 png=folder/(prefix+'.png')
 if png.exists():
  with Image.open(png) as im:dimensions=im.size;im.verify()
  items.append({'actualSaveAs':actual,'format':'png','fullImageDecodes':True,'dimensions':dimensions,'sha256':hashlib.sha256(png.read_bytes()).hexdigest()})
 if actual:
  doc=fitz.open(pdf)
  for index,page in enumerate(doc):page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(F/('actual-pdf-page-'+str(index+1)+'.png'))
def normalized(v):
 if isinstance(v,dict):return {k:normalized(x) for k,x in v.items() if x is not None}
 if isinstance(v,list):return [normalized(x) for x in v]
 return v
assert normalized(json.loads((C/'sessions.json').read_text(encoding='utf8')))==[normalized(json.loads((C/'public-seed.json').read_text(encoding='utf8')))]
actual_count=sum(1 for row in items if row['actualSaveAs'])
receipt={'state':'INSTALLED_WINDOWS067_ACTUAL_NATIVE_SAVE_AS_CONTENT_CHECKED','version':'0.1.67','files':items,'actualSaveAsFormats':actual_count,'releaseNativeFormats':8,'sourceContentPreserved':True,'officeSchemaErrors':0,'cancellation':json.loads((F/'actual-cancel.json').read_text(encoding='utf8')) if (F/'actual-cancel.json').exists() else None,'publicSyntheticFixture':True,'actualShareRecipientVerified':False,'modelsRun':False,'wholeProductQualified':False}
(F/'actual-content-result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in receipt.items() if k not in ['files','cancellation']},ensure_ascii=False))
