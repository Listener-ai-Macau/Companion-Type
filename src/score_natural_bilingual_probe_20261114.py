"""Strict character diagnostic of one frozen natural mixed-language utterance.

References are opened only here, after local inference; no acceptance shortcut.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,ast,hashlib,json,re,unicodedata
from rapidfuzz.distance import Levenshtein
from moss_windows_resource_limits_20261104 import WorkerLimits
ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();assert not args.output.exists()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=96*1024**2)
    protocol=read(args.control/'audio-only-protocol.json')
    assert protocol['naturalConversation'] and not protocol['constructedLanguageConcatenation']
    session=Path(protocol['localSession']);doc=read(session/'document.json');state=read(session/'session.json')
    worker=read(args.run/'worker-state.json');run=read(args.run/'run.json')
    assert doc['isFinal'] and state['sealed'] and run['exitCode']==0
    assert doc['confirmedAudioFrames']==doc['finalDecodedFrames']==protocol['frames']
    assert sha(session/'audio.pcm')==protocol['pcmSha256'] and sha(protocol['audio'])==protocol['audioSha256']
    assert len(doc['utterances'])==1
    result=read(next((session/'results').glob('*-final.json')))
    assert result['inferenceBinding']==worker['binding'] and result['result']['referenceUsed'] is False
    assert not result['result']['wordsPostEdited']
    for name,key in [('companion_local_qwen_worker_20261114.py','workerSourceSha256'),
                     ('companion_local_pcm_session_20261114.py','sessionParserSourceSha256'),
                     ('companion_local_decode_recovery_20261114.py','localRecoverySourceSha256')]:
        assert sha(ROOT/'model-research/src'/name)==worker['binding'][key]
    normalizer=ROOT/'model-research/src/full_meeting_transcript_metrics_20261103.py'
    assert sha(normalizer)=='45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'
    module=ast.parse(normalizer.read_text(encoding='utf-8'));scope={'re':re,'unicodedata':unicodedata}
    exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'frozen-normalizer','exec'),scope)
    # This is the first reference read in this scoring process. Its text was
    # never an argument, prompt or session field of the inference worker.
    reference=read(args.control/'scoring-only.json');assert reference['rowId']==protocol['rowId']
    ref=scope['normalize'](reference['reference']);hyp=scope['normalize'](doc['text']);assert ref
    edits=Levenshtein.editops(ref,hyp)
    record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
            'state':'NATURAL_MIXED_UTTERANCE_LOCAL_RESULT_SCORED_NOT_MEETING_QUALIFICATION',
            'dataset':protocol['dataset'],'metadataRevision':protocol['metadataRevision'],
            'license':protocol['license'],'rowId':protocol['rowId'],'seconds':protocol['audioSeconds'],
            'audioSha256':protocol['audioSha256'],'pcmSha256':protocol['pcmSha256'],
            'reference':reference['reference'],'hypothesis':doc['text'],
            'referenceCharacters':len(ref),'hypothesisCharacters':len(hyp),'totalEdits':len(edits),
            'edits':{k:sum(op.tag==k for op in edits) for k in ['replace','delete','insert']},
            'strictCharacterErrorRate':len(edits)/len(ref),
            'diagnosticBelowFivePercent':len(edits)/len(ref)<.05,
            'bothScriptsProduced':bool(re.search('[\u4e00-\u9fff]',doc['text']) and re.search('[A-Za-z]',doc['text'])),
            'modelLanguageHeader':doc['utterances'][0].get('language'),
            'reviewRequired':doc.get('reviewRequired'),
            'actualNeuralCalls':worker['neuralCalls'],'coldModelLoadSeconds':worker.get('modelLoadSeconds'),
            'freshInferenceSeconds':worker['freshInferenceSeconds'],'privatePeakBytes':run['privatePeakBytes'],
            'binding':worker['binding'],'referenceReceiptSha256':sha(args.control/'scoring-only.json'),
            'normalizerSourceSha256':sha(normalizer),'inferenceReferenceUsed':False,
            'limitations':['One4.03second utterance, not a complete bilingual meeting or a generalization claim.',
                           'Character metric preserves lexical fillers and numbers; this is not the official ASCEND mixed-word MER benchmark.',
                           'No verified diarization or word timing; all audio words and raw decoder nodes retained.'],
            'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k not in ['binding','limits','limitations']},ensure_ascii=False))

if __name__=='__main__':main()
