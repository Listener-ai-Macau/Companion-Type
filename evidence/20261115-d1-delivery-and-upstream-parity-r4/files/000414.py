"""Single diagnostic oracle-activity control, never a product/accuracy result.

Ask whether fixing activity/identity alone rescues the fixed spatial pipeline.
No reference words enter ASR; no model, geometry, threshold or window sweep.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';MAIN=R/'docs/handoffs/20261108-dual-mic-independent-meetings';C=MAIN/'oracle-activity-control';E=Path('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108/oracle-activity-control')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not C.exists();C.mkdir();E.mkdir();assert read(MAIN/'review.json')['allFrozenCasesAndPeopleScored']
cases=[]
for case in read(MAIN/'spatial-audio-only.json'):
    if case['kind']=='ordinary-regression':continue
    scoring=next(r for r in read(MAIN/'scoring-only.json') if r['originalMeeting']==case['meeting'] and r['sourceChannel']==0);assert sha(scoring['reference'])==scoring['referenceSha256'];full=read(scoring['fixedMappingReview']);mapping={person:int(v['matchedAnonymousGroup'].removeprefix('speaker_')) for person,v in full['perReferenceSpeakerForEvaluationOnly'].items() if v['matchedAnonymousGroup'] is not None};assert len(mapping)==full['referenceSpeakers']
    truth=[r for r in read_reference_intervals(scoring['reference']) if normalize(r['text'])];journal=C/(case['meeting']+'-ORACLE-ACTIVITY-NOT-PRODUCT.json')
    if not journal.exists():atomic_json(journal,{'meeting':case['meeting'],'segments':[{'start':r['start'],'end':r['end'],'speaker':mapping[r['speaker']]} for r in truth],'scope':'DIAGNOSTIC_REFERENCE_ACTIVITY_ONLY_NOT_PRODUCT_PREDICTION. No lexical text provided to processing.'})
    lo,hi=case['rootStartSample']/16000,case['rootEndSample']/16000;people=sorted({mapping[r['speaker']] for r in truth if r['end']>lo and r['start']<hi})
    cases.append({**case,'kind':'diagnostic-reference-activity','journal':str(journal),'journalSha256':sha(journal),'predictedRootPeople':people,'activityProvenance':'ORACLE_REFERENCE_ACTIVITY_DIAGNOSTIC_NOT_PRODUCT','referenceLexicalTextPassedToAsr':False})
atomic_json(C/'spatial-audio-only.json',cases)
for name in ['numpy-backend.json','numpy-numerical-proof.json','model-ready.json','scoring-only.json','journal-review.json']:(C/name).write_bytes((MAIN/name).read_bytes())
atomic_json(C/'seed-manifest.json',{})
def derive(old,new,changes):
    text=old.read_text(encoding='utf8').replace(str(MAIN).replace('\\','/'),str(C).replace('\\','/'))
    for a,b in changes:
        assert a in text,a;text=text.replace(a,b)
    ast.parse(text);assert not new.exists();new.write_text(text,encoding='utf8');return text
spatial=S/'independent_oracle_gss_worker_20261108.py'
derive(S/'independent_dual_gss_worker_20261108.py',spatial,[('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108','E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108/oracle-activity-control'),("'referencePassedToWorker':False","'referenceActivityPassedToWorker':True,'referenceLexicalTextPassedToWorker':False"),("'oracleOrReferenceActivityUsed':False","'oracleOrReferenceActivityUsed':True")])
asr=S/'independent_oracle_asr_worker_20261108.py'
text=derive(S/'independent_dual_asr_worker_20261108.py',asr,[("'referencePassedToWorker':False","'referenceActivityUsedForInputPreparation':True,'referenceLexicalTextPassedToWorker':False")])
infer=lambda t:ast.dump(next(n for n in ast.walk(ast.parse(t)) if isinstance(n,ast.FunctionDef) and n.name=='infer'),include_attributes=False)
assert infer(text)==infer((S/'independent_dual_asr_worker_20261108.py').read_text(encoding='utf8'))
derive(S/'run_independent_dual_gss_20261108.py',S/'run_independent_oracle_gss_20261108.py',[("'independent_dual_gss_worker_20261108.py'","'independent_oracle_gss_worker_20261108.py'"),("'independent_dual_asr_worker_20261108.py'","'independent_oracle_asr_worker_20261108.py'")])
derive(S/'score_independent_dual_gss_20261108.py',S/'score_independent_oracle_gss_20261108.py',[("C=R/'docs/handoffs/20261108-dual-mic-independent-meetings'","C=R/'docs/handoffs/20261108-dual-mic-independent-meetings/oracle-activity-control'"),("'allFrozenCasesAndPeopleScored':True","'allFrozenCasesAndPeopleScored':True,'oracleReferenceActivityUsed':True,'productScore':False")])
P=read(MAIN/'protocol-r2.json');files=[C/'spatial-audio-only.json',C/'numpy-backend.json',C/'numpy-numerical-proof.json',spatial,S/'companion_gss_numpy_backend_20261108.py']+[Path(c['journal']) for c in cases]
P.update(at=datetime.now().astimezone().isoformat(),state='FROZEN_SINGLE_REFERENCE_ACTIVITY_DIAGNOSTIC_NOT_PRODUCT',workerSourceSha256=sha(spatial),asrWorkerSourceSha256=sha(asr),audioOnlySha256=sha(C/'spatial-audio-only.json'),modelReadySha256=sha(C/'model-ready.json'),sourceFiles=[{'file':str(p),'sha256':sha(p)} for p in files],rootCount=len(cases),expectedOutputRows=sum(len(c['predictedRootPeople'])*2 for c in cases),referenceActivityUsed=True,referenceLexicalTextPassedToAsr=False,referencePayloadRead=True,activity='DIAGNOSTIC only: complete official reference speech intervals and identity alias. No words provided to GSS or ASR. Compare with automatic journal after all fixed outputs; never include this score in the product acceptance result.',retention='One causal control on all four existing complex roots, both mono and rawdual. No new window, model, parameter, per-person winner or replacement of failed automatic results. Ordinary bypass already validated and unchanged; do not rerun it.',conditions=['oracle_activity_mono','oracle_activity_rawdual'])
atomic_json(C/'protocol-r2.json',P);atomic_json(C/'control-purpose.json',{'at':P['at'],'state':P['state'],'automaticReviewSha256':sha(MAIN/'review.json'),'automaticGateAuditSha256':sha(MAIN/'gate-audit.json'),'hypothesis':'If true activity/identity still leaves substantial speaker words missing or contaminated, fixing diarization alone is insufficient; spatial front end also needs a different separation design. If much improved, prioritize robust identity/activity before more separator models.','ordinaryPipelineChanged':False,'expectedOutputRows':P['expectedOutputRows'],'referenceActivityUsed':True,'referenceLexicalTextPassedToAsr':False,'newTrainingRuns':0,'productDefaultChanged':False,'productScore':False})
print(json.dumps({'state':P['state'],'roots':len(cases),'expectedOutputRows':P['expectedOutputRows']}),flush=True)
