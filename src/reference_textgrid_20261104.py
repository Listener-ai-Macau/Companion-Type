"""One reference reader for scoring; preserve multiline Praat labels.

Use the maintained PraatIO parser, without high-level tier normalization or
repair. Empty intervals stay present for count validation. No label/time edits
are written back to the source, and these files never enter model inference.
"""
from pathlib import Path
import math,re,sys

DEPENDENCIES=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/evaluation-textgrid-r6')
sys.path.insert(0,str(DEPENDENCIES))
from praatio.utilities.textgrid_io import parseTextgridStr

PARSER_ID='praatio-6.2.2-count-validated-long-textgrid-r6'


def read_reference_intervals(path):
    raw=Path(path).read_text(encoding='utf-8-sig')
    assert 'ooTextFile' in raw and 'item [' in raw,'Expected frozen long-format TextGrid'
    parsed=parseTextgridStr(raw,includeEmptyIntervals=True)
    declared_tiers=re.search(r'^\s*size\s*=\s*(\d+)\s*$',raw,re.M)
    declared_intervals=[int(n) for n in re.findall(r'^\s*intervals:\s*size\s*=\s*(\d+)\s*$',raw,re.M)]
    assert declared_tiers and int(declared_tiers[1])==len(parsed['tiers'])
    assert len(declared_intervals)==len(parsed['tiers']),'Unsupported non-interval tier; inspect reference'
    rows=[]
    for tier,expected in zip(parsed['tiers'],declared_intervals):
        assert tier['class']=='IntervalTier' and tier['name']
        assert len(tier['entries'])==expected,'Reference interval count mismatch: refuse silent omissions'
        for start,end,text in tier['entries']:
            start,end=float(start),float(end)
            assert math.isfinite(start) and math.isfinite(end) and 0<=start<=end
            assert isinstance(text,str)
            rows.append({'start':start,'end':end,'speaker':tier['name'],'text':text})
    return rows
