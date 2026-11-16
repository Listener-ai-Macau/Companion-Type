"""Independent raw-runtime admission and fixed24 paired enhancement scoring."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse
import json
from meeting_acoustic_contract_20261116 import read,require,sha
from score_sequential_meetings_20261115 import measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--mode',choices=['raw','paired'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);C=read(a.control);P=read(C['protocol'])
    for item in C['files']+P['files']:require(sha(item['file'])==item['sha256'],'Frozen pairing dependency changed')
    refs={r['id']:r for r in read(C['references']) if r['role']=='validation'}
    originals={r['id']:r for r in read(P['audioOnly'])};baseline={r['id']:r for r in read(C['baseline'])['cases']}
    raw=read(a.run/'raw/completed.json')
    require(raw['state']=='COMPLETE_GUARDED_RAW25_PENDING_SCORE' and len(raw['completed'])==25
        and raw['binding']['protocolSha256']==sha(C['protocol']),'Raw same-profile cohort incomplete')
    def outputs(final,kind):
        by_id={}
        for entry in final['completed']:
            require(sha(entry['file'])==entry['sha256'],'Paired ASR result changed')
            out=read(entry['file'])
            require(out['binding']==raw['binding'] and out['naturalEos'] and not out['referenceUsed']
                and not out['wordsPostEdited'] and out['trainingUpdates']==0,'Invalid paired ASR output')
            if out['kind']=='control':continue
            require(out['kind']==kind and out['id'] not in by_id,'Kind/uniqueness changed')
            by_id[out['id']]=out
        require(set(by_id)==set(refs)==set(originals) and len(by_id)==24,'Original fixed24 cases differ')
        return by_id
    raw_outputs=outputs(raw,'raw');enhanced=None;inputs=None;final=None
    if a.mode=='paired':
        final=read(a.run/'asr/completed.json');enhance=read(a.run/'enhance/completed.json')
        require(final['state']=='COMPLETE_GUARDED_ENHANCED25_PENDING_SCORE'
            and final['pairedControlExact'] and len(final['completed'])==25
            and final['binding']==enhance['binding']==raw['binding']
            and final['rawCompletedSha256']==sha(a.run/'raw/completed.json')
            and final['enhancementCompletedSha256']==sha(a.run/'enhance/completed.json')
            and enhance['state']=='COMPLETE_GUARDED_FRCRN24_ALL_FRAMES','Paired phases/control incomplete')
        left=read(a.run/'raw/results/native-original-control.json');right=read(a.run/'asr/results/native-original-control.json')
        require(left['generatedIds']==right['generatedIds'],'Exact same-profile model reload control differs')
        enhanced=outputs(final,'enhanced');inputs={c['id']:c for c in enhance['completed']}
        require(set(inputs)==set(refs),'Enhanced input cohort changed')
    rows=[]
    for identity,case in refs.items():
        out=raw_outputs[identity];original=originals[identity];old=baseline[identity]
        require(out['audioSha256']==original['audioSha256'],'Raw runtime original PCM differs')
        score=measure(case['rawReferenceText'],out['text'],case['language'])
        require(score['referenceUnits']==old['referenceUnits'],'Reference denominator changed')
        row={'id':identity,'meeting':case['meeting'],'language':case['language'],'referenceUnits':score['referenceUnits'],
            'originalErrors':old['errors'],'rawErrors':score['errors'],
            'rawSubstitutions':score['substitutions'],'rawDeletions':score['deletions'],'rawInsertions':score['insertions']}
        if enhanced is not None:
            source=inputs[identity];out=enhanced[identity]
            require(source['originalAudioSha256']==original['audioSha256'] and source['frames']==original['frames']
                and source['originalGainRestored'] and sha(source['file'])==source['sha256']
                and out['audioSha256']==source['sha256'],'Original/full enhanced sample pairing differs')
            score=measure(case['rawReferenceText'],out['text'],case['language'])
            require(score['referenceUnits']==row['referenceUnits'],'Enhanced denominator changed')
            row.update(enhancedErrors=score['errors'],enhancedSubstitutions=score['substitutions'],
                enhancedDeletions=score['deletions'],enhancedInsertions=score['insertions'])
        rows.append(row)
    def aggregate(items):
        n=sum(r['referenceUnits'] for r in items)
        d={'cases':len(items),'referenceUnits':n}
        for key in ['original','raw']+(['enhanced'] if enhanced is not None else []):
            d[key+'Errors']=sum(r[key+'Errors'] for r in items);d[key+'ErrorRate']=d[key+'Errors']/n
        if enhanced is not None:d['pairedRelativeErrorReduction']=(d['rawErrors']-d['enhancedErrors'])/d['rawErrors']
        return d
    languages={lang:aggregate([r for r in rows if r['language']==lang]) for lang in ['English','Chinese']}
    require((languages['English']['referenceUnits'],languages['English']['originalErrors'])==(709,141)
        and (languages['Chinese']['referenceUnits'],languages['Chinese']['originalErrors'])==(1258,73),'Original baseline units/edits changed')
    groups=defaultdict(list)
    for row in rows:groups[(row['language'],row['meeting'])].append(row)
    meetings=[{'language':k[0],'meeting':k[1],**aggregate(items)} for k,items in groups.items()]
    raw_ok=all(r['rawErrors']<=r['originalErrors'] for r in meetings)
    if a.mode=='raw':
        state='PASS_SAME_PROFILE_RAW_BILINGUAL_NONREGRESSION' if raw_ok else 'REJECT_NATIVE_PROFILE_RAW_RECOGNITION_REGRESSION'
        keep=False
    else:
        keep=raw_ok and all(r['enhancedErrors']<=r['rawErrors'] for r in meetings)
        keep=keep and languages['English']['pairedRelativeErrorReduction']>=P['retentionGate']['englishRelativeErrorReductionAtLeast']
        state='ADVANCE_GUARDED_FRCRN_TO_WHOLE_SOURCES' if keep else 'REJECT_GUARDED_FRCRN_NO_USEFUL_BILINGUAL_GAIN'
    result={'state':state,'at':datetime.now().astimezone().isoformat(timespec='seconds'),'mode':a.mode,
        'languages':languages,'meetings':meetings,'rows':rows,'rawEachMeetingNonregression':raw_ok,
        'oldDefaultControlExact':raw.get('oldDefaultControlExact'),'sameProfileReloadControlExact':final.get('pairedControlExact') if final else None,
        'advanceToWholeSources':keep,'scope':P['scope'],'rawAdmissionGate':P['rawAdmissionGate'],
        'retentionGate':P['retentionGate'],'protocolSha256':sha(C['protocol']),'scorerSha256':sha(__file__),
        'rawCompletedSha256':sha(a.run/'raw/completed.json'),'trainingUpdates':0,'newInferenceByScorer':0,
        'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    require(not a.output.exists(),'Preserve finished score');atomic_json(a.output,result)
    print(json.dumps({k:result[k] for k in ['state','languages','rawEachMeetingNonregression','advanceToWholeSources']},ensure_ascii=False))

if __name__=='__main__':main()
