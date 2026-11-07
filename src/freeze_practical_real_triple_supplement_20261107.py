"""Expose missing Mandarin triple-overlap diagnostic coverage; no model rerun."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import json,hashlib,math,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert (C/'review.json').exists() and not (C/'mandarin-triple-supplement.json').exists();out=Path('E:/CodexData/Companion/.model-cache/target-activity-controls-20261107');selected=[];findings=[]
for score in [r for r in read(C/'scoring-only.json') if r['referenceKind']=='textgrid_lexical']:
    name=score['meeting'];reference=[r for r in read_reference_intervals(score['reference']) if normalize(r['text'])];events=defaultdict(list)
    for r in reference:events[r['start']].append((r['speaker'],1));events[r['end']].append((r['speaker'],-1))
    points=sorted(events);active=defaultdict(int);triple=[]
    for i,lo in enumerate(points[:-1]):
        for person,delta in events[lo]:
            active[person]+=delta
            if not active[person]:del active[person]
        if len(active)>=3 and points[i+1]>lo:triple.append((lo,points[i+1]))
    excluded=[(p['startSample']/16000,p['endSample']/16000) for p in read(C/'audio-only.json')+read(C/'automatic-enrollments.json') if p['meeting']==name]
    chosen=None
    for root in range(math.floor(score['audioSeconds']/30)):
        lo=root*30.;hi=lo+30
        if any(min(hi,b)>max(lo,a) for a,b in excluded):continue
        seconds=sum(max(0.,min(hi,b)-max(lo,a)) for a,b in triple)
        if seconds>=.5:chosen=(root,lo,hi,seconds);break
    findings.append({'meeting':name,'fullReferenceTripleSeconds':sum(b-a for a,b in triple),'firstEligibleDisjoint30sRoot':chosen[0] if chosen else None,'supplementEligible':chosen is not None})
    if chosen:
        root,lo,hi,seconds=chosen;file=out/(name+'-reference-curated-triple-root-%06d.wav'%root);assert not file.exists()
        with wave.open(score['audio'],'rb') as source:
            source.setpos(round(lo*16000));pcm=source.readframes(480000)
            with wave.open(str(file),'wb') as dest:dest.setparams(source.getparams());dest.writeframes(pcm)
        with file.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        selected.append({'id':name+'-curated-triple-root-%06d'%root,'meeting':name,'audio':str(file),'audioSha256':digest,'audioSeconds':30.,'startSample':round(lo*16000),'endSample':round(hi*16000),'allAnonymousTargets':sorted(a['speaker'] for a in read(C/'automatic-enrollments.json') if a['meeting']==name)})
        findings[-1]['referenceTripleSecondsInSupplement']=seconds
atomic_json(C/'mandarin-triple-audio-only.json',selected)
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'EXPOSED_MANDARIN_TRIPLE_COVERAGE_SUPPLEMENT_FROZEN_NO_INFERENCE','findings':findings,
    'reason':'Posthoc coverage found the old predicted Mandarin triple clip had zero true3-person overlap; AMI controls contain true triple overlap. Do not call a predicted category ground truth.',
    'selection':'For each exposed Mandarin development recording, first complete30s root with>=0.5s lexical reference3+ overlap, disjoint from all13 frozen test clips and all15 automatic enrollments. Reference-assisted benchmark curation is disclosed; not a blind/unseen test and not training data.',
    'referenceLabelsNotInAudioOnlyManifest':True,'original13ClipAnd67QueryResultsUnchanged':True,'rejectedCandidateNotRerunOnSupplement':True,'newNeuralCalls':0,'finalHoldoutOpened':False,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'mandarin-triple-supplement.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
