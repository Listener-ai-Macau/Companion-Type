"""Resume only the missing scorer dependency; do not repeat ASR or AI."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,re,shutil,sys,unicodedata
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261109-core-acceptance';D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')
out=C/'whole-805278e2b7214018a4ddef74e361a9e8';record=json.loads((out/'result.json').read_text(encoding='utf8'));assert record['error']=="ModuleNotFoundError(\"No module named 'praatio'\")"
shutil.copyfile(out/'result.json',out/'scoring-preparation-failure-retained.json')
generated=json.loads((out/'02-generate-ai-from-actual-audio-asr.json').read_text(encoding='utf8'));row=json.loads((D/'same-meeting-asr-ci-42592563926/same-meeting-state/session.json').read_text(encoding='utf8'))
for key in ['transcriptText','utterances']:assert generated[key]==row[key]
assert generated['minutes']['source']=='llm_deepseek' and generated['minutes']['processing']['complete']
sys.path.insert(0,str(D/'quality-deps'));sys.path.insert(0,str(R/'model-research/src'))
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from rapidfuzz.distance import Levenshtein
module=ast.parse((R/'model-research/src/full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf8'));scope={'re':re,'unicodedata':unicodedata}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'<existing-normalizer>','exec'),scope);normalize=scope['normalize']
reference=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/S_R004S03C01.TextGrid')
with reference.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3'
ref=normalize(''.join(r['text'] for r in sorted(read_reference_intervals(reference),key=lambda r:(r['start'],r['end']))));hyp=normalize(row['transcriptText']);ops=Levenshtein.editops(ref,hyp)
record.update(state='SAME_REAL_AUDIO_PRODUCT_ASR_AI_GENERATED_AND_REOPENED_DELIVERY_CONTINUES',scoringPreparationFailureRetained='scoring-preparation-failure-retained.json',asrOrAiRepeatedForScoring=False,finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'))
record.pop('error',None)
record['currentProductAsrChronologicalDiagnostic']={'referenceCharacters':len(ref),'hypothesisCharacters':len(hyp),'edits':{kind:sum(op.tag==kind for op in ops) for kind in ['replace','delete','insert']},'cer':len(ops)/len(ref),'referenceParser':PARSER_ID,'referenceSha256':'ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3','scope':'Current installed provider, one exposed full public meeting, chronological mixed text only; not per-speaker overlap/DER/cross-meeting acceptance','passedBelowFivePercent':len(ops)/len(ref)<.05}
(out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');fixture=S/'tools/qa/core_acceptance20261109/fixtures/whole-meeting-ai-session.json'
(C/'same-meeting-ai-current.json').write_text(json.dumps({'evidence':str(out),'root':record['root'],'fixture':str(fixture),'fixtureSha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'record':record},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'state':record['state'],'sameSessionId':row['id'],'asrSeconds':record['productAsrSeconds'],'aiSeconds':record['aiSeconds'],'currentProductAsrChronologicalDiagnostic':record['currentProductAsrChronologicalDiagnostic']},ensure_ascii=False))
