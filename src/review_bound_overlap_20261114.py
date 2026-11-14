"""Compare the predeclared same-Qwen original/extracted short controls.

References are post-inference diagnostics only. No invented partial-utterance
reference, whole-clip/pure-overlap CER, or automatic product promotion.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ast,hashlib,json,re,unicodedata

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
RUN=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/same-qwen-six20261114/run')
CONTROL=ROOT/'docs/handoffs/20261109-paired-real-meeting/sleep-continuation20261114'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    target=CONTROL/'same-qwen-overlap-review.json';assert not target.exists(),'Retain the previous review'
    batch=read(RUN/'batch.json');assert batch['state']=='COMPLETE_BOUND_NATIVE_CASES_UNSCORED'
    manifest=RUN.parent/'manifest.json';pack=RUN.parent/'model-pack.json'
    assert batch['binding']=={'manifestSha256':sha(manifest),'modelPackSha256':sha(pack)}
    cases=read(manifest);assert batch['completed']==[r['id'] for r in cases]
    former=read(ROOT/'model-research/evidence/20261108-competitive-sale-standard/two-lane-validation-20261109/paired-content-review.json')
    metrics=ROOT/'model-research/src/full_meeting_transcript_metrics_20261103.py'
    assert sha(metrics)=='45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'
    scope={'re':re,'unicodedata':unicodedata};module=ast.parse(metrics.read_text())
    exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'frozen-normalizer','exec'),scope)
    normalize=scope['normalize'];results={}
    for case in cases:
        path=RUN/'tasks'/case['id']/'task.json';task=read(path)
        assert task['state']=='COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED'
        assert task['binding']=={'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'modelPackSha256':sha(pack)}
        assert sha(Path(case['audio']))==case['audioSha256'] and sha(Path(task['output']))==task['outputSha256']
        output=read(Path(task['output']));assert output['isFinal']
        results[case['id']]={'text':output['text'],'audioSha256':case['audioSha256'],'outputSha256':task['outputSha256'],
                             'taskReceiptSha256':sha(path),'accumulatedKnownOwnedProcessSeconds':task['accumulatedKnownOwnedProcessSeconds'],
                             'attemptsWithUnknownDuration':task['attemptsWithUnknownDuration']}
    checks=[]
    for previous in former['cases']:
        prefix=previous['case'];mixed=results[prefix+'-mixture']['text']
        for person in previous['selectedTargetPeople']:
            name=prefix+'-native-'+person['nativePerson'];current=results[name]['text']
            reference=[r for r in previous['allIntersectingReferenceUtterancesForInspectionOnly']
                       if r['speaker']==person['referenceIdentityForScoringOnly'] and not r['crossesWindowBoundary']
                       and normalize(r['text'])]
            checks.append({'case':prefix,'nativePerson':person['nativePerson'],'knownPosthocReferenceIdentity':person['referenceIdentityForScoringOnly'],
                           'originalMixtureNativeQwen':mixed,'extractedNativeQwen':current,
                           'formerExtractedCloudAsr':previous['recognition'][name]['textFromCompleteProviderWords'],
                           'fullyContainedUtteranceExactPresence':[{'text':r['text'],'start':r['start'],'end':r['end'],
                                'inMixture':normalize(r['text']) in normalize(mixed),'inExtraction':normalize(r['text']) in normalize(current)} for r in reference],
                           'exactPresenceIsNotWordAlignmentOrCompleteRecognition':True})
    failed=next(c for c in checks if c['case']=='overlap-01' and c['nativePerson']=='3')
    assert any(r['text']=='对有的就是一些' and not r['inExtraction'] for r in failed['fullyContainedUtteranceExactPresence'])
    recovered=next(c for c in checks if c['case']=='overlap-00' and c['nativePerson']=='1')
    assert any(r['text']=='挺普遍的' and r['inExtraction'] for r in recovered['fullyContainedUtteranceExactPresence'])
    record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
            'state':'COMPLETE_SAME_QWEN_SHORT_CONTROL_SECOND_TARGET_FAILURE_DO_NOT_EXPAND',
            'results':results,'targetChecks':checks,'sameFrozenNativeRecognizerAcrossAllSix':True,
            'referenceUsedOnlyAfterInference':True,'newSeparationOrTrainingCalls':0,
            'interpretation':['The exact former extracted waveform supports 挺普遍的 under native Qwen; its former cloud error 交通便利 does not alone prove destroyed target audio.',
                              'Recognition back-end compatibility explains part of the former failure; this does not prove all extraction outputs preserve target speech.',
                              'The second target3 still fails the fully contained 对有的就是一些 and emits unrelated text. All-target content protection is not demonstrated.',
                              'Retain the original audio and unknown attribution. Stop the predeclared17-window expansion for this candidate; no tuning on these exposed clips.'],
            'wholeMeetingOrPureOverlapCerMeasured':False,'fullAutomaticIdentityQualification':False,
            'scope':'Two fixed8s contexts in one exposed six-person real meeting, four target streams; reference utterances can cross clip boundaries and other speakers appear outside central target pairs.',
            'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False}
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'state':record['state'],'results':results,'qualityQualified':False},ensure_ascii=False))

if __name__=='__main__':main()
