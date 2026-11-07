"""Exited full-recording activity errors by overlap, with ONE frozen global mapping."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,re
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);a=p.parse_args();C=Path(a.control);read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert read(C/'native-run.json')['state']=='COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED';limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();assert not pressure.low()
from pyannote.core import Annotation,Segment,Timeline
from pyannote.metrics.identification import IdentificationErrorRate
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
rows=[]
for case in read(C/'scoring-only.json'):
    out=C/'results'/case['meeting'];review=read(out/'review.json');producer=read(out/'completed-state.json');assert producer['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' and producer['finishedAt'] and producer['audioSha256']==case['audioSha256']
    assert sha(case['reference'])==case['referenceSha256'] and sha(out/'predicted.rttm')==review['rttmSha256']==producer['rttmSha256']
    reference=Annotation(uri=case['meeting']);hypothesis=Annotation(uri=case['meeting']);uem=Timeline([Segment(0,case['audioSeconds'])])
    for index,row in enumerate(read_reference_intervals(case['reference'])):
        if re.sub(r'<[^>]*>','',row['text']).strip():reference[Segment(row['start'],row['end']),row['speaker']+':'+str(index)]=row['speaker']
    reference=reference.support().crop(uem)
    mapping={r['matchedAnonymousGroup']:person for person,r in review['perReferenceSpeakerForEvaluationOnly'].items() if r['matchedAnonymousGroup'] is not None}
    for index,line in enumerate((out/'predicted.rttm').read_text(encoding='utf8').splitlines()):
        fields=line.split();start=float(fields[3]);hypothesis[Segment(start,start+float(fields[4])),str(index)]=mapping.get(fields[7],'UNMATCHED:'+fields[7])
    hypothesis=hypothesis.support().crop(uem);metric=IdentificationErrorRate(collar=0.,skip_overlap=False);all_components=metric(reference,hypothesis,uem=uem,detailed=True)
    for key in ['correct','confusion','missed detection','false alarm','total']:assert abs(all_components[key]-review['components'][key])<1e-4,'Frozen-map full score differs from the original complete score'
    events={0.:0,case['audioSeconds']:0}
    for person in reference.labels():
        for span in reference.label_timeline(person).support():events[span.start]=events.get(span.start,0)+1;events[span.end]=events.get(span.end,0)-1
    regions={'nonOverlapIncludingSilence':Timeline(),'twoOrMore':Timeline(),'threeOrMore':Timeline()};previous=0.;active=0
    for point,delta in sorted(events.items()):
        if point>previous:
            regions['twoOrMore' if active>=2 else 'nonOverlapIncludingSilence'].add(Segment(previous,point))
            if active>=3:regions['threeOrMore'].add(Segment(previous,point))
        active+=delta;previous=point
    details={}
    for name,region in regions.items():
        region=region.support();duration=region.duration()
        if not duration:details[name]={'audioRegionSeconds':0.,'state':'NOT_APPLICABLE_NO_REFERENCE_REGION'};continue
        counts=metric(reference,hypothesis,uem=region,detailed=True);errors=sum(counts[k] for k in ['confusion','missed detection','false alarm']);details[name]={'audioRegionSeconds':duration,'referenceSpeakerSeconds':counts['total'],'derWithFrozenGlobalAssignment':errors/counts['total'] if counts['total'] else None,'components':counts}
    # The first two disjoint regions must exactly partition the full score,
    # including quiet false alarms. No region gets its own identity remap.
    for key in ['correct','confusion','missed detection','false alarm','total']:
        assert abs(sum(details[name].get('components',{}).get(key,0) for name in ['nonOverlapIncludingSilence','twoOrMore'])-all_components[key])<1e-4
    row={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'meeting':case['meeting'],'referenceParser':PARSER_ID,'referenceSha256':case['referenceSha256'],'rttmSha256':producer['rttmSha256'],'frozenFullMeetingMappingForEvaluationOnly':mapping,'mappingNeverReturnedToInference':True,'fullOriginalComponentsReproduced':True,'collarSeconds':0.,'overlapIncluded':True,'regionSpecificRemapping':False,'regions':details,'neuralInferenceAdded':0,'overlapWordsRecovered':False,'qualified':False};atomic_json(out/'overlap-breakdown.json',row);rows.append(row)
pressure.close();atomic_json(C/'overlap-breakdown.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'COMPLETE_FULL_MAPPING_OVERLAP_BREAKDOWN_NO_NEW_INFERENCE','results':rows,'limits':limits.query()});print(json.dumps([{'meeting':r['meeting'],'regions':{k:{x:v.get(x) for x in ['audioRegionSeconds','derWithFrozenGlobalAssignment']} for k,v in r['regions'].items()}} for r in rows]),flush=True)
