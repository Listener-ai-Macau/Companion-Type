"""Rebuild the PDF-only OFL font from its pinned public upstream input.

No recording text is an input. Preserve all source Unicode coverage and give
each codepoint a distinct glyph ID so Skia can round-trip PDF text correctly.
Requires the fontTools version recorded beside the checked-in output font.
"""
from pathlib import Path
import argparse,copy,hashlib,json,tempfile
import fontTools
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

def build(source,output,provenance):
    metadata=json.loads(provenance.read_text(encoding='utf8'))
    if fontTools.__version__!=metadata['fontToolsVersion']:
        raise ValueError('Use the recorded fontTools version for reproducible font output')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=metadata['source']['sha256']:
        raise ValueError('Upstream font differs from pinned source')
    font=instantiateVariableFont(TTFont(source),{'wght':400},inplace=True)
    if 'DSIG' in font:del font['DSIG']
    font['head'].created=metadata['fixedHeadCreated'];font['head'].modified=metadata['fixedHeadModified'];font.recalcTimestamp=False
    with tempfile.TemporaryDirectory(prefix='companion-pdf-font-',dir=output.parent) as tmp:
        static=Path(tmp)/'static.ttf';font.save(static);font.close();font=TTFont(static)
        cmap=font.getBestCmap().copy();groups={}
        for cp,glyph in cmap.items():groups.setdefault(glyph,[]).append(cp)
        order=list(font.getGlyphOrder());mapping={}
        for glyph,codepoints in groups.items():
            for cp in sorted(codepoints)[1:]:
                name='cp'+format(cp,'06X')
                if name in font['glyf'].glyphs:raise ValueError('Duplicate generated glyph')
                font['glyf'][name]=copy.deepcopy(font['glyf'][glyph]);font['hmtx'].metrics[name]=font['hmtx'].metrics[glyph]
                if 'vmtx' in font:font['vmtx'].metrics[name]=font['vmtx'].metrics[glyph]
                order.append(name);mapping[cp]=name
        if len(order)>=65535:raise ValueError('TrueType glyph limit exceeded')
        font.setGlyphOrder(order)
        for table in font['cmap'].tables:
            if table.isUnicode() and hasattr(table,'cmap'):
                for cp,name in mapping.items():
                    if cp in table.cmap:table.cmap[cp]=name
        if 'GSUB' in font:del font['GSUB']
        names={1:'Companion PDF Sans',2:'Regular',3:'Companion-PDF-Sans-Regular-1',4:'Companion PDF Sans Regular',6:'CompanionPDFSans-Regular',16:'Companion PDF Sans',17:'Regular'}
        for record in font['name'].names:
            if record.nameID in names:record.string=names[record.nameID].encode(record.getEncoding())
        if font['OS/2'].fsType!=0:raise ValueError('Unexpected embedding restriction in pinned font')
        font.recalcTimestamp=False;candidate=Path(tmp)/'document.ttf';font.save(candidate)
        with TTFont(candidate,lazy=True) as verified:check=verified.getBestCmap()
        if set(check)!=set(cmap) or len(set(check.values()))!=len(check):raise ValueError('Coverage or unique mapping failed')
        if hashlib.sha256(candidate.read_bytes()).hexdigest()!=metadata['outputSha256']:raise ValueError('Rebuilt font differs from verified output')
        with output.open('xb') as stream:stream.write(candidate.read_bytes())
        font.close()
    return metadata['outputSha256']

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();provenance=Path(__file__).parent/'src/main/assets/companion-documents/provenance.json'
    print('PDF_FONT_REBUILT_SHA256',build(args.source,args.output,provenance))
