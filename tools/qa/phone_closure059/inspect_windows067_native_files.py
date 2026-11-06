from pathlib import Path
import hashlib,json,re,subprocess,zipfile,xml.etree.ElementTree as ET
import fitz,pypdf
from PIL import Image
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering'
D=max((p for p in F.glob('native-files-*') if (p/'manifest.json').exists()),key=lambda p:p.stat().st_mtime)
office=[D/(kind+'.'+extension) for kind in ['transcript','material'] for extension in ['docx','xlsx','pptx']]
validator=Path('E:/CodexData/Companion/.build-cache/exports052-qa/ValidateDocuments059.exe')
run=subprocess.run([str(validator),*map(str,office)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
(F/'native-openxml-schema.json').write_text(run.stdout,encoding='utf8');assert run.returncode==0,run.stdout+run.stderr
norm=lambda value:''.join(value.split())
items=[]
for kind in ['transcript','material']:
 expected=['11月8日前核对20%差额，尚未确认采购。'] if kind=='transcript' else ['The purchase has not been approved.','原文依据：尚未确认采购。']
 texts={extension:(D/(kind+'.'+extension)).read_text(encoding='utf8') for extension in ['txt','md']}
 for extension,pattern in [('docx',r'word/document.xml'),('xlsx',r'xl/worksheets/sheet\d+.xml'),('pptx',r'ppt/slides/slide\d+.xml')]:
  with zipfile.ZipFile(D/(kind+'.'+extension)) as z:
   roots=[ET.fromstring(z.read(name)) for name in z.namelist() if re.fullmatch(pattern,name)]
   if extension=='xlsx':assert not any(node.tag.endswith('}f') for root in roots for node in root.iter())
   texts[extension]='\n'.join(node.text or '' for root in roots for node in root.iter() if node.tag.endswith('}t'))
 texts['mm']='\n'.join(node.get('TEXT','') for node in ET.parse(D/(kind+'.mm')).iter('node'))
 reader=pypdf.PdfReader(D/(kind+'.pdf'));texts['pdf']='\n'.join(page.extract_text() for page in reader.pages)
 for extension,text in texts.items():
  for token in expected:assert norm(token) in norm(text),(kind,extension,token)
  assert 'UNSELECTED_PRIVATE_MATERIAL' not in text
  path=D/(kind+'.'+extension);items.append({'case':kind,'format':extension,'contentPreserved':True,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 png=D/(kind+'.png')
 with Image.open(png) as image:size=image.size;image.verify()
 items.append({'case':kind,'format':'png','fullFileDecodes':True,'pixels':size})
 doc=fitz.open(D/(kind+'.pdf'))
 for index,page in enumerate(doc):page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(F/(kind+'-pdf-page-'+str(index+1)+'.png'))
record={'result':'CONTROLLED_NATIVE_SEMANTICS_AND_SIX_OPENXML_PACKAGES_PASSED','folder':str(D),'files':items,'schema':json.loads(run.stdout),'scope':'Actual compiled product source tests generated these outputs; this is not an OS SaveAs or actual share recipient result. Dedicated literal-prefix test also passed.','modelsRun':False,'realMeetingQualityClaim':False}
(F/'native-content-inspection.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'result':record['result'],'sourceCases':2,'fileFormatsPerCase':8,'openXmlErrors':sum(row['errors'] for row in record['schema'])},ensure_ascii=False))
