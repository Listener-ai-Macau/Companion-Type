"""Map alignment units back to unchanged ASR text, including punctuation.

The native forced-aligner word splitter drops punctuation. Display text must
keep every original codepoint; a lexical mismatch means alignment unavailable,
never permission to substitute an aligner's text. This module does no inference
and establishes neither correct word times nor speaker identities.
"""
import unicodedata

def source_text_spans(text,words):
    if not isinstance(text,str) or not isinstance(words,list) or any(not isinstance(w,str) or not w for w in words):
        raise ValueError('Expected original text and nonempty alignment word strings')
    if not words:return [] if text=='' else None
    def separator(char):return char.isspace() or unicodedata.category(char)[0] in ('P','S')
    cursor=0;spans=[]
    for word in words:
        actual_start=None
        for char in word:
            while cursor<len(text) and text[cursor]!=char:
                if not separator(text[cursor]):return None
                cursor+=1
            if cursor==len(text):return None
            if actual_start is None:actual_start=cursor
            cursor+=1
        if spans:spans[-1]['textEndCodepoint']=actual_start
        spans.append({'alignmentUnit':word,'textStartCodepoint':actual_start if spans else 0,'textEndCodepoint':cursor})
    if any(not separator(c) for c in text[cursor:]):return None
    spans[-1]['textEndCodepoint']=len(text)
    for span in spans:
        start,end=span['textStartCodepoint'],span['textEndCodepoint']
        span['text']=text[start:end]
        span['textStartUtf16']=len(text[:start].encode('utf-16-le'))//2
        span['textEndUtf16']=len(text[:end].encode('utf-16-le'))//2
    assert ''.join(s['text'] for s in spans)==text
    assert spans[0]['textStartCodepoint']==0 and spans[-1]['textEndCodepoint']==len(text)
    assert all(a['textEndCodepoint']==b['textStartCodepoint'] for a,b in zip(spans,spans[1:]))
    return spans
