"""Reuse the Nov10 literal crosstalk diagnostic on completed native outputs.

No word deletion, ASR calls, speaker-identity claim or adjusted quality score.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,ast,difflib,hashlib,json,re,unicodedata
from reference_textgrid_20261104 import read_reference_intervals
from moss_windows_resource_limits_20261104 import WorkerLimits

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
CONTROL=ROOT/'docs/handoffs/20261109-paired-real-meeting'
TASKS=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-r2-runs')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()

def literal_examples(document,identity,by,normalize):
    # Exact Nov10 criteria: no target-reference speech in the input window,
    # +/-100ms annotation tolerance, >=12 contiguous other-reference chars.
    examples=[];absent=0
    for row in document['utterances']:
        start,end=row['startMs']/1000,row['endMs']/1000
        if any(r['start']<end+.1 and r['end']>start-.1 for r in by[identity]):continue
        absent+=1;hyp=normalize(row['text']);best=None
        for other,refs in by.items():
            if other==identity:continue
            for ref in refs:
                if ref['start']>=end+.1 or ref['end']<=start-.1:continue
                text=normalize(ref['text'])
                match=difflib.SequenceMatcher(None,hyp,text,autojunk=False).find_longest_match()
                if match.size>=12 and (best is None or match.size>best['literalCharacters']):
                    quote=hyp[match.a:match.a+match.size]
                    assert quote==text[match.b:match.b+match.size]
                    best={'inputWindowStartSeconds':start,'inputWindowEndSeconds':end,
                          'approximateInputWindowNotWordAlignment':True,'targetSource':identity,
                          'otherSource':other,'literalCharacters':match.size,
                          'normalizedLiteralQuote':quote,'reference':ref,'modelWindowText':row['text']}
        if best:examples.append(best)
    return {'id':identity,'transcribedInputWindowsWithNoTargetReferenceSpeech':absent,
            'suchWindowsWithAtLeastTwelveLiteralOtherSpeakerCharacters':len(examples),
            'examples':sorted(examples,key=lambda x:x['inputWindowStartSeconds'])[:4]}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--score',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    assert not args.output.exists(),'Retain previous diagnostic'
    limits=WorkerLimits(cpu_percent=5,memory_bytes=96*1024**2)
    normalizer=ROOT/'model-research/src/full_meeting_transcript_metrics_20261103.py'
    assert sha(normalizer)=='45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'
    module=ast.parse(normalizer.read_text(encoding='utf-8'));scope={'re':re,'unicodedata':unicodedata}
    exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'frozen-normalizer','exec'),scope)
    normalize=scope['normalize'];score=read(args.score);references=CONTROL/'fixed-asr-scoring-only.json'
    assert sha(references)==score['referenceManifestSha256']
    by={}
    for ref in read(references)['sourceReferences']:
        assert sha(ref['reference'])==ref['referenceSha256']
        by[ref['id']]=[r for r in read_reference_intervals(ref['reference']) if normalize(r['text'])]
    results=[]
    for scored in score['results']:
        identity=scored['id']
        if identity not in by:continue
        task_path=TASKS/identity/'task.json';task=read(task_path)
        assert sha(task_path)==scored['taskReceiptSha256']
        assert task['state']=='COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED'
        assert sha(task['output'])==task['outputSha256']==scored['outputSha256']
        document=read(task['output']);assert document['isFinal']
        result=literal_examples(document,identity,by,normalize)
        result.update(outputSha256=task['outputSha256'],unchangedStrictCer=scored['cer'])
        results.append(result)
    record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
            'state':'POSTHOC_NATIVE_LITERAL_OTHER_REFERENCE_DIAGNOSTIC_NOT_SCORE_ADJUSTMENT',
            'scoreReceiptSha256':sha(args.score),'referenceManifestSha256':sha(references),
            'methodReusedFrom':'audit_paired_headset_crosstalk_20261110.py',
            'methodSourceSha256':sha(Path(__file__).with_name('audit_paired_headset_crosstalk_20261110.py')),
            'minimumLiteralCharacters':12,'annotationToleranceSeconds':.1,'results':results,
            'neuralCalls':0,'asrWordsDeletedOrEdited':False,'strictScoresAdjusted':False,
            'limitations':['Posthoc examples only; not exhaustive insertion accounting.',
                           'Window times are approximate; exact speaker/word attribution is not established.',
                           'Other-reference literal matches support crosstalk in these examples, not every insertion.',
                           'Known headset identities are file assignments, not automatic diarization.'],
            'qualityQualified':False,'limits':limits.query()}
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'state':record['state'],'counts':[{k:v for k,v in r.items() if k!='examples'} for r in results]},ensure_ascii=False))

if __name__=='__main__':main()
