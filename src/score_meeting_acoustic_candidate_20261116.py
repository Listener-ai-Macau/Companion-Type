"""Independent original-reference scoring; never imported by model workers."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import argparse
import json
from meeting_acoustic_contract_20261116 import accepted_output, committed_checkpoint, read, require, sha
from score_sequential_meetings_20261115 import measure
from score_joint_whole_meetings_20261115 import lexical_references, units, measure as whole_measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control',required=True,type=Path)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--baseline-replay',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args(); control = read(args.control)
    limits = WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
    for item in control['files']:
        require(sha(item['file']) == item['sha256'],'Scoring input/helper changed: '+item['file'])
    require(sha(control['packet']) == control['packetSha256'],'Training/evaluation packet changed')
    packet = read(control['packet'])
    outputs = {}
    cases = read(packet['evaluationAudioOnly'])
    baseline = {r['id']:r for r in read(control['strictBaseline'])['cases']}
    references = {r['id']:r for r in read(control['strictReferences']) if r['role'] == 'validation'}
    require(len(references) == 24,'Fixed validation cohort changed')
    if args.baseline_replay:
        require(args.run is None,'Baseline replay cannot consume a candidate run')
        for case in cases:
            if case['scope'] == 'strict-validation':
                outputs[case['id']] = {'text':baseline[case['id']]['hypothesis'],
                                        'audioSha256':case['audioSha256']}
        original = read(control['ordinaryOriginalLeaves'])['cases']
        for leaf in original:
            require(sha(leaf['rawAsrFile']) == leaf['rawAsrSha256'],'Original native leaf changed')
            value = read(leaf['rawAsrFile'])
            for key in leaf['rawAsrTextPath']:
                value = value[key]
            outputs['S_R004S03C01-'+leaf['id']] = {'text':value,'audioSha256':leaf['wavSha256']}
        evaluation_sha = None
    else:
        require(args.run is not None,'Candidate evaluation run required')
        state = read(args.run/'evaluation-complete.json')
        train_binding = {'packetSha256':control['packetSha256'],'workerSha256':sha(packet['trainingWorker'])}
        complete = read(Path(control['trainingRun'])/'training-complete.json')
        require(complete['binding'] == train_binding and complete['completedExamples'] == 944
                and complete['optimizerUpdates'] == 472,'Candidate is not the fixed final epoch')
        checkpoint,receipt = committed_checkpoint(control['trainingRun'],train_binding)
        expected = {'packetSha256':control['packetSha256'],'checkpointSha256':receipt['sha256'],
                    'workerSha256':sha(packet['evaluationWorker'])}
        require(state['state'] == 'COMPLETE_FIXED_RAW_ASR_EVALUATION_PENDING_INDEPENDENT_SCORING'
                and state['binding'] == expected,'Incomplete/different candidate evaluation')
        for item in state['completed']:
            require(sha(item['file']) == item['sha256'],'Candidate output changed')
            output = read(item['file'])
            require(output['binding'] == expected and accepted_output(output),'Invalid candidate output')
            outputs[item['id']] = output
        evaluation_sha = sha(args.run/'evaluation-complete.json')
    require(set(outputs) == {c['id'] for c in cases},'Missing/extra evaluated leaf')
    rows = []
    for identifier,case in references.items():
        output = outputs[identifier]
        require(output['audioSha256'] == case['wavSha256'],'Strict reference/audio pairing changed')
        result = measure(case['rawReferenceText'],output['text'],case['language'])
        original = baseline[identifier]
        check = measure(case['rawReferenceText'],original['hypothesis'],case['language'])
        require(check['errors'] == original['errors'] and check['referenceUnits'] == original['referenceUnits'], 'Original strict baseline no longer reproduces')
        rows.append({'id':identifier,'meeting':case['meeting'],'language':case['language'],
                     'referenceUnits':result['referenceUnits'],'errors':result['errors'],
                     'errorRate':result['rate'],'substitutions':result['substitutions'],
                     'deletions':result['deletions'],'insertions':result['insertions'],
                     'baselineErrors':original['errors'],'baselineErrorRate':original['rate'],
                     'rawFloor95Passed':result['rate'] < .05,'rawTarget98Reached':result['rate'] <= .02})
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['language']].append(row)
    groups = []
    for language,items in grouped.items():
        denominator = sum(r['referenceUnits'] for r in items)
        errors = sum(r['errors'] for r in items)
        groups.append({'language':language,'cases':len(items),'referenceUnits':denominator,
                       'errors':errors,'errorRate':errors/denominator,
                       'baselineErrors':sum(r['baselineErrors'] for r in items),
                       'rawFloor95Passed':errors/denominator < .05,
                       'rawTarget98Reached':errors/denominator <= .02})
    ordinary = read(control['ordinaryReferences'])['cases'][0]
    require(ordinary['meeting'] == 'S_R004S03C01','Wrong ordinary meeting')
    events = lexical_references(ordinary)
    reference = units(''.join(e['text'] for e in events),'Chinese')
    require(sha(ordinary['baselineTextFile']) == ordinary['baselineTextSha256'],'Ordinary native baseline changed')
    old = whole_measure(reference,units(read(ordinary['baselineTextFile'])['text'],'Chinese'))
    require(old['errors'] == 461 and old['referenceUnits'] == 8325,'Original whole baseline no longer reproduces')
    leaves = sorted([c for c in cases if c['scope'] == 'ordinary-whole-leaf'],key=lambda r:r['sourceStartFrame'])
    require(len(leaves) == 79 and leaves[0]['sourceStartFrame'] == 0
            and leaves[-1]['sourceEndFrame'] == ordinary['frames'],'Ordinary meeting coverage changed')
    require(all(a['sourceEndFrame'] == b['sourceStartFrame'] for a,b in zip(leaves,leaves[1:])), 'Ordinary meeting gap/duplicate')
    for leaf in leaves:
        require(outputs[leaf['id']]['audioSha256'] == leaf['audioSha256'],'Ordinary output/audio pairing changed')
    result = whole_measure(reference,units('\n'.join(outputs[c['id']]['text'] for c in leaves),'Chinese'))
    ordinary_result = {'meeting':ordinary['meeting'],'candidate':result,'baseline':old,
                       'rawFloor95Passed':result['errorRate'] < .05,
                       'rawTarget98Reached':result['errorRate'] <= .02,
                       'noRegression':result['errors'] <= old['errors']}
    if args.baseline_replay:
        require(result['errors'] == 461 and result['referenceUnits'] == 8325,'Whole native leaf replay changed words')
        require({g['language']:(g['errors'],g['referenceUnits']) for g in groups}
                == {'English':(141,709),'Chinese':(73,1258)},'Strict native replay changed scores')
    result = {'state':'PASS_RETAINED_NATIVE_RAW_SCORE_REPLAY_NO_CANDIDATE' if args.baseline_replay else 'FIXED_ACOUSTIC_PILOT_RAW_SCORED_NOT_PRODUCT_QUALIFIED',
              'at':datetime.now().astimezone().isoformat(timespec='seconds'),
              'evaluationStateSha256':evaluation_sha,
              'scoringControlSha256':sha(args.control),'scorerSha256':sha(__file__),
              'groups':groups,'cases':rows,'ordinaryChineseWhole':ordinary_result,
              'speakerAttributedTextMeasured':False,'diarizationMeasured':False,
              'factsMeasured':False,'blindHoldoutOpened':False,
              'originalScoringChanged':False,'productDefaultChanged':False,
              'baselineReplayOnly':args.baseline_replay,'newNeuralCallsByScorer':0,
              'qualityQualified':False,'saleQualified':False,'limits':limits.query(),
              'nextGate':'Report all raw regressions. Even a passing raw pilot still needs new-text alignment/continuous person attribution, per-person/facts/resource and unseen-meeting acceptance before adoption.'}
    require(not args.output.exists(),'Scoring receipt is immutable')
    atomic_json(args.output,result)
    print(json.dumps({'state':result['state'],'groups':groups,'ordinaryChineseWhole':ordinary_result},ensure_ascii=False))


if __name__ == '__main__':
    main()
