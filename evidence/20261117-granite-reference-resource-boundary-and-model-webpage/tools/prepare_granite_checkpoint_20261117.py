"""Select closed, small model evidence without weights, audio or runtime caches."""
from pathlib import Path
from datetime import datetime
import hashlib,json,sys
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/tools/handbook')
import docstore

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
key='Companion/docs/development_log.md'
timeline=docstore.read_bytes(key)
assert b'MODEL_REFERENCE_AND_PORTAL_BATCH_20261117' in timeline
receipt=dict(at=datetime.now().astimezone().isoformat(),timelineQueryKey=key,timelineUrl=docstore.url(key),
    timelineSha256=docstore.sha(timeline),timelineBytes=len(timeline),
    physicalMarkdownRestored=False,canonicalBacklogSha256=hashlib.sha256((R/'docs/product_backlog.json').read_bytes()).hexdigest())
(C/'canonical-record-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
items=[]
def add(p,name):
    p=Path(p)
    assert p.is_file() and p.stat().st_size<32*1024**2
    items.append(dict(source=str(p.resolve()),name=name))
for p in C.glob('*.json'):add(p,'reference/'+p.name)
for run in sorted(C.glob('native-cpu-r*')):
    for p in run.iterdir():
        if p.is_file() and p.suffix in ('.json','.py','.previous'):add(p,'reference/'+run.name+'/'+p.name)
for p in (C/'asset-acquisition-r1').glob('*.json'):add(p,'reference/asset-acquisition-r1/'+p.name)
for p in (C/'portal-browser-r5').iterdir():
    if p.is_file():add(p,'portal-browser-r5/'+p.name)
for name in ['acquire_granite_reference_20261117.py','prepare_granite_execution_20261117.py',
 'score_granite_reference_20261117.py','record_granite_and_portal_20261117.py',
 'record_bilingual_progress.py','check_model_portal_20261117.py',
 'checkpoint_model_portal_20261117.py','complete_cpu_wheel_payload_20261117.py',
 'prepare_granite_checkpoint_20261117.py']:
    add(Path('work')/name,'tools/'+name)
add('work/bilingual_progress.json','workpoint-snapshot.json')
assert len({x['name'] for x in items})==len(items)
config=dict(revision=74,evidenceDirectory='evidence/20261117-granite-reference-resource-boundary-and-model-webpage',
    sources=['src/granite_reference_worker_20261117.py'],closedDirectories=[],files=items,
    commitMessage='Preserve native Granite reference execution boundary and measured model-webpage delivery',
    claims=dict(state='GRANITE_REFERENCE_PARTIAL_CPU_BOUNDARY_RETAINED_AND_MODEL_PAGE_DELIVERED',
        completedOriginalAudioOutputs=1,attemptedOriginalAudioCases=2,originalCaseCount=12,
        newTrainingUpdates=0,fullFixedReferenceScoreExists=False,
        cpuDiskOffloadProfileEndedWithoutAutomaticRetry=True,
        candidateQualityRejected=False,qualityQualified=False,saleQualified=False,
        originalReferencesAndMetricsUnchanged=True,
        rawAudioInputFeaturesModelWeightsRuntimeWheelsOrCredentialsIncluded=False,
        webpageLocalSourceCommit=json.loads((C/'portal-source-checkpoint.json').read_text())['commit']))
out=Path('work/checkpoint_granite_and_portal_r74.json')
out.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(configuration=str(out),files=len(items),bytes=sum(Path(i['source']).stat().st_size for i in items),canonicalRecord=receipt)))
