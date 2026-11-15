"""Strict full-recording AMI word scoring, separate from model input."""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, re, unicodedata, wave
import xml.etree.ElementTree as ET

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def words(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*",unicodedata.normalize('NFKC',text).lower().replace('\u2019',"'"))

POLICY={
 'schema':'companion.english-full-word-scoring.v1',
 'reference':'All <w> lexical content in all four official AMI word files, including fillers and partial words',
 'normalization':'Unicode NFKC, lower case, curly apostrophe to ASCII, alphanumeric words with internal apostrophes; punctuation separates words',
 'wordOrder':'All words sorted by original start time, original end time, speaker and XML order; overlap ordering is a limitation of single-stream WER',
 'excluded':'Non-word XML nodes only; no manual synonym, abbreviation, numeral, filler or disfluency rewrites',
 'wer':'(substitutions+deletions+insertions)/all reference words',
 'englishQualityTarget':{'strictWholeWerLessThan':.05,'status':'explicit conservative extension for English ordinary-meeting development; not an existing Chinese CER definition'},
 'qualityQualificationRequires':'Complete final document, per-person words and activity, ordinary/complex conditions and original independent meeting coverage; raw WER alone cannot qualify product'}

def references(directory,meeting,duration):
    all_words=[];bindings=[];events=[]
    for file in sorted(Path(directory).glob(meeting+'.?.words.xml')):
        speaker=file.name.split('.')[1];bindings.append({'path':str(file),'sha256':sha(file)})
        for i,w in enumerate(ET.parse(file).getroot().iter('w')):
            text=''.join(w.itertext());tokens=words(text)
            if not tokens:continue
            start,end=float(w.attrib['starttime']),float(w.attrib['endtime'])
            assert 0<=start<=end<=duration+.1,(file,start,end,duration)
            all_words.append(dict(start=start,end=end,speaker=speaker,index=i,text=text,tokens=tokens))
            if end>start:events.extend([(start,1,speaker),(end,-1,speaker)])
    assert len(bindings)==4 and all_words
    active=Counter();last=0.;speech=overlap=reference_speaker_time=0.
    for t,change,spk in sorted(events):
        n=sum(v>0 for v in active.values());dt=t-last
        speech+=dt*(n>0);overlap+=dt*(n>1);reference_speaker_time+=dt*n
        active[spk]+=change;assert active[spk]>=0;last=t
    return sorted(all_words,key=lambda x:(x['start'],x['end'],x['speaker'],x['index'])),bindings,{
        'wordActivityUnionSeconds':speech,'wordActivityOverlapSeconds':overlap,
        'overlapFractionOfSpeechUnion':overlap/speech,'referenceSpeakerSeconds':reference_speaker_time,
        'condition':'complex_overlap_development' if overlap/speech>=.05 else 'ordinary_development',
        'conditionUsesReferencesOnlyForScoringNotInference':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--audio',type=Path,required=True);p.add_argument('--manual',type=Path,required=True)
    p.add_argument('--meeting',default='EN2002a');p.add_argument('--document',type=Path)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
    with wave.open(str(a.audio),'rb') as f:duration=f.getnframes()/f.getframerate()
    rows,bindings,condition=references(a.manual,a.meeting,duration)
    result={'policy':POLICY,'audioSha256':sha(a.audio),'audioSeconds':duration,'referenceFiles':bindings,
        'referenceWords':sum(len(x['tokens']) for x in rows),'bySpeaker':dict(Counter(x['speaker'] for x in rows)),
        'condition':condition,'qualityQualified':False,'referencePassedToInference':False}
    if a.document:
        from rapidfuzz.distance import Levenshtein
        doc=json.loads(a.document.read_text(encoding='utf-8'));assert doc['isFinal'] and not doc.get('reviewRequired',False)
        ref=[token for x in rows for token in x['tokens']];hyp=words(doc['text'])
        ops=Levenshtein.editops(ref,hyp);counts=Counter(o[0] for o in ops)
        distance=Levenshtein.distance(ref,hyp);assert distance==sum(counts.values())
        result.update(documentSha256=sha(a.document),hypothesisWords=len(hyp),substitutions=counts['replace'],
            deletions=counts['delete'],insertions=counts['insert'],errors=distance,wer=distance/len(ref),
            rawWordTargetPassed=distance/len(ref)<.05)
        result['rawHypothesis']=doc['text']
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['rawHypothesis','policy','referenceFiles']},ensure_ascii=False))

if __name__=='__main__':main()
