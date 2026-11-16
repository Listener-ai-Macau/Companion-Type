from pathlib import Path
import hashlib,json
original=Path('work/build_afternoon_cpu_delivery_20261116.py');source=original.read_text(encoding='utf-8')
changes={
 'outputs/Companion-CPU与复杂会议阶段交付-20261116-1600':'outputs/Companion-CPU与复杂会议阶段交付-20261116-1600-r2',
 "p.write_text(text,encoding='utf-8');return p":"p.write_bytes(text.encode('utf-8'));return p",
 "B/'afternoon-delivery-r1.json'":"B/'afternoon-delivery-r2.json'"}
for before,after in changes.items():assert before in source;source=source.replace(before,after)
target=Path('work/build_afternoon_cpu_delivery_frozen_r2_20261116.py');assert not target.exists();target.write_text(source,encoding='utf-8')
failure={'state':'FIRST_REPORT_DRAFT_NOT_DELIVERED_RAW_TEXT_BYTE_CHECK_CAUGHT_WINDOWS_LF_TO_CRLF_TRANSLATION','sourceSha256':hashlib.sha256(original.read_bytes()).hexdigest(),
 'fix':'Write generated raw UTF8 transcript bytes directly; retain failed draft folder/zip and build a separate r2 report. No model recomputation or score change.','newNeuralCalls':0}
Path('work/afternoon-report-r1-preparation-failure.json').write_text(json.dumps(failure,indent=2)+'\n',encoding='utf-8')
exec(compile(source,str(target),'exec'),{'__name__':'__main__','__file__':str(target)})
