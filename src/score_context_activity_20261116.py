"""Original zero-collar activity score under the original whole-source mapping."""
from pathlib import Path
from datetime import datetime
import argparse
import json
from meeting_acoustic_contract_20261116 import read,sha,require
from score_joint_whole_meetings_20261115 import activity_score,rttm
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
    p.add_argument('--prediction',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);C=read(a.control)
    for item in C['files']:require(sha(item['file'])==item['sha256'],'Frozen activity scoring source changed')
    predicted=read(a.prediction);require(predicted['protocolSha256']==sha(C['predictionProtocol'])
        and not predicted['referencesRead'],'Different/reference-exposed prediction recipe')
    case=next(r for r in read(C['wholeReferences'])['cases'] if r['meeting']==predicted['meeting'])
    require(predicted['audioSha256']==case['audioSha256'],'Reference/audio pairing changed')
    require(sha(predicted['sourceRttm'])==predicted['sourceRttmSha256'],'Original journal changed')
    require(sha(case['activityReference'])==case['activityReferenceSha256'],'Original activity reference changed')
    reference=read(case['activityReference']) if case['activityKind']=='json' else rttm(case['activityReference'])
    baseline=activity_score(reference,rttm(predicted['sourceRttm']),case['audioSeconds'])
    require(abs(baseline['DER']-case['baselineDER'])<1e-8,'Original multi-voice DER not reproduced')
    values={}
    for name in ['mossMapped','combined']:
        item=predicted[name];require(sha(item['file'])==item['sha256'],'Closed predicted journal changed')
        values[name]=activity_score(reference,rttm(item['file']),case['audioSeconds'],
            identity=baseline['identityForScoringOnly'])
    rate=values['combined']['DER'];gain=(baseline['DER']-rate)/baseline['DER']
    structure=not predicted['invalidNativeTimeSegments'] and not predicted['unmatchedLocalSpeakerSegments']
    result={'state':'CONTEXT_ACTIVITY_UNION_SCORED_NOT_PRODUCT_QUALIFIED',
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),'meeting':case['meeting'],'language':case['language'],
        'originalRawMultiVoice':baseline,'mossMappedWithOriginalFixedIdentity':values['mossMapped'],
        'combinedWithOriginalFixedIdentity':values['combined'],'relativeDerReduction':gain,
        'nativeTimesAndAssociationStructurallyComplete':structure,
        'advanceToSecondEnglishSource':case['language']=='English' and gain>=.2 and structure,
        'originalDerTenPercentGate':rate<=.1 and structure,
        'oneOriginalWholeSourceIdentityMappingForAllConditions':True,'noPerBlockGoldPermutation':True,
        'collarSeconds':0,'overlapIncluded':True,'thresholdPaddingAndWordsChanged':False,
        'newNeuralCalls':0,'trainingUpdates':0,'qualityQualified':False,'saleQualified':False,
        'predictionSha256':sha(a.prediction),'scorerSha256':sha(__file__),
        'scope':'English-only activity supplement candidate; Chinese default remains the original continuous journal. ASR words, per-person text, facts, unseen meetings and end-user CPU execution remain separate gates.',
        'limits':limits.query()}
    require(not a.output.exists(),'Keep completed activity score immutable')
    atomic_json(a.output,result)
    print(json.dumps({k:result[k] for k in ['state','meeting','originalRawMultiVoice','mossMappedWithOriginalFixedIdentity',
        'combinedWithOriginalFixedIdentity','relativeDerReduction','advanceToSecondEnglishSource']},ensure_ascii=False))


if __name__=='__main__':main()
