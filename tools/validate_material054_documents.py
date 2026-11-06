from pathlib import Path
import subprocess,json,hashlib,zipfile,re,xml.etree.ElementTree as ET
from openpyxl import load_workbook
b=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-android-material-exports054')
run=Path(json.loads((b/'java-formats-result.json').read_text(encoding='utf8'))['output'])
qa=Path('E:/CodexData/Companion/.build-cache/exports052-qa');framework=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319')
exe=qa/'ValidateDocuments054.exe';dll=qa/'DocumentFormat.OpenXml.dll'
cmd=[str(framework/'csc.exe'),'/nologo','/out:'+str(exe),'/r:'+str(dll),'/r:'+str(framework/'WPF/WindowsBase.dll'),'/r:'+str(framework/'System.Web.Extensions.dll'),str(Path(__file__).parent/'ValidateDocuments054.cs')]
p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
p=subprocess.run([str(exe),str(run/'saved-material.pptx'),str(run/'saved-material.xlsx')],capture_output=True,text=True,encoding='utf8');(b/'openxml-schema.json').write_text(p.stdout,encoding='utf8');assert p.returncode==0,p.stdout+p.stderr
with zipfile.ZipFile(run/'saved-material.pptx') as z:
    names=sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml',n)),key=lambda n:int(re.search(r'(\d+)\.xml',n).group(1)))
    text=''.join(''.join(ET.fromstring(z.read(n)).itertext()) for n in names)
    assert text.count('The purchase has not been approved.')==34
    assert '未确认就不支付20%' in text and '# 原话不是标题' in text and '<A&B> 😀' in text
    for n in z.namelist():
        if n.endswith('.rels'):assert not any(e.attrib.get('TargetMode')=='External' for e in ET.fromstring(z.read(n)))
wb=load_workbook(run/'saved-material.xlsx',data_only=False);rows=list(wb.active.values);joined='\n'.join(str(c) for row in rows for c in row if c is not None)
assert '未确认就不支付20%' in joined and '<A&B> 😀' in joined and '=HYPERLINK(' in joined
assert all(cell.data_type!='f' for row in wb.active for cell in row)
mm=ET.parse(run/'saved-material.mm');assert any('# 原话不是标题'==n.attrib.get('TEXT') for n in mm.iter('node'))
result={'status':'ACTUAL_JAVA_EXPORTED_PPTX_XLSX_MM_CONTENT_AND_SCHEMA_PASSED','source':str(run),'slides':len(names),'xlsxRows':len(rows),'excelFormulaCells':0,'all34RepeatedSourceSentencesPreserved':True,'negationMoneyDeadlineCitationUnicodePreserved':True,'externalRelationships':False,'powerPointApplicationOpened':False,'androidPixelRenderCovered':False,'files':[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in [run/'saved-material.pptx',run/'saved-material.xlsx',run/'saved-material.mm']]}
(b/'document-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
