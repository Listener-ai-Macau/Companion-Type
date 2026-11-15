from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from reference_textgrid_20261104 import read_reference_intervals
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-acoustic-context-r1';assert C.exists() and not (C/'train.json').exists()
assert not (C/'source-coverage-audit.json').exists()
shutil.copyfile(Path('work/prepare_public_acoustic_context_20261115.py'),C/'preparation-before-insufficient-data-stop.py')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
root=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/official-annotations')
report=[]
for p in sorted(root.glob('*.TextGrid')):
    # Original target's full day and the two frozen validation-source days
    # remain excluded, even for selecting training-only additions.
    if p.name[:8] in {'20200623','20200709','20200805'}:continue
    rows=sorted([r for r in read_reference_intervals(p) if r['text'].strip()],key=lambda r:(r['start'],r['end'],r['speaker']))
    components=[];end=-1.
    for r in rows:
        if r['start']>=end:components.append([])
        components[-1].append(r);end=max(end,r['end'])
    plans=[]
    for i,c in enumerate(components):
        if len(c)!=1:continue
        win=[]
        for more in components[i:]:
            if len(more)!=1 or more[0]['end']-c[0]['start']>29.84:break
            win+=more
        if len({r['speaker'] for r in win})<2 or win[-1]['end']-win[0]['start']<4:continue
        if not any(r['end']-r['start']<2 for r in win):continue
        if any('<' in r['text'] or '>' in r['text'] for r in win):continue
        plans.append(win)
    selected=[];end=-1.
    for win in plans:
        if win[0]['start']>=end+.16:selected.append(win);end=win[-1]['end']
    report.append(dict(meeting=p.stem,reference=str(p),referenceSha256=sha(p),
                       eligiblePlans=len(plans),disjointGreedyPlans=len(selected),
                       selectedSeconds=sum(w[-1]['end']-w[0]['start'] for w in selected),
                       referenceSpeakers=len({r['speaker'] for r in rows})))
ranked=sorted(report,key=lambda r:(-r['disjointGreedyPlans'],r['meeting']))
eligible=[r for r in ranked if r['disjointGreedyPlans']>=20]
assert eligible,'No adequate source under fixed rules; do not train or relax data rules'
choice=eligible[0]
result=dict(state='COMPLETE_ANNOTATION_ONLY_TRAINING_COVERAGE_AUDIT_BEFORE_ACOUSTIC_MODEL_RUN',
            at=datetime.now().astimezone().isoformat(),sources=report,selectedAddition=choice,
            selection='Single highest count of disjoint eligible natural nonoverlap multi-turn contexts; lexical timestamp/source order tie-break. No neural output, recognition error or validation score consulted. Preserve original data rules, not a model/parameter trial.',
            previousPreparation='STOP_INSUFFICIENT_DATA: only11 valid WAVs exported; no train manifest, neural call or parameter update. System-Python initial invocation also lacked soundfile; existing AMD interpreter used without package edits.',
            excludedFullDays=['20200623','20200709','20200805'],
            ownerParticipationRequired=False,newNeuralCalls=0,newTrainingUpdates=0,
            scoringRulesChanged=False,qualityQualified=False,limits=limits.query())
(C/'source-coverage-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'auditedSources':len(report),'selectedAddition':choice,'top5':ranked[:5]},ensure_ascii=False))
