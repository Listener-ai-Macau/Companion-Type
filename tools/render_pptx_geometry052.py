"""Read-only preview of native editable text frames, not PowerPoint execution."""
from pathlib import Path
import json,zipfile,re,html,xml.etree.ElementTree as ET
b=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-material-exports052')
source=sorted(b.glob('native-files-*'))[-1]/'material.pptx';out=b/'pptx-geometry-preview';out.mkdir(exist_ok=True)
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
files=[]
with zipfile.ZipFile(source) as z:
    slides=sorted([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)],key=lambda n:int(re.search(r'(\d+)\.xml',n)[1]))
    for index,name in enumerate(slides):
        root=ET.fromstring(z.read(name));boxes=[]
        for shape in root.findall('.//p:sp',ns):
            transform=shape.find('p:spPr/a:xfrm',ns);off=transform.find('a:off',ns);ext=transform.find('a:ext',ns)
            rect=[int(off.get('x')),int(off.get('y')),int(ext.get('cx')),int(ext.get('cy'))];x,y,w,h=[v/9525 for v in rect]
            paragraphs=[]
            for para in shape.findall('p:txBody/a:p',ns):
                run=para.find('a:r/a:rPr',ns);size=int(run.get('sz','2000'))/100
                color=run.find('a:solidFill/a:srgbClr',ns).get('val');spacing=para.find('a:pPr/a:lnSpc/a:spcPts',ns)
                line_height=int(spacing.get('val'))/100 if spacing is not None else size*1.4
                text=''.join(p.text or '' for p in para.findall('.//a:t',ns))
                paragraphs.append(f'<p style="font-size:{size}pt;line-height:{line_height}pt;color:#{color};font-weight:{700 if run.get("b")=="1" else 400}">{html.escape(text)}</p>')
            boxes.append(f'<div class="frame" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'+''.join(paragraphs)+'</div>')
        file=out/f'slide-{index+1}.html';file.write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\';style-src \'unsafe-inline\'"><style>html,body{margin:0;width:1280px;height:720px;background:#F8FAFC;font-family:"Microsoft YaHei",sans-serif}.frame{position:absolute}p{white-space:pre;margin:0;padding:0}</style>'+''.join(boxes),encoding='utf8');files.append(str(file))
(out/'inputs.json').write_text(json.dumps({'files':files,'scope':'Local text-frame geometry preview parsed from the generated PPTX; not a native Microsoft PowerPoint screenshot.'},indent=2),encoding='utf8')
print(json.dumps({'files':files}))
