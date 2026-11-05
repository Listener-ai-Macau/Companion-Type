from pathlib import Path
import json,re,hashlib,xml.etree.ElementTree as ET
import fitz
from pypdf import PdfReader
from docx import Document
from openpyxl import load_workbook
out=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261105-windows-content051')
root=max((p for p in out.glob('native-files-*') if (p/'manifest.json').exists()),key=lambda p:p.stat().st_mtime)
manifest=json.loads((root/'manifest.json').read_text(encoding='utf8'));rows=[];renders=[]
compact=lambda t:re.sub(r'\s+','',t)
for item in manifest:
    p=root/item['file'];body=item['selectedText'];title=item['title'];plain=[re.sub(r'^(?:#{1,6}|>)\s?','',line).strip() for line in body.splitlines() if line.strip()]
    result={'file':item['file'],'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    if p.suffix in ['.txt','.md']:assert p.read_text(encoding='utf8')==body
    elif p.suffix=='.docx':
        paragraphs=[para.text for para in Document(p).paragraphs];assert paragraphs[0]==title;assert paragraphs[1:]==plain,(p,paragraphs,plain)
    elif p.suffix=='.xlsx':
        wb=load_workbook(p,data_only=False);sheet=wb.active
        assert sheet['B2'].value==title
        assert [sheet.cell(i,2).value or '' for i in range(3,sheet.max_row+1)]==body.splitlines()
        assert all(cell.data_type!='f' and len(str(cell.value or '').encode('utf-16-le'))//2<=32767 for row in sheet for cell in row)
        assert sheet.freeze_panes=='A2';wb.close()
    elif p.suffix=='.mm':
        parsed=ET.parse(p);values=[n.attrib['TEXT'] for n in parsed.iter('node')]
        expected=[title]+[re.sub(r'^#{1,6}\s','',line).strip() for line in body.splitlines() if line.strip()]
        assert values==expected,(p,values,expected)
    elif p.suffix=='.pdf':
        pdf=fitz.open(p);extract='\n'.join(page.get_text() for page in pdf);second='\n'.join(page.extract_text() or '' for page in PdfReader(p).pages)
        for text in [extract,second]:
            joined=compact(text);assert compact(title) in joined
            cursor=0
            for line in plain:
                pos=joined.find(compact(line),cursor);assert pos>=0,(p.name,'missing exact characters',line,text);cursor=pos+len(compact(line))
        for index,page in enumerate(pdf):
            image=out/f'{p.stem}-page-{index+1}.png';page.get_pixmap(dpi=144).save(image);renders.append(str(image))
        result['pages']=len(pdf);pdf.close();result['twoIndependentReadersExactCharacters']=True
    else:raise AssertionError(p)
    # The excluded fixture material must never leak into any file.
    data=p.read_bytes();assert b'UNSELECTED_PRIVATE_MATERIAL' not in data
    result['passed']=True;rows.append(result)
srt=(root/'transcript.srt').read_text(encoding='utf8');assert '00:00:00,000 --> 00:00:04,000' in srt and '尚未确认采购' in srt and 'The purchase' not in srt
report={'status':'ALL_GENERATED_SELECTED_CONTENT_FILES_OPENED_AND_CHECKED','sourceDirectory':str(root),'files':rows,'srtTimingAndScopePassed':True,'pdfRenderer':'MuPDF (system/bundled Poppler not present)','pdfImages':renders,'visualReview':'PENDING_IMAGE_INSPECTION','modelsRun':False,'ownerDataUsed':False}
(out/'document-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'status':report['status'],'files':len(rows),'pdfImages':renders},ensure_ascii=False))
