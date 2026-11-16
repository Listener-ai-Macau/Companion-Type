"""Microphone-view comparison only; never grants product qualification."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import argparse
import json
from meeting_acoustic_contract_20261116 import read,require,sha
from score_sequential_meetings_20261115 import measure
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits


def main():
    p=argparse.ArgumentParser(); p.add_argument('--control',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); control=read(a.control)
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
    for item in control['files']: require(sha(item['file'])==item['sha256'],'Diagnostic score binding changed')
    protocol=read(control['protocol']); state=read(a.run/'completed.json')
    expected={'protocolSha256':sha(control['protocol']),'workerSha256':sha(control['worker']),
              'modelSha256':protocol['modelSha256']}
    require(state['binding']==expected and state['nativeControlExact']
            and state['state']=='COMPLETE_PRETRAINED_MICROPHONE_DIAGNOSTIC_PENDING_INDEPENDENT_SCORING', 'Incomplete/different diagnostic')
    require(state['binding']['workerSha256']==sha(control['worker']), 'Diagnostic worker changed')
    cases={c['id']:c for c in read(control['references']) if c['language']=='English' and c['role']=='validation'}
    baseline={c['id']:c for c in read(control['baseline'])['cases']}
    audio={c['id']:c for c in read(protocol['audioOnly'])}
    rows=[]
    for item in state['completed']:
        require(sha(item['file'])==item['sha256'],'Diagnostic output changed')
        out=read(item['file']); require(out['binding']==state['binding'] and out['naturalEos'],'Invalid diagnostic output')
        require(out['id'] in audio and out['audioSha256']==audio[out['id']]['audioSha256']
                and out['caseId']==audio[out['id']]['caseId'],'Output/audio reference pairing changed')
        if out['kind']=='native-distant-control': continue
        case=cases[out['caseId']]; original=baseline[case['id']]
        score=measure(case['rawReferenceText'],out['text'],'English')
        rows.append({'id':case['id'],'meeting':case['meeting'],'referenceUnits':score['referenceUnits'],
                     'distantErrors':original['errors'],'headsetMixErrors':score['errors'],
                     'distantWer':original['rate'],'headsetMixWer':score['rate']})
    require(len(rows)==12 and len({r['id'] for r in rows})==12,'Fixed12 pairs required')
    denominator=sum(r['referenceUnits'] for r in rows); far=sum(r['distantErrors'] for r in rows); near=sum(r['headsetMixErrors'] for r in rows)
    require(denominator==709 and far==141,'Original distant score changed')
    grouped=defaultdict(list)
    for row in rows: grouped[row['meeting']].append(row)
    sources=[{'meeting':name,'referenceWords':sum(r['referenceUnits'] for r in items),
              'distantErrors':sum(r['distantErrors'] for r in items),
              'headsetMixErrors':sum(r['headsetMixErrors'] for r in items)} for name,items in grouped.items()]
    consistent=all(s['headsetMixErrors']<s['distantErrors'] for s in sources)
    result={'state':'PRETRAINED_MICROPHONE_DIAGNOSTIC_SCORED_NOT_PRODUCT_ACCEPTANCE',
            'at':datetime.now().astimezone().isoformat(timespec='seconds'),'rows':rows,'sources':sources,
            'referenceWords':denominator,'distantErrors':far,'headsetMixErrors':near,
            'distantWer':far/denominator,'headsetMixWer':near/denominator,
            'bothSourcesImproveInEasierRecording':consistent,
            'diagnosticAcousticConditionContributionMaterial':consistent and near<=far*.75,
            'diagnostic25PercentRelativeThresholdIsNotAProductGate':True,
            'headsetMixStillAboveFivePercent':near/denominator>=.05,
            'scope':'12 exposed English clips; headset-mix changes recording condition. It is not the product input or a claim that hardware is faulty. Multiple factors can remain.',
            'trainingUpdates':0,'newInferenceByScorer':0,'referenceOrWordsChanged':False,
            'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    require(not a.output.exists(),'Keep exited diagnostic immutable')
    atomic_json(a.output,result); print(json.dumps({k:result[k] for k in ['state','distantWer','headsetMixWer','diagnosticAcousticConditionContributionMaterial','qualityQualified']},ensure_ascii=False))


if __name__=='__main__': main()
