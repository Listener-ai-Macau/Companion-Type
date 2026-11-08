"""Freeze one bounded real-meeting comparison before any speech is submitted."""
from pathlib import Path
from datetime import datetime
import hashlib,json,sys,wave,re,math,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from reference_textgrid_20261104 import read_reference_intervals
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cases=json.loads((R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/scoring-only.json').read_text(encoding='utf8'))
case=next(x for x in cases if x['meeting']=='L_R003S01C02')
assert sha(case['audio'])==case['audioSha256'] and sha(case['reference'])==case['referenceSha256']
rows=read_reference_intervals(case['reference'])
lexical=[x for x in rows if re.sub(r'<[^>]*>','',x['text']).strip()]
gaps=[0.0]
for end in sorted({x['end'] for x in lexical}):
 if any(x['start']<end<x['end'] for x in lexical):continue
 following=min([x['start'] for x in lexical if x['start']>=end]+[case['audioSeconds']])
 if following-end>=.05:gaps.append(end+.025)
all_edges=sorted({v for x in lexical for v in [x['start'],x['end']]})
overlap_intervals=[(a,b) for a,b in zip(all_edges,all_edges[1:]) if sum(x['start']<b and x['end']>a for x in lexical)>=2]
candidates=[]
for start in gaps:
 ends=[v for v in gaps if start+300<=v<=start+330]
 if not ends:continue
 end=min(ends);window=[x for x in lexical if x['start']<end and x['end']>start]
 if len({x['speaker'] for x in window})<4:continue
 overlap=sum(max(0,min(end,b)-max(start,a)) for a,b in overlap_intervals)
 candidates.append((overlap/(end-start),-start,start,end))
assert candidates
ratio,_,start,end=max(candidates)
assert ratio>=.05
if (C/'prefix-protocol.json').exists():
 old=json.loads((C/'prefix-protocol.json').read_text(encoding='utf8'))
 assert not (C/'prefix-run.json').exists()
 for name in ['prefix-protocol','prefix-scoring-only']:shutil.copyfile(C/(name+'.json'),C/(name+'-initial-not-inferred.json'))
 old_audio=Path(old['audio']);shutil.copyfile(old_audio,old_audio.with_name('initial-ordinary-not-inferred.wav'))
cache=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108');cache.mkdir(parents=True,exist_ok=True)
audio=cache/'L_R003S01C02-prefix.wav'
assert not (C/'prefix-final-response.json').exists()
with wave.open(case['audio'],'rb') as src:
 assert (src.getnchannels(),src.getframerate(),src.getsampwidth())==(1,16000,2)
 begin=math.floor(start*16000);finish=math.ceil(end*16000);src.setpos(begin);pcm=src.readframes(finish-begin)
 with wave.open(str(audio),'wb') as dst:
  dst.setparams(src.getparams());dst.writeframes(pcm)
actual=len(pcm)/32000
source_start=begin/16000;source_end=finish/16000
original_selected=[x for x in lexical if x['start']<source_end and x['end']>source_start]
assert all(x['start']>=source_start and x['end']<=source_end for x in original_selected)
selected=[dict(x,start=x['start']-source_start,end=x['end']-source_start) for x in original_selected]
edges=sorted({0,actual,*[v for x in selected for v in [x['start'],x['end']]]})
overlap=sum(b-a for a,b in zip(edges,edges[1:]) if sum(x['start']<b and x['end']>a for x in selected)>=2)
protocol={'frozenAt':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FROZEN_PUBLIC_REAL_MEETING_PREFIX_DIAGNOSTIC','sourceMeeting':case['meeting'],'sourceAudio':case['audio'],'sourceAudioSha256':case['audioSha256'],'audio':str(audio),'audioSha256':sha(audio),'audioSeconds':actual,'sourceStartSeconds':source_start,'sourceEndSeconds':source_end,'selection':'Prior to any speech inference: enumerate >=50ms common gaps, at each start choose first gap300..330s later, require>=4 annotated voices, choose largest true-overlap fraction, earliest start breaks ties. This deliberately difficult development window is not an unbiased or full-meeting qualification. No text/people count supplied to provider.','preparationRevision':'Initial first305.2s window had only0.91% annotated overlap, insufficient for the declared complex purpose. It was never inferred. Original manifest/scoring retained; replace before speech submission with fixed hardest-overlap window, no selection based on ASR. PY lacked existing PraatIO dependency; same parser ran in existing clean scoring runtime, no parser change.','referencePassedToProvider':False,'hotwords':[],'denoising':False,'physicalCardCapture':False,'modelOrThresholdSelectionAllowedFromResult':True,'finalHoldoutOpened':False,'saleQualified':False,'requestPolicy':'Mirror existing Windows SAUC adapter,100ms real-time-paced packets,anonymous speaker info and original ITN enabled; no service upgrade, no endpoint/resource sweep, no automatic retry.','providerReference':'Existing configured Volcengine service; not a measurement of latest vendor model or competitor product.','originalWholeMeetingAcceptanceUnchanged':True}
scoring={'reference':case['reference'],'referenceSha256':case['referenceSha256'],'segments':selected,'referencePeople':sorted({x['speaker'] for x in selected}),'overlapSeconds':overlap,'overlapFraction':overlap/actual,'notPassedToInference':True,'limits':'Annotation utterance bounds are not word timestamps. cpCER can be scored but pure-overlap wordCER/tcpCER and accurate speech-activity DER remain unmeasured. No invented reference words at clipped boundaries.'}
for name,data in [('prefix-protocol.json',protocol),('prefix-scoring-only.json',scoring)]:
 (C/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'audioSeconds':actual,'referencePeople':len(scoring['referencePeople']),'overlapSeconds':overlap,'state':protocol['state']},ensure_ascii=False))
