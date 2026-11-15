"""Independently score the one completed fixed adapter trial; no inference."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,re,sys,unicodedata
from rapidfuzz.distance import Levenshtein

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',required=True,type=Path);p.add_argument('--run',required=True,type=Path);a=p.parse_args()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    target=a.control/'decision.json';assert not target.exists()
    state=read(a.run/'trial-state.json');assert state['state']=='COMPLETE_ONE_ADAPTER_TRIAL_INDEPENDENT_SCORING_PENDING' and state['finishedAt']
    assert state['trainingSteps']==128 and state['optimizerUpdates']==32
    assert read(a.run/'frozen-before.json')==read(a.run/'frozen-after.json')
    protocol=read(a.control/'protocol.json')
    assert sha(a.control/'validation-scoring-only.json')==protocol['validationScoringManifestSha256']
    source=Path(__file__).with_name('full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
    start=source.index('def normalize(');end=source.index('\ndef ',start+1)
    scope={'re':re,'unicodedata':unicodedata};exec(source[start:end],scope);normalize=scope['normalize']
    groups={};rows=[]
    for row in read(a.control/'validation-scoring-only.json'):
        ref=normalize(row['text']);result={'id':row['id'],'meeting':row['meeting'],'referenceCharacters':len(ref)}
        for phase in ['baseline','candidate']:
            packet=read(a.run/(phase+'-validation')/(row['id']+'.json'))
            assert packet['audioSha256']==row['audioSha256'] and not packet['referenceUsed'] and not packet['wordsPostEdited']
            ops=Levenshtein.editops(ref,normalize(packet['text']));result[phase]={'edits':len(ops),'cer':len(ops)/len(ref),
                'counts':{k:sum(o.tag==k for o in ops) for k in ['replace','delete','insert']},'rawText':packet['text']}
            bucket=groups.setdefault(row['meeting'],{'referenceCharacters':0,'baselineEdits':0,'candidateEdits':0})
            bucket[phase+'Edits']+=len(ops)
        groups[row['meeting']]['referenceCharacters']+=len(ref);rows.append(result)
    total={'referenceCharacters':sum(v['referenceCharacters'] for v in groups.values())}
    for phase in ['baseline','candidate']:
        total[phase+'Edits']=sum(v[phase+'Edits'] for v in groups.values());total[phase+'Cer']=total[phase+'Edits']/total['referenceCharacters']
        for value in groups.values():value[phase+'Cer']=value[phase+'Edits']/value['referenceCharacters']
    english_id='existing-English-first30';mixed_id='existing-natural-mixed-00009'
    english=[read(a.run/(phase+'-controls')/(english_id+'.json')) for phase in ['baseline','candidate']]
    assert read(a.run/'after-training-disabled-English-control.json')['generatedIds']==english[0]['generatedIds']
    english_preserved=normalize(english[0]['text'])==normalize(english[1]['text'])
    mixed=[read(a.run/(phase+'-controls')/(mixed_id+'.json')) for phase in ['baseline','candidate']]
    ref=normalize(read(a.control/'mixed-control-scoring-only.json')['reference'])
    mixed_edits=[Levenshtein.distance(ref,normalize(packet['text'])) for packet in mixed]
    keep=total['candidateEdits']<total['baselineEdits'] and all(v['candidateEdits']<=v['baselineEdits'] for v in groups.values()) and english_preserved and mixed_edits[1]<=mixed_edits[0]
    report={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
        'state':'KEEP_FOR_COMPLETE_MEETING_EVALUATION_ONLY' if keep else 'REJECT_FIXED_SMALL_ADAPTER_TRIAL',
        'protocolSha256':sha(a.control/'protocol.json'),'adapterSha256':state['adapterSha256'],
        'total':total,'byMeeting':groups,'rows':rows,'english30NormalizedOutputPreserved':english_preserved,
        'englishRawOutputs':[v['text'] for v in english],'mixed4SecondReferenceCharacters':len(ref),'mixedEdits':mixed_edits,
        'frozenBackboneBytesUnchanged':True,'disabledAdapterExactEnglishIdsPreserved':True,
        'parameterSweeps':0,'qualityQualified':False,'saleQualified':False,'adoptedInProduct':False,
        'scope':'32 held-out complete annotated utterances, not complete meetings or independent room/speaker/final-holdout qualification. A kept adapter still needs unchanged full Chinese/English and person gates.'}
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['state','total','byMeeting','english30NormalizedOutputPreserved','mixedEdits','qualityQualified']},ensure_ascii=False))

if __name__=='__main__':main()
