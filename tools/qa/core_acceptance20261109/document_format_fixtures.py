"""Independent local Office/text fixtures. No meeting facts or owner files."""
from pathlib import Path
import datetime
import hashlib
import json
import sys
import zipfile
from docx import Document
from openpyxl import Workbook
from reportlab.pdfgen import canvas
from reportlab.lib.pdfencrypt import StandardEncryption

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
doc = Document()
doc.add_heading('公开采购讨论补充材料', 0)
doc.add_paragraph('这不是录音事实。预算草案为12000元，由Alex在周二核对。')
table = doc.add_table(rows=2, cols=2)
for row, values in zip(table.rows, [('事项', '状态'), ('工程需求', '待收集')]):
    for cell, value in zip(row.cells, values): cell.text = value
doc.sections[0].header.paragraphs[0].text = '虚构材料页眉'
doc.save(root / 'material.docx')
# Add a real footnote relationship, reference and content using independent ZIP tooling.
with zipfile.ZipFile(root / 'material.docx') as archive:
    parts = {info.filename: archive.read(info) for info in archive.infolist()}
parts['word/document.xml'] = parts['word/document.xml'].replace(b'</w:body>', b'<w:p><w:r><w:footnoteReference w:id="2"/></w:r></w:p></w:body>')
parts['word/_rels/document.xml.rels'] = parts['word/_rels/document.xml.rels'].replace(b'</Relationships>', b'<Relationship Id="rFoot" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/></Relationships>')
parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace(b'</Types>', b'<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/></Types>')
parts['word/footnotes.xml'] = '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:id="2"><w:p><w:r><w:t>附注：人工提供，不是会议结论。</w:t></w:r></w:p></w:footnote></w:footnotes>'.encode()
with zipfile.ZipFile(root / 'material.docx', 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, content in parts.items(): archive.writestr(name, content)

book = Workbook()
sheet = book.active
sheet.title = '预算草案'
sheet.append(['项目', '金额', '确认', '数量', '日期', '公式'])
sheet.append(['人工补充', 12000, False, 0, datetime.date(2026, 11, 10), '=B2*2'])
sheet['B2'].number_format = '#,##0.00'
sheet['E2'].number_format = 'yyyy-mm-dd'
sheet['XFD1048576'] = '稀疏末尾单元格'
hidden = book.create_sheet('不展示')
hidden['A1'] = '隐藏内容不能悄悄使用'
hidden.sheet_state = 'hidden'
book.save(root / 'material.xlsx')

ns_p = 'http://schemas.openxmlformats.org/presentationml/2006/main'
ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
ns_r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ns_rel = 'http://schemas.openxmlformats.org/package/2006/relationships'
parts = {
 '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>',
 '_rels/.rels': f'<Relationships xmlns="{ns_rel}"><Relationship Id="r1" Type="{ns_r}/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
 'ppt/presentation.xml': f'<p:presentation xmlns:p="{ns_p}" xmlns:r="{ns_r}"><p:sldIdLst><p:sldId id="256" r:id="later"/><p:sldId id="257" r:id="first"/><p:sldId id="258" r:id="hide"/></p:sldIdLst></p:presentation>',
 'ppt/_rels/presentation.xml.rels': f'<Relationships xmlns="{ns_rel}"><Relationship Id="first" Type="{ns_r}/slide" Target="slides/slide1.xml"/><Relationship Id="later" Type="{ns_r}/slide" Target="slides/slide9.xml"/><Relationship Id="hide" Type="{ns_r}/slide" Target="slides/slide2.xml"/></Relationships>',
 'ppt/notesSlides/notesSlide1.xml': f'<p:notes xmlns:p="{ns_p}" xmlns:a="{ns_a}"><a:p><a:r><a:t>演讲者备注不属于正文</a:t></a:r></a:p></p:notes>',
}
for number, text, show in [(9, '第一张：人工材料的来源', '1'), (1, '第二张：工程需求待收集', '1'), (2, '隐藏幻灯片内容', '0')]:
    parts[f'ppt/slides/slide{number}.xml'] = f'<p:sld xmlns:p="{ns_p}" xmlns:a="{ns_a}" show="{show}"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
with zipfile.ZipFile(root / 'material.pptx', 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, content in parts.items(): archive.writestr(name, content.encode())

text = '  人工材料，保留空白。\n不是会议转写。\n'
(root / 'material.txt').write_text(text, encoding='utf-8', newline='')
(root / 'material-utf16.txt').write_bytes(text.encode('utf-16'))
(root / 'material-gb.txt').write_bytes(text.encode('gb18030'))
for name, encrypt in [('material.pdf', None), ('protected.pdf', StandardEncryption('local-password', canCopy=1)), ('restricted.pdf', StandardEncryption('local-password', canCopy=0))]:
    pdf = canvas.Canvas(str(root / name), encrypt=encrypt)
    pdf.drawString(72, 750, 'PUBLIC SUPPLEMENT: 12000, Alex, Tuesday. Not recorded speech.')
    pdf.showPage()
    pdf.drawString(72, 750, 'Second page: verify the source before making a decision.')
    pdf.save()
manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in root.iterdir() if p.is_file() and p.name != 'manifest.json'}
(root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'root': str(root), 'files': len(manifest), 'state': 'FICTIONAL_DOCUMENT_FIXTURES_GENERATED'}))
