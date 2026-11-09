"""Independent post-inference scoring of full public paired input streams.

Headset source IDs are known file assignments, NOT automatic diarization.
Raw far mix chronological CER and source-associated CER are distinct metrics.
"""
from pathlib import Path
from datetime import datetime
import argparse,ast,hashlib,json,re,sys,unicodedata
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-paired-real-meeting'
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=192*1024**2)
sys.path.insert(0,'E:/CodexData/Companion/.build-cache/core-acceptance20261109/quality-deps')
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from rapidfuzz.distance import Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=argparse.ArgumentParser();p.add_argument('--artifact',required=True);a=p.parse_args();artifact=Path(a.artifact).resolve()
run=read(artifact/'result.json');assert run['state']=='COMPLETE_FIVE_FIXED_PRODUCT_ASR_INPUTS_UNSCORED' and len(run['completed'])==5
assert run['modelSha256']=='8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54'
module=ast.parse((R/'model-research/src/full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf8'));scope={'re':re,'unicodedata':unicodedata}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'frozen-normalizer','exec'),scope);normalize=scope['normalize']
inputs={r['id']:r for r in read(C/'fixed-asr-audio-only.json')};refs=read(C/'fixed-asr-scoring-only.json')['sourceReferences'];own={};all_rows=[];results=[];offset_examples={}
for source in refs:
    assert sha(source['reference'])==source['referenceSha256']
    rows=[r for r in read_reference_intervals(source['reference']) if normalize(r['text'])]
    assert rows and len({r['speaker'] for r in rows})==1
    own[source['id']]=rows;all_rows.extend(rows)
assert len(all_rows)==604
for completed in run['completed']:
    ident=completed['id'];inp=inputs[ident];assert completed['sha256']==inp['audioSha256'] and completed['seconds']==inp['audioSeconds']
    output=artifact/(ident+'-output.json');assert sha(output)==completed['outputSha256']
    doc=read(output);assert doc['isFinal'] and hashlib.sha256(doc['text'].encode()).hexdigest()==completed['transcriptSha256']
    rows=own.get(ident,all_rows);ordered=sorted(rows,key=lambda r:(r['start'],r['end']))
    assert max(r['end'] for r in rows)<=inp['audioSeconds']
    reference=normalize(''.join(r['text'] for r in ordered));hypothesis=normalize(doc['text']);ops=Levenshtein.editops(reference,hypothesis)
    edits={kind:sum(op.tag==kind for op in ops) for kind in ['replace','delete','insert']}
    results.append({'id':ident,'metric':'known-headset-source-CER' if ident in own else 'raw-mixed-chronological-CER','referenceCharacters':len(reference),'hypothesisCharacters':len(hypothesis),'edits':edits,'totalEdits':len(ops),'cer':len(ops)/len(reference),'elapsedSeconds':completed['elapsedSeconds'],'realTimeFactor':completed['elapsedSeconds']/inp['audioSeconds'],'privatePeakBytes':completed['privatePeakBytes'],'audioSha256':completed['sha256'],'outputSha256':completed['outputSha256'],'allOriginalDurationSubmitted':True,'referenceActivityPassedToInference':False})
    offset_examples[ident]=[{'op':op.tag,'referenceIndex':op.src_pos,'hypothesisIndex':op.dest_pos,'referenceContext':reference[max(0,op.src_pos-12):op.src_pos+13],'hypothesisContext':hypothesis[max(0,op.dest_pos-12):op.dest_pos+13]} for op in list(ops)[:24]]
near=[r for r in results if r['id'] in own];aggregate={'metric':'known-headset-source-aggregate-CER-not-diarization','referenceCharacters':sum(r['referenceCharacters'] for r in near),'edits':{k:sum(r['edits'][k] for r in near) for k in ['replace','delete','insert']},'totalEdits':sum(r['totalEdits'] for r in near)};aggregate['cer']=aggregate['totalEdits']/aggregate['referenceCharacters']
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'COMPLETE_FIVE_FIXED_PRODUCT_ASR_SCORED_EXPOSED_DIAGNOSTIC','meeting':'AliMeeting R8001_M8004','commonSeconds':1551.82,'sourceUtterances':604,'modelSha256':run['modelSha256'],'appSource':run['appSource'],'testSource':run['testSource'],'results':results,'nearAggregate':aggregate,'referenceParser':PARSER_ID,'referenceManifestSha256':sha(C/'fixed-asr-scoring-only.json'),'rawRunReceiptSha256':sha(artifact/'result.json'),'neuralInferencePerformedByScorer':False,'inferenceUsedReferenceTextOrActivity':False,'knownSourceAssignmentNotAutomaticSpeakers':True,'isolatedSourceTruth':False,'metricComparisonLimits':['Headsets contain measured real crosstalk: non-target insertions are not automatically hallucinations.','Far mixed chronological reference has overlap ordering ambiguity; do not directly compare this CER with per-headset aggregate.','File-level source assignment is known; this is not automatic diarization, cpCER, word alignment, holdout or sale qualification.','This is deployed Paraformer on Windows, distinct from the frozen Qwen arm pending local RAM recovery.'],'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
dest=C/'product-five-source-ci';dest.mkdir(exist_ok=True);assert not (dest/'score.json').exists(),'Preserve the original score'
(dest/'score.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(dest/'edit-examples.json').write_text(json.dumps(offset_examples,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'state':record['state'],'results':results,'nearAggregate':aggregate},ensure_ascii=False))
