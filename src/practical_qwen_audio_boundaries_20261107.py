"""Bounded-WAV port of the author's low-energy boundary rule.

Source: QwenLM/Qwen3-ASR utils.py at7c6daf77a2421100f5fb066495372c00129d39ff.
The rule is retained with a local30s target, not the author's1200s default
ASR chunk budget. Only a10s search region is held in memory. Every original
sample remains in exactly one output span; padding is explicitly separate.
No VAD trimming, reference, recognized text, or person count is consulted.
"""
import wave
import numpy as np

def quiet_wav_spans(path,*,target_seconds=30.,search_expand_seconds=5.,minimum_window_ms=100.):
    if target_seconds<=search_expand_seconds or search_expand_seconds<0 or minimum_window_ms<=0:raise ValueError('Invalid local boundary budget')
    with wave.open(str(path),'rb') as stream:
        assert stream.getframerate()==16000 and stream.getnchannels()==1 and stream.getsampwidth()==2 and stream.getcomptype()=='NONE'
        rate=stream.getframerate();count=stream.getnframes();assert count>0
        maximum=int(target_seconds*rate);expand=int(search_expand_seconds*rate);window=max(4,int(minimum_window_ms/1000*rate))
        if count<=maximum:
            # Match the upstream early return, which does not pad short inputs.
            return [{'index':0,'startSample':0,'endSample':count,'paddingSamples':0}]
        start=0;rows=[]
        while count-start>maximum:
            cut=start+maximum;left=max(start,cut-expand);right=min(count,cut+expand)
            if right-left<=window:boundary=cut
            else:
                stream.setpos(left);pcm=stream.readframes(right-left)
                samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32);samples/=32768
                absolute=np.abs(samples)
                sums=np.convolve(absolute,np.ones(window,dtype=np.float32),mode='valid')
                wstart=int(np.argmin(sums));inner=int(np.argmin(absolute[wstart:wstart+window]))
                boundary=left+wstart+inner
            boundary=int(min(count,max(boundary,start+1)))
            rows.append({'index':len(rows),'startSample':start,'endSample':boundary,'paddingSamples':max(0,8000-(boundary-start))})
            start=boundary
        rows.append({'index':len(rows),'startSample':start,'endSample':count,'paddingSamples':max(0,8000-(count-start))})
    assert rows[0]['startSample']==0 and rows[-1]['endSample']==count
    assert all(a['endSample']==b['startSample'] for a,b in zip(rows,rows[1:]))
    assert sum(row['endSample']-row['startSample'] for row in rows)==count
    return rows
