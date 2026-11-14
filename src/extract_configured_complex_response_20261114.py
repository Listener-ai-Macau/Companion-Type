"""Read saved provider responses using Companion's existing text/token policy.
No cloud/model call or reference text. Opaque IDs, including0, stay anonymous.
"""
from pathlib import Path
import argparse,hashlib,json,math

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
DEFAULT=ROOT/'docs/handoffs/20261109-paired-real-meeting/sleep-continuation20261114/configured-full-complex'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def sha(path):
    with path.open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()

def result_object(value):
    result=value.get('result',value if isinstance(value.get('text'),str) else None)
    if isinstance(result,list):
        assert len(result)==1,'Do not discard another result/channel'
        result=result[0]
    assert isinstance(result,dict),'Missing provider result object'
    return result

def utterance_text(row):
    text=row.get('text')
    if isinstance(text,str) and text.strip():return text
    words=row.get('words')
    if not isinstance(words,list) or not words:return None
    if not all(isinstance(word.get('text'),str) for word in words):return None
    text=''.join(word['text'] for word in words)
    return text if text.strip() else None

def extract_text(value):
    result=result_object(value);original=result.get('text')
    if not isinstance(original,str):original=None
    rows=result.get('utterances')
    if not isinstance(rows,list):return original
    explicit=[];complete=[];recovered=False
    for row in rows:
        own=row.get('text')
        if isinstance(own,str) and own.strip():explicit.append(own);complete.append(own)
        else:
            text=utterance_text(row)
            if text is not None:complete.append(text);recovered=True
            elif row.get('words'):return original
    signature=lambda text:''.join(c.lower() for c in text if c.isalnum())
    joined=''.join(complete)
    if joined.strip() and (original is None or not original.strip() or recovered and signature(original)==signature(''.join(explicit))):return joined
    return original

def speaker(row):
    keys=['speaker','speaker_id','speakerId','spk_id']
    def first(obj):
        if not isinstance(obj,dict):return None
        for key in keys:
            if key in obj:
                value=obj[key]
                return str(value).strip() if isinstance(value,(str,int,float)) and not isinstance(value,bool) and str(value).strip() else None
    direct=first(row)
    if direct is not None:return direct
    additions=row.get('additions')
    if isinstance(additions,str):
        try:additions=json.loads(additions)
        except ValueError:return None
    return first(additions)

def millis(row,keys):
    for key in keys:
        value=row.get(key)
        if isinstance(value,bool):continue
        try:
            if value is not None and math.isfinite(float(value)):return int(value)
        except (ValueError,TypeError):pass
    return None

def extract(value,seconds):
    result=result_object(value);text=extract_text(value)
    assert isinstance(text,str) and text.strip(),'No complete provider text'
    rows=[];unlocated=[];fallback=0
    for index,item in enumerate(result.get('utterances') or []):
        content=utterance_text(item)
        if content is None:continue
        if not (isinstance(item.get('text'),str) and item['text'].strip()):fallback+=1
        words=item.get('words') or []
        starts=[millis(word,['start_time','startTime','start_ms']) for word in words]
        ends=[millis(word,['end_time','endTime','end_ms']) for word in words]
        start=next((x for x in starts if x is not None),None)
        end=next((x for x in reversed(ends) if x is not None),None)
        if start is None:start=millis(item,['start_time','startTime','start_ms'])
        if end is None:end=millis(item,['end_time','endTime','end_ms'])
        if start is None or end is None or not 0<=start<end<=seconds*1000:
            unlocated.append({'index':index,'text':content,'speaker':speaker(item),'startMs':start,'endMs':end});continue
        rows.append({'text':content.strip(),'startMs':start,'endMs':end,'speaker':speaker(item),
                     'approximateTiming':True})
    return {'isFinal':True,'text':text,'utterances':rows,'unlocatedText':unlocated,
            'wordOnlyUtterancesRecovered':fallback,'providerSpeakerIdsAreAnonymous':True,
            'wordTimingGroundTruthVerified':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,default=DEFAULT);parser.add_argument('--self-check',action='store_true');args=parser.parse_args()
    if args.self_check:
        old=ROOT/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109/asr-paired-r1'
        value=read(old/'overlap-01-native-2-response.json')
        assert extract_text(value)=='这就是本校区呗'
        document=extract(value,8)
        assert document['utterances'][0]['speaker']=='0' and document['utterances'][0]['startMs']==4532 and document['utterances'][0]['endMs']==5632
        assert document['wordOnlyUtterancesRecovered']==1
        assert extract_text({'result':{'text':'原有正文','utterances':[{'words':[{'text':'不得部分补写'},{}]}]}})=='原有正文'
        print('PASS: real word-only response, opaque0identity, actual word bounds and malformed-token refusal match the production policy');return
    control=args.control;state=read(control/'state.json')
    assert state['state']=='COMPLETE_CONFIGURED_WHOLE_COMPLEX_RESPONSE_UNSCORED' and state['authoritativePostEosFinal']
    assert state['sentFrames']==round(state['audioSeconds']*16000) and sha(Path(state['audio']))==state['audioSha256']
    response=control/'authoritative-final-response.json';document=extract(read(response),state['audioSeconds'])
    target=control/'model-output.json';assert not target.exists(),'Preserve original extraction'
    target.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (control/'transcript.txt').write_text(document['text'],encoding='utf-8')
    rttm=[]
    for row in document['utterances']:
        if row['speaker'] is not None:rttm.append(f"SPEAKER {state['meeting']} 1 {row['startMs']/1000:.3f} {(row['endMs']-row['startMs'])/1000:.3f} <NA> <NA> {row['speaker']} <NA> <NA>")
    (control/'hypothesis.rttm').write_text('\n'.join(rttm)+'\n',encoding='utf-8')
    receipt={'state':'COMPLETE_PROVIDER_TEXT_AND_ANONYMOUS_TIMELINE_EXTRACTED','responseSha256':sha(response),
             'outputSha256':sha(target),'wordOnlyUtterancesRecovered':document['wordOnlyUtterancesRecovered'],
             'unlocatedLexicalRows':len(document['unlocatedText']),'utterances':len(document['utterances']),
             'anonymousSpeakers':sorted({row['speaker'] for row in document['utterances'] if row['speaker'] is not None}),
             'noWordTextManuallyCorrected':True,'qualityQualified':False}
    (control/'extraction.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
