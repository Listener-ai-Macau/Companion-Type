"""Independent paired English adaptation score with the original12/709 words.

Scoring references never enter the GPU recipe. This admission can authorize
whole-source evaluation, not deployment or bilingual/diarization acceptance.
"""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse,json,math
from meeting_acoustic_contract_20261116 import read,require,sha
from score_sequential_meetings_20261115 import measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
from tdt_adaptation_contract_20261117 import require_final_checkpoint
from tdt_adaptation_checkpoint_20261116 import committed_tdt_checkpoint

def summarize_pair(rows,gate):
    require(gate['maximumEnglishErrors']==99 and gate['minimumRelativeErrorReductionVsSameProfileBaseline']==.2,
        'Frozen original improvement gate changed')
    words=sum(r['referenceWords'] for r in rows);base=sum(r['baselineErrors'] for r in rows)
    errors=sum(r['candidateErrors'] for r in rows);meetings=defaultdict(list)
    for row in rows:meetings[row['meeting']].append(row)
    grouped=[{'meeting':name,'referenceWords':sum(r['referenceWords'] for r in items),
        **{key:sum(r[key] for r in items) for key in ['baselineErrors','candidateErrors','priorMossErrors']}}
        for name,items in sorted(meetings.items())]
    require(words==gate['referenceWords']==709,'Original English reference denominator changed')
    maximum=min(99,base*4//5)
    advance=errors<=maximum and all(r['candidateErrors']<=min(r['baselineErrors'],r['priorMossErrors']) for r in grouped)
    return {'referenceWords':words,'baselineErrors':base,'candidateErrors':errors,
        'baselineWer':base/words,'candidateWer':errors/words,'maximumErrorsForThisPairedAdmission':maximum,
        'relativeErrorReductionVsSameProfileBaseline':(base-errors)/base if base else None,
        'meetings':grouped,'advanceToCompleteSources':advance,'englishFivePercentFloorPassedOnThisExposedSubset':errors/words<.05,
        'englishTwoPercentTargetPassedOnThisExposedSubset':errors/words<=.02}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);C=read(a.control)
    for entry in C['files']:require(sha(entry['file'])==entry['sha256'],'Frozen scoring dependency changed')
    P=read(C['protocol']);plan=read(P['dataPlan'])
    expected={'protocolSha256':sha(C['protocol']),'workerSha256':sha(C['worker']),
        'publishedWeightsSha256':P['weights']['sha256'],'dataSha256':plan['trainingManifestSha256']}
    training=read(a.run/'training-completed.json')
    require(training['binding']==expected and training['completedTrainingExamples']==475
        and training['candidateOptimizerUpdates']==119,'Fixed one-epoch candidate incomplete')
    preflight=read(a.run/'preflight/completed.json')
    require(preflight['binding']==expected
        and preflight['state']=='PASS_REAL_TDT_GPU_TRAINING_AND_CHECKPOINT_PREFLIGHT'
        and preflight['checkpointExactRoundtrip'] and preflight['tinyLossGradientProofPassed']
        and preflight['steadyAdamStatesPresentForMaximumShape']
        and preflight['integerBuffersOptimizerStepsAndRngExactRoundtrip']
        and preflight['preflightParameterUpdates']==1 and preflight['preflightWeightsMustNotInitializeCandidate'],
        'Actual GPU preflight proof missing')
    _,checkpoint=committed_tdt_checkpoint(a.run/'checkpoints',expected)
    candidate_identity=require_final_checkpoint(checkpoint,training)
    cases={r['id']:r for r in read(P['validationAudioOnly'])}
    require(len(cases)==12,'Original12 English inputs missing')
    references={r['id']:r for r in read(C['references']) if r['language']=='English' and r['role']=='validation'}
    require(set(references)==set(cases),'Scoring references differ from original English inputs')
    original={r['id']:r for r in read(C['qwenBaseline'])['cases']}
    prior={r['id']:r for r in read(C['mossBaseline'])['cases']}
    outputs={};states={}
    for phase in ['baseline','validate']:
        state=read(a.run/phase/'completed.json');states[phase]=state
        require(state['state']=='COMPLETE_TDT_'+phase.upper()+'_12_PENDING_INDEPENDENT_SCORE'
            and state['binding']==expected and len(state['completed'])==12,'Incomplete/different '+phase)
        require(state['parameterUpdates']==0 and state['candidateOptimizerUpdates']==(119 if phase=='validate' else 0),
            'Inference phase unexpectedly updated weights')
        factory=read(a.run/phase/'factory-load.json')
        require(factory['fileSha256']==factory['deviceRoundtripSha256']==P['weights']['sha256'],
            'Factory native tensor byte roundtrip unproven')
        if phase=='validate':require(state['evaluatedCheckpoint']==candidate_identity,'Validation state checkpoint differs')
        packets={}
        for entry in state['completed']:
            file=Path(entry['file']);require(file.resolve().parent==(a.run/phase/'results').resolve(),
                'Output escaped phase results')
            require(sha(file)==entry['sha256'],'Frozen output bytes changed')
            packet=read(file);identity=packet['id'];require(identity in cases and identity not in packets,'Unexpected/duplicate case')
            audio=cases[identity]
            require(packet['binding']==expected and packet['phase']==phase
                and packet['audioSha256']==audio['audioSha256'] and packet['inputFrames']==audio['frames']
                and packet['allInputFramesPreserved'] and packet['naturalTermination'],'Input/model/termination mismatch')
            require(packet['wordsPostEdited'] is False and packet['repeatedLexicalTokensCollapsed'] is False
                and packet['referenceUsed'] is False,'Raw lexical policy changed')
            require(packet['evaluatedCheckpoint']==(candidate_identity if phase=='validate' else None),
                'Decoded weights do not match the declared phase')
            packets[identity]=packet
        require(set(packets)==set(cases),'Missing original English output');outputs[phase]=packets
    rows=[]
    for identity,case in sorted(references.items()):
        baseline=measure(case['rawReferenceText'],outputs['baseline'][identity]['text'],'English')
        candidate=measure(case['rawReferenceText'],outputs['validate'][identity]['text'],'English')
        require(baseline['referenceUnits']==candidate['referenceUnits']==original[identity]['referenceUnits']
            ==prior[identity]['raw']['referenceUnits'],'Original per-case denominator changed')
        rows.append({'id':identity,'meeting':case['meeting'],'referenceWords':baseline['referenceUnits'],
            'baselineErrors':baseline['errors'],'candidateErrors':candidate['errors'],
            'priorMossErrors':prior[identity]['raw']['errors'],'priorQwenErrors':original[identity]['errors'],
            'baselineOperations':{k:baseline[k] for k in ['substitutions','deletions','insertions']},
            'candidateOperations':{k:candidate[k] for k in ['substitutions','deletions','insertions']}})
    require(sum(r['priorMossErrors'] for r in rows)==124 and sum(r['priorQwenErrors'] for r in rows)==141,
        'Frozen historical baselines changed')
    result=summarize_pair(rows,C['admissionGate'])
    result.update(state='FIXED_ONE_EPOCH_ENGLISH_ADAPTATION_'+('ADVANCE_TO_WHOLE_SOURCE_VALIDATION'
        if result['advanceToCompleteSources'] else 'REJECT_PAIRED_ADMISSION_NO_GRID'),
        at=datetime.now().astimezone().isoformat(timespec='seconds'),cases=rows,
        evaluatedCheckpoint=candidate_identity,trainingExamples=475,candidateOptimizerUpdates=119,
        protocolSha256=sha(C['protocol']),controlSha256=sha(a.control),scorerSha256=sha(__file__),
        baselineStateSha256=sha(a.run/'baseline/completed.json'),validationStateSha256=sha(a.run/'validate/completed.json'),
        admissionGate=C['admissionGate'],originalReferencesAndNormalizationUnchanged=True,
        referencesWereReadByIndependentScorerOnly=True,validationLabelsUsedForCheckpointSelection=False,
        exposedSubsetOnly=True,heldOutBlindCohortEvaluated=False,wholeSourceAcceptance=False,
        speakerAttributionEvaluated=False,chineseEngineChanged=False,automaticBilingualRoutingAccepted=False,
        newNeuralCallsByScorer=0,parameterUpdatesByScorer=0,qualityQualified=False,saleQualified=False,limits=limits.query())
    require(not a.output.exists(),'Preserve completed score');atomic_json(a.output,result)
    print(json.dumps({k:result[k] for k in ['state','baselineErrors','candidateErrors','candidateWer','advanceToCompleteSources','meetings']},ensure_ascii=False))

if __name__=='__main__':main()
