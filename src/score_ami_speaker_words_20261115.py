"""Full reference-word speaker scoring, with unknown words forced unmatched."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,hashlib,itertools,json,re,unicodedata,wave
from score_ami_bilingual_20261115 import references,words,POLICY

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--audio',type=Path,required=True);p.add_argument('--manual',type=Path,required=True)
    p.add_argument('--meeting',required=True);p.add_argument('--document',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists()
    from rapidfuzz.distance import Levenshtein
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    with wave.open(str(a.audio),'rb') as f:duration=f.getnframes()/f.getframerate()
    rows,bindings,condition=references(a.manual,a.meeting,duration)
    doc=json.loads(a.document.read_text(encoding='utf-8'));assert doc['isFinal']
    assert ''.join(u['text'] for u in doc['utterances'])==doc['text']
    reference=defaultdict(list)
    for row in rows:reference[row['speaker']].extend(row['tokens'])
    normalized=[];owners=[]
    for utterance in doc['utterances']:
        for ch in utterance['text']:
            text=unicodedata.normalize('NFKC',ch).lower().replace('\u2019',"'")
            normalized.append(text);owners.extend([utterance.get('speaker')]*len(text))
    text=''.join(normalized)
    assert text==unicodedata.normalize('NFKC',doc['text']).lower().replace('\u2019',"'"),'Cross-character normalization needs an explicit offset map'
    hypothesis=defaultdict(list);unknown=[]
    for match in re.finditer(r"[a-z0-9]+(?:'[a-z0-9]+)*",text):
        people=set(owners[match.start():match.end()])
        if len(people)==1 and None not in people:hypothesis[next(iter(people))].append(match.group())
        else:unknown.append(match.group())
    assert sum(map(len,hypothesis.values()))+len(unknown)==len(words(doc['text']))
    ref_ids=sorted(reference);hyp_ids=sorted(hypothesis);n=max(len(ref_ids),len(hyp_ids));cost=np.zeros((n,n),dtype=np.int64)
    for i in range(n):
        for j in range(n):
            left=reference[ref_ids[i]] if i<len(ref_ids) else []
            right=hypothesis[hyp_ids[j]] if j<len(hyp_ids) else []
            cost[i,j]=Levenshtein.distance(left,right)
    r,c=linear_sum_assignment(cost);best=int(cost[r,c].sum())
    if n<=8:assert best==min(sum(int(cost[i,j]) for i,j in enumerate(perm)) for perm in itertools.permutations(range(n)))
    people=[];extra=[];counts=Counter()
    for i,j in zip(r,c):
        left=reference[ref_ids[i]] if i<len(ref_ids) else []
        right=hypothesis[hyp_ids[j]] if j<len(hyp_ids) else []
        errors=Counter(op.tag for op in Levenshtein.editops(left,right));counts.update(errors)
        row={'referenceSpeaker':ref_ids[i] if i<len(ref_ids) else None,'predictedAnonymousSpeaker':hyp_ids[j] if j<len(hyp_ids) else None,
             'referenceWords':len(left),'hypothesisWords':len(right),'substitutions':errors['replace'],
             'deletions':errors['delete'],'insertions':errors['insert'],'wer':sum(errors.values())/len(left) if left else None}
        (people if left else extra).append(row)
    assert sum(counts.values())==best
    total=sum(map(len,reference.values()));result={
        'state':'COMPLETE_FULL_ENGLISH_WORD_AND_SPEAKER_DIAGNOSTIC_NOT_QUALIFIED',
        'policy':POLICY,'audioSha256':sha(a.audio),'documentSha256':sha(a.document),'referenceFiles':bindings,'condition':condition,
        'referenceWords':total,'hypothesisWords':sum(map(len,hypothesis.values()))+len(unknown),
        'unknownWordsForcedUnmatched':len(unknown),'cpWerErrors':best+len(unknown),'cpWer':(best+len(unknown))/total,
        'perReferenceSpeaker':people,'extraPredictedGroups':extra,'reviewRequired':doc.get('reviewRequired',False),
        'unknownHandling':'Unknown or cross-person lexical words remain unmatched insertions; missing reference content is also counted by reference sequences. No unknown group is assigned to a reference person.',
        'mappingForScoringOnly':True,'referenceNeverPassedToInference':True,'qualityQualified':False}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['policy','referenceFiles','perReferenceSpeaker','extraPredictedGroups']},ensure_ascii=False))

if __name__=='__main__':main()
