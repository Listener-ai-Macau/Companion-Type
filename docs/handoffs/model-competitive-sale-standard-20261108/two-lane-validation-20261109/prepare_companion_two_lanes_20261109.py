from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,math,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109'
A=C.parent/'word-identity-audit-20261109'
C.mkdir(exist_ok=False)
cache=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/two-lane-validation-20261109');cache.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
profiles=read(A/'automatic-profiles-inputs.json');journal=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results/L_R003S01C02/speaker-journal.json'
j=read(journal);assert sha(profiles['audioSource'])==profiles['audioSha256']==j['audioSha256']
segments=j['segments'];edges=sorted(set(v for s in segments for v in (s['start'],s['end'])))
spans=[]
for a,b in zip(edges,edges[1:]):
 people={str(s['speaker']) for s in segments if s['start']<(a+b)/2<s['end']}
 if len(people)==1:
  person=next(iter(people))
  if spans and spans[-1][2]==person and abs(spans[-1][1]-a)<1e-5:spans[-1]=(spans[-1][0],b,person)
  else:spans.append((a,b,person))
forbidden=[(1559.9,1861.95)]+[(p['start'],p['end']) for p in profiles['profiles']]
selected=[];counts={p:0 for p in profiles['predictedPeople']};last={p:-1000 for p in counts}
with wave.open(profiles['audioSource'],'rb') as original:
 assert (original.getnchannels(),original.getframerate(),original.getsampwidth())==(1,16000,2)
 for a,b,person in spans:
  start=math.ceil((a+.2)*16000);end=min(math.floor((b-.2)*16000),start+4*16000)
  if end-start<16000 or counts[person]>=4 or start/16000-last[person]<15:continue
  if any(start/16000<y and end/16000>x for x,y in forbidden):continue
  qid='q%03d'%len(selected);audio=cache/(qid+'.wav');original.setpos(start);pcm=original.readframes(end-start)
  with wave.open(str(audio),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm)
  with wave.open(str(audio),'rb') as f:assert f.readframes(f.getnframes())==pcm
  selected.append({'id':qid,'audio':str(audio),'audioSha256':sha(audio),'start':start/16000,'end':end/16000,'expectedNativePersonForScoringOnly':person});last[person]=start/16000;counts[person]+=1
bank=R/'docs/handoffs/20261108-tse-source-supervision/reference-bank-r1'
cal=read(bank/'reference-plan.json')['references'][0]
worker=M/'src/automatic_speaker_cpu_worker_20261109.py'
inputs={'modelReady':str(R/'docs/handoffs/20261108-joint-neural-spatial/model-ready.json'),'torchaudioSource':str(M/'upstream-tse/torchaudio-python-34c52a67e8941bbd8e6adaca0eb0b9eabec11d78/src'),'profiles':[{k:p[k] for k in ('id','nativePerson','audio','audioSha256')} for p in profiles['profiles']],'queries':[{k:p[k] for k in ('id','audio','audioSha256')} for p in selected],'calibration':[{'id':'cpu-author-frontend-calibration','audio':cal['audio'],'audioSha256':cal['audioSha256']}]}
write(C/'audio-only.json',inputs)
write(C/'selection-scoring-only.json',{'sourceAudio':profiles['audioSource'],'sourceAudioSha256':profiles['audioSha256'],'journal':str(journal),'journalSha256':sha(journal),'queries':selected,'counts':counts,'calibrationVectorSource':str(bank/'embedding-vectors.json'),'profileReviewForScoringOnly':str(A/'automatic-profiles-review.json')})
write(C/'protocol.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'workerSha256':sha(worker),'audioOnlySha256':sha(C/'audio-only.json'),'modelReadySha256':sha(inputs['modelReady']),'policy':'Frozen17automatic profiles, originalPS4 ECAPA raw-vector mean. Earliest4 nonoverlapping queries per predictedperson, 1..4s,15s start spacing, solo predictedjournal shrunk200ms. Exclude allprofile spans and old302s analysiswindow. Allselected retained. Reference labels/text are scoring-only. No new threshold tuning or weights.','gate':'Development readiness only: report every person and every selected query, profile confusion, same-device calibration, resource/time. Not whole-meeting DER, overlap CER or generalization qualification.','queryCount':len(selected),'queriesPerPerson':counts,'cpuPercentCap':5,'privateCommitCapBytes':2*1024**3,'systemLowMemoryStop':True,'finalHoldoutOpened':False,'saleQualified':False})
print(json.dumps({'control':str(C),'queries':len(selected),'queriesPerPerson':counts,'worker':str(worker)},ensure_ascii=False))
