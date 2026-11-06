from pathlib import Path
import json,re,hashlib,xml.etree.ElementTree as ET,zipfile,subprocess
from PIL import Image
import fitz
from pypdf import PdfReader
from docx import Document
from openpyxl import load_workbook
b=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-material-exports052')
root=max((p for p in b.glob('native-files-*') if (p/'manifest.json').exists()),key=lambda p:p.stat().st_mtime)
manifest=json.loads((root/'manifest.json').read_text(encoding='utf8'));rows=[]
compact=lambda t:re.sub(r'\s+','',t)
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
for item in manifest:
    p=root/item['file'];body=item['selectedText'];title=item['title']
    plain=[re.sub(r'^(?:#{1,6}|>)\s?','',line).strip() for line in body.splitlines() if line.strip()]
    result={'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    if p.suffix in ['.txt','.md']:assert p.read_text(encoding='utf8')==body
    elif p.suffix=='.docx':
        paragraphs=[para.text for para in Document(p).paragraphs];assert paragraphs[0]==title;assert paragraphs[1:]==plain
    elif p.suffix=='.xlsx':
        wb=load_workbook(p,data_only=False);sheet=wb.active;assert sheet['B2'].value==title
        assert [sheet.cell(i,2).value or '' for i in range(3,sheet.max_row+1)]==body.splitlines()
        assert all(cell.data_type!='f' for row in sheet for cell in row);wb.close()
    elif p.suffix=='.mm':
        values=[n.attrib['TEXT'] for n in ET.parse(p).iter('node')];expected=[title]
        for line in body.splitlines():
            if not line.strip():continue
            visual=line.lstrip().removeprefix('> ')
            expected.append(re.sub(r'^#{1,6}\s','',visual).strip() if re.match(r'^#{1,6}\s',visual) else line.strip())
        assert values==expected,(p,values,expected)
    elif p.suffix=='.pdf':
        pdf=fitz.open(p);extract='\n'.join(page.get_text() for page in pdf);second='\n'.join(page.extract_text() or '' for page in PdfReader(p).pages)
        for text in [extract,second]:
            joined=compact(text);assert compact(title) in joined;cursor=0
            for line in plain:
                pos=joined.find(compact(line),cursor);assert pos>=0,(p.name,line);cursor=pos+len(compact(line))
        result['pages']=len(pdf);result['twoIndependentReadersExactCharacters']=True;pdf.close()
    elif p.suffix=='.pptx':
        with zipfile.ZipFile(p) as z:
            names=sorted([name for name in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',name)],key=lambda name:int(re.search(r'(\d+)\.xml$',name)[1]))
            titles=[];paragraphs=[]
            for name in names:
                slide=ET.fromstring(z.read(name))
                for shape in slide.findall('.//p:sp',ns):
                    name=shape.find('p:nvSpPr/p:cNvPr',ns).get('name')
                    texts=[''.join(p.itertext()) for p in shape.findall('.//a:t',ns)]
                    if name=='标题':titles+=texts
                    elif name=='保存的正文':paragraphs+=texts
            for line in body.splitlines():
                visual=line.lstrip().removeprefix('> ')
                if not visual.strip():continue
                heading=re.match(r'^#{1,6}\s+(.*)',visual)
                value=heading[1] if heading else visual
                haystack=''.join(titles) if heading else ''.join(paragraphs)
                assert compact(value) in compact(haystack),(p.name,value)
            assert compact(title) in compact(''.join(titles))
            assert not any(name.startswith('ppt/media/') for name in z.namelist()),'Text must stay editable'
            result.update(slides=len(names),savedTextAndCitationsRetained=True,editableTextShapes=True)
    elif p.suffix=='.png':
        with Image.open(p) as image:
            assert image.format=='PNG';width,height=image.size;image.verify()
        assert width<=4096 and height<=12000 and width*height<=24_000_000
        result.update(width=width,height=height,visualReview='SEPARATE_IMAGE_INSPECTION_REQUIRED')
    else:raise AssertionError(p)
    assert b'UNSELECTED_PRIVATE_MATERIAL' not in p.read_bytes();result['passed']=True;rows.append(result)
srt=(root/'transcript.srt').read_text(encoding='utf8');assert '00:00:00,000 --> 00:00:04,000' in srt and '尚未确认采购' in srt and 'The purchase' not in srt
report={'status':'ALL_SELECTED_CONTENT_FILES_READ_AND_CONTENT_CHECKED','sourceDirectory':str(root),'files':rows,'srtTimingAndScopePassed':True,'powerPointApplicationUsed':False,'modelsRun':False,'ownerDataUsed':False}
(b/'document-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'status':report['status'],'files':len(rows),'sourceDirectory':str(root)},ensure_ascii=False))
