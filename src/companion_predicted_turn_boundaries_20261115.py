"""Insert predicted speaker changes into the frozen audio-only ASR spans.

Existing boundaries remain. Every original sample, including quiet intervals,
belongs to exactly one span. No words, reference labels or true speaker count
are read. Short spans retain the original input padding rule.
"""
from pathlib import Path
import hashlib,json
from practical_qwen_audio_boundaries_20261107 import quiet_wav_spans

POLICY={'base':'Unchanged author low-energy30s spans',
 'additionalCuts':'Predicted native single-speaker onset when anonymous identity changes from previous single-speaker run',
 'minimumNewIntervalSamples':16000,'cutPosition':'Original predicted onset rounded to source sample, without padding or threshold adjustment',
 'preservation':'Keep every original boundary and every source sample once; original short-tail pad to8000 samples remains explicit',
 'source':'Only frozen predicted activity, audio and existing rule; no ASR words, references, true people or score-driven cut selection',
 'stopping':'One complete new ordinary development case, then the previous ordinary regression case. No cut-duration or onset-offset sweep.'}

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def source_turn_spans(audio,journal):
    base=quiet_wav_spans(audio)
    events={}
    for i,row in enumerate(journal['segments']):
        events.setdefault(row['start'],[]).append((i,True));events.setdefault(row['end'],[]).append((i,False))
    active=set();previous=None;changes=[]
    for t,updates in sorted(events.items()):
        for i,start in updates:
            if start:active.add(i)
            else:active.remove(i)
        people={journal['segments'][i]['speaker'] for i in active}
        if len(people)==1:
            person=next(iter(people))
            if previous is not None and person!=previous:changes.append(round(t*16000))
            previous=person
    result=[]
    for span in base:
        at=span['startSample'];end=span['endSample']
        points=[]
        for point in changes:
            if point-at>=16000 and end-point>=16000:points.append(point);at=point
        points=[span['startSample']]+points+[end]
        for a,b in zip(points,points[1:]):
            result.append({'index':len(result),'startSample':a,'endSample':b,'paddingSamples':max(0,8000-(b-a))})
    assert result[0]['startSample']==0 and result[-1]['endSample']==base[-1]['endSample']
    assert all(a['endSample']==b['startSample'] for a,b in zip(result,result[1:]))
    assert sum(r['endSample']-r['startSample'] for r in result)==base[-1]['endSample']
    assert {s['endSample'] for s in base}.issubset({s['endSample'] for s in result})
    return result

def checked_turn_spans(audio,case,protocol,control):
    assert protocol['turnBoundarySourceSha256']==sha(__file__) and protocol['turnBoundaryPolicy']==POLICY
    path=Path(control)/'predicted-turn-spans.json';assert sha(path)==protocol['turnPlanSha256']
    plan=json.loads(path.read_text(encoding='utf-8'))[case['meeting']]
    assert plan['audioSha256']==case['audioSha256'] and sha(plan['journal'])==plan['journalSha256']
    journal=json.loads(Path(plan['journal']).read_text(encoding='utf-8'));assert journal['audioSha256']==case['audioSha256']
    spans=source_turn_spans(audio,journal);assert spans==plan['spans']
    return spans
