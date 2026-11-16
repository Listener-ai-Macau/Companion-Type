"""Recover only three export failures; keep every already valid source/example."""
from pathlib import Path
import hashlib,json
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1');old=E/'acoustic-nonoverlap'
state=json.loads((old/'run.json').read_text(encoding='utf-8'));assert state['finishedAt'] and len(state['failures'])==3
source=Path('work/export_meeting_domain_acoustic_frozen_20261116.py');text=source.read_text(encoding='utf-8')
changes={"OUT=E/'acoustic-nonoverlap'":"OUT=E/'acoustic-nonoverlap-r2'",
 "examples=[];meetings=[];failures=[];state=":"previous=read(E/'acoustic-nonoverlap/run.json');recover_names={r['meeting'] for r in previous['failures']};examples=read(E/'acoustic-nonoverlap/example-provenance.json');meetings=previous['completed'];failures=[];state=",
 "for item in data['completed']:\n  meeting=item['meeting'];":"for item in data['completed']:\n  if item['meeting'] not in recover_names:continue\n  meeting=item['meeting'];",
 "C/'acoustic-export-protocol.json'":"C/'acoustic-export-r2-protocol.json'","C/'acoustic-export.json'":"C/'acoustic-export-r2.json'",
 "if accepted:assert first_frame>=accepted[-1]['endFrame'],'No duplicated overlapping training windows'":"""if accepted and first_frame<accepted[-1]['endFrame']:
     # Adjacent padded regions meet at a midpoint between speech events.
     # Independent floor/ceil can share one sample. Trim only that context
     # when the complete next lexical interval still fits; never clip words.
     if accepted[-1]['endFrame']<=math.floor(start*16000):first_frame=accepted[-1]['endFrame']
     else:skip['subsampleGapCannotSeparateWithoutClippingCore']+=1;group.clear();return"""}
for before,after in changes.items():assert before in text,before;text=text.replace(before,after)
marker="atomic_json(C/'acoustic-export-r2-protocol.json',protocol)"
replacement="protocol['recovery']={'previousRunSha256':sha(E/'acoustic-nonoverlap/run.json'),'previousProvenanceSha256':sha(E/'acoustic-nonoverlap/example-provenance.json'),'reuseSuccessfulSources':19,'changedCondition':'One-sample overlap from floor/ceil of a shared padding midpoint; trim context only, otherwise exclude the example. No label, source, model or evaluation change.'};"+marker
assert marker in text;text=text.replace(marker,replacement)
target=Path('work/recover_domain_acoustic_export_frozen_20261116.py');assert not target.exists();target.write_text(text,encoding='utf-8');compile(text,str(target),'exec')
exec(compile(text,str(target),'exec'),{'__name__':'__main__','__file__':str(target)})
