"""Independent fixed bilingual frontend comparison; all original words count."""
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
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);C=read(a.control)
    for item in C['files']:require(sha(item['file'])==item['sha256'],'Frontend score binding changed')
    P=read(C['protocol'])
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frontend pipeline source changed')
    final=read(a.run/'asr/completed.json');enhance=read(a.run/'enhance/completed.json')
    require(final['state']=='COMPLETE_FIXED_OFFICIAL_FRCRN_ASR_PENDING_INDEPENDENT_SCORING'
        and final['nativeControlExact'] and len(final['completed'])==25
        and final['enhancementCompletedSha256']==sha(a.run/'enhance/completed.json')
        and final['binding']==enhance['binding'] and final['binding']['protocolSha256']==sha(C['protocol']),
        'Incomplete/different frontend comparison')
    refs={c['id']:c for c in read(C['references']) if c['role']=='validation'}
    base={c['id']:c for c in read(C['baseline'])['cases']};originals={c['id']:c for c in read(P['audioOnly'])}
    inputs={c['id']:c for c in enhance['completed']};rows=[]
    for entry in final['completed']:
        require(sha(entry['file'])==entry['sha256'],'ASR output changed')
        out=read(entry['file']);require(out['binding']==final['binding'] and out['naturalEos'],'Failed output')
        if out['kind']=='unchanged-native-control':
            require(out['generatedIds']==P['asrControlIds'],'Exact native ASR control mismatch');continue
        case=refs[out['id']];source=inputs[case['id']]
        require(source['originalAudioSha256']==originals[case['id']]['audioSha256']
            and out['audioSha256']==source['sha256'] and sha(source['file'])==source['sha256'],
            'Original/enhanced/model pairing differs')
        score=measure(case['rawReferenceText'],out['text'],case['language']);old=base[case['id']]
        require(score['referenceUnits']==old['referenceUnits'],'Reference denominator changed')
        rows.append({'id':case['id'],'meeting':case['meeting'],'language':case['language'],
            'referenceUnits':score['referenceUnits'],'originalErrors':old['errors'],'enhancedErrors':score['errors'],
            'substitutions':score['substitutions'],'deletions':score['deletions'],'insertions':score['insertions']})
    require(len(rows)==24 and len({r['id'] for r in rows})==24,'Fixed24 cohort missing/duplicated')
    def aggregate(items):
        n=sum(r['referenceUnits'] for r in items);before=sum(r['originalErrors'] for r in items);after=sum(r['enhancedErrors'] for r in items)
        return {'cases':len(items),'referenceUnits':n,'originalErrors':before,'enhancedErrors':after,
            'originalErrorRate':before/n,'enhancedErrorRate':after/n,'relativeErrorReduction':(before-after)/before,
            'substitutions':sum(r['substitutions'] for r in items),'deletions':sum(r['deletions'] for r in items),
            'insertions':sum(r['insertions'] for r in items)}
    languages={lang:aggregate([r for r in rows if r['language']==lang]) for lang in ['English','Chinese']}
    require((languages['English']['referenceUnits'],languages['English']['originalErrors'])==(709,141)
        and (languages['Chinese']['referenceUnits'],languages['Chinese']['originalErrors'])==(1258,73),'Original baseline changed')
    groups=defaultdict(list)
    for row in rows:groups[(row['language'],row['meeting'])].append(row)
    meetings=[{'language':key[0],'meeting':key[1],**aggregate(items)} for key,items in groups.items()]
    no_regression=all(r['enhancedErrors']<=r['originalErrors'] for r in meetings)
    keep=languages['English']['relativeErrorReduction']>=.2 and no_regression
    result={'state':'FIXED_OFFICIAL_FRONTEND_'+('ADVANCE_TO_WHOLE_SOURCE_VALIDATION' if keep else 'REJECT_NO_USEFUL_BILINGUAL_GAIN'),
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),'languages':languages,'meetings':meetings,'rows':rows,
        'bothLanguagesEachMeetingNoRegression':no_regression,'advanceToWholeSources':keep,
        'retentionGate':P['retentionGate'],'originalReferencesAndWordsUnchanged':True,
        'all25AsrInputsCompleteWithExactNativeControl':True,'trainingUpdates':0,'newInferenceByScorer':0,
        'qualityQualified':False,'saleQualified':False,'scope':P['scope'],
        'scorerSha256':sha(__file__),'protocolSha256':sha(C['protocol']),'limits':limits.query()}
    require(not a.output.exists(),'Preserve completed frontend score')
    atomic_json(a.output,result);print(json.dumps({'state':result['state'],'languages':languages,'advanceToWholeSources':keep},ensure_ascii=False))


if __name__=='__main__':main()
