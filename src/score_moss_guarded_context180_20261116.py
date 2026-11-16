"""Original whole-source raw-text scoring; never promotes local block IDs."""
from pathlib import Path
from datetime import datetime
import argparse
import json
from meeting_acoustic_contract_20261116 import read,sha,require
from score_joint_whole_meetings_20261115 import lexical_references,units,measure,parse_native
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--meeting',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
    C=read(a.control)
    for item in C['files']:require(sha(item['file'])==item['sha256'],'Frozen original score dependency changed')
    P=read(C['protocol'])
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Inference source binding changed')
    case=next(r for r in read(C['wholeReferences'])['cases'] if r['meeting']==a.meeting)
    done=read(a.run/(a.meeting+'-completed.json'));state=read(a.run/'state.json')
    require(state['nativeRawTextControlExact'] and done['binding']==state['binding']
            and done['binding']['protocolSha256']==sha(C['protocol'])
            and done['naturalEos'] and done['noFramesDroppedOrDuplicated'],'Incomplete original source')
    require(done['frames']==case['frames'] and done['audioSha256']==case['audioSha256'],'Whole source identity changed')
    reference=lexical_references(case);language=case['language']
    ref=[v for row in reference for v in units(row['text'],language)]
    require(sha(case['baselineTextFile'])==case['baselineTextSha256'],'Original Qwen baseline changed')
    baseline=read(case['baselineTextFile']);base=measure(ref,units(baseline[case['baselineTextKey']],language))
    require(base['referenceUnits']==case['expectedReferenceUnits'] and base['errors']==case['expectedBaselineErrors'],
            'Original complete-source score not reproduced')
    expected=0;hyp=[];rows=[];invalid=[];residuals=[];seconds=0.
    for block in done['blocks']:
        require(block['startFrame']==expected and block['endFrame']>expected,'Gap/duplicate original audio')
        require(sha(block['file'])==block['sha256'],'Generated block changed')
        out=read(block['file']);require(out['binding']==done['binding'] and out['naturalEos']
            and out['meeting']==a.meeting and out['audioSha256']==case['audioSha256']
            and (out['startFrame'],out['endFrame'])==(block['startFrame'],block['endFrame']),
            'Block/audio/model pairing changed')
        parsed,all_rows,residual=parse_native(out['rawDecoded'])
        hyp.extend(v for r in all_rows for v in units(r['text'],language))
        invalid.extend({'block':out['id'],'index':i,'start':r['start'],'end':r['end']}
            for i,r in enumerate(parsed) if not 0<=r['start']<r['end']<=out['audioSeconds'])
        residuals.extend({'block':out['id'],**r} for r in residual)
        rows.append({'id':out['id'],'frames':out['frames'],'segments':len(parsed),
                     'generatedTokens':len(out['generatedIds']),'seconds':out['seconds']})
        seconds+=out['seconds'];expected=block['endFrame']
    require(expected==case['frames'],'Original final tail not included')
    score=measure(ref,hyp)
    result={'state':'COMPLETE_NATIVE_CONTEXT180_ORIGINAL_RAW_TEXT_SCORED_NOT_PRODUCT_QUALIFIED',
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),'meeting':a.meeting,'language':language,
        'protocolSha256':sha(C['protocol']),'completedSourceSha256':sha(a.run/(a.meeting+'-completed.json')),
        'scorerSha256':sha(__file__),'rawText':score,'baselineRawText':base,
        'rawEditsReduced':base['errors']-score['errors'],
        'relativeRawErrorReduction':(base['errors']-score['errors'])/base['errors'],
        'rawFivePercentGate':score['errorRate']<.05,'rawTwoPercentTarget':score['errorRate']<=.02,
        'allOriginalFramesCoveredExactlyOnce':True,'audioSeconds':case['audioSeconds'],
        'inferenceSeconds':seconds,'realTimeFactor':seconds/case['audioSeconds'],
        'blocks':rows,'invalidLocalTimeSegments':invalid,'allLexicalResidualsCounted':True,
        'residualUnparsed':residuals,'allLocalSpeakerIdsCountedForRawText':True,
        'continuousWholeMeetingSpeakerIdentityMeasured':False,
        'globalSpeakerActivityOrDERChangedByThisRawASR':False,
        'originalReferenceAndGatesChanged':False,'nativeGeneratedIdControlExact':state['nativeControlExact'],
        'rawLexicalControlExact':state['nativeRawTextControlExact'],
        'runtimeControlProofSha256':state['runtimeControlProofSha256'],
        'trainingUpdates':0,'newInferenceByScorer':0,
        'qualityQualified':False,'saleQualified':False,
        'scope':'Previously seen original far-field single-channel development source, no reference-selected cropping. Each fixed180s block resets native speaker IDs, so this raw-text result cannot qualify diarization or per-person transcript quality.',
        'limits':limits.query()}
    require(not a.output.exists(),'Preserve immutable completed score')
    atomic_json(a.output,result)
    print(json.dumps({k:result[k] for k in ['state','meeting','rawText','baselineRawText','rawEditsReduced','realTimeFactor']},ensure_ascii=False))


if __name__=='__main__':main()
