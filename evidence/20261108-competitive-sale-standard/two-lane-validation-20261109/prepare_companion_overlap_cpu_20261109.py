from pathlib import Path
import json,hashlib,math,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=read(C/'selection-scoring-only.json');j=read(plan['journal']);segments=j['segments'];edges=sorted({v for s in segments for v in (s['start'],s['end']) if 1559.9<=v<=1861.95})
selected=[];previous_end=0
cache=Path(read(C/'audio-only.json')['queries'][0]['audio']).parent
with wave.open(plan['sourceAudio'],'rb') as f:
 for a,b in zip(edges,edges[1:]):
  people=sorted({str(s['speaker']) for s in segments if s['start']<(a+b)/2<s['end']})
  if len(people)!=2 or b-a<.7:continue
  start=math.floor(((a+b)/2-4)*16000);end=start+8*16000
  if start/16000<previous_end:continue
  packet={'id':'overlap-%02d'%len(selected),'sourceStartSample':start,'sourceEndSample':end,'predictedOverlapStart':a,'predictedOverlapEnd':b,'targetNativePeople':people}
  audio=cache/(packet['id']+'-mixture.wav');f.setpos(start);pcm=f.readframes(end-start)
  with wave.open(str(audio),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
  packet.update(audio=str(audio),audioSha256=sha(audio));selected.append(packet);previous_end=end/16000
  if len(selected)==2:break
assert len(selected)==2
inputs={'cases':selected,'encoderResult':str(C/'encoder-result.json'),'encoderResultSha256':sha(C/'encoder-result.json'),'encoderProtocol':str(C/'protocol.json'),'encoderProtocolSha256':sha(C/'protocol.json'),'baseAudioOnly':str(C/'audio-only.json'),'baseAudioOnlySha256':sha(C/'audio-only.json'),'outputDirectory':str(cache/'extractions')}
write(C/'overlap-audio-only.json',inputs)
worker=R/'model-research/src/automatic_speaker_extraction_cpu_20261109.py'
write(C/'overlap-protocol.json',{'workerSha256':sha(worker),'audioOnlySha256':sha(C/'overlap-audio-only.json'),'policy':'First2 disjoint8s windows centered on predicted2person overlap>=.7s in prior302s querywindow. All17automatic profiles are outside querywindow. Run originalauthor checkpoint perselected predictedidentity, conditioning on meanraw17CPUembeddings. No groundtruth labels/counts/text, threshold sweep, newtraining or originalaudio alteration. This is a targeted readiness smoke test, not allvoices/fullwindow separation claim.','preserveOriginal':True,'defaultRouteChanged':False,'saleQualified':False})
print(json.dumps(selected,ensure_ascii=False))
