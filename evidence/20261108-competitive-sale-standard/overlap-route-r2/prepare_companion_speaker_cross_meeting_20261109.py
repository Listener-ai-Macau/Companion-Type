"""Freeze cross-meeting automatic enrollment before reading any answer labels."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import collections,hashlib,json,math,wave,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';OLD=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109';C=OLD/'automatic-cross-meeting-r2';C.mkdir(exist_ok=False)
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);pressure=SystemRamPressure()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
inputs=read(R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5/audio-only.json');old=read(OLD/'audio-only.json');cases=[]
for source in inputs:
 meeting=source['meeting'];folder=C/meeting;folder.mkdir();cache=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/cross-meeting-r2')/meeting;cache.mkdir(parents=True,exist_ok=True)
 assert sha(source['audio'])==source['audioSha256']
 journal=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results'/meeting/'speaker-journal.json';j=read(journal);assert j['audioSha256']==source['audioSha256']
 segments=j['segments'];edges=sorted({v for s in segments for v in (s['start'],s['end'])});spans=[]
 for a,b in zip(edges,edges[1:]):
  people={str(s['speaker']) for s in segments if s['start']<(a+b)/2<s['end']}
  if len(people)==1:
   person=next(iter(people))
   if spans and spans[-1][2]==person and abs(spans[-1][1]-a)<1e-5:spans[-1]=(spans[-1][0],b,person)
   else:spans.append((a,b,person))
 people=sorted({str(s['speaker']) for s in segments});profiles=[];queries=[];counts=collections.Counter();last=collections.defaultdict(lambda:-1000)
 old_queries=[]
 with wave.open(source['audio'],'rb') as audio:
  assert (audio.getnchannels(),audio.getframerate(),audio.getsampwidth())==(1,16000,2)
  def crop(kind,idx,start,end,person):
   audio.setpos(start);pcm=audio.readframes(end-start);path=cache/(kind+'-%04d.wav'%idx)
   with wave.open(str(path),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
   return {'id':kind+'-%04d'%idx,'nativePerson':person,'audio':str(path),'audioSha256':sha(path),'start':start/16000,'end':end/16000}
  if meeting=='L_R003S01C02':
   original=read(OLD.parent/'word-identity-audit-20261109/automatic-profiles-inputs.json');profiles=original['profiles'];old_queries=read(OLD/'selection-scoring-only.json')['queries']
  else:
   for a,b,person in spans:
    start=math.ceil((a+.2)*16000);end=min(math.floor((b-.2)*16000),start+8*16000)
    if counts[person]>=3 or end-start<32000 or start/16000-last[person]<30:continue
    profiles.append(crop('profile',len(profiles),start,end,person));counts[person]+=1;last[person]=start/16000
  excluded=[(p['start']-15,p['end']+15) for p in profiles]
  if meeting=='L_R003S01C02':excluded += [(1559.9,1861.95)]+[(p['start'],p['end']) for p in old_queries]
  previous=collections.defaultdict(lambda:-1000)
  for a,b,person in spans:
   if pressure.low():raise RuntimeError('Windows actualLOWRAM; stopcrop')
   start=math.ceil((a+.2)*16000);end=min(math.floor((b-.2)*16000),start+4*16000)
   if end-start<16000 or start/16000-previous[person]<15:continue
   if any(start/16000<y and end/16000>x for x,y in excluded):continue
   queries.append(crop('query',len(queries),start,end,person));previous[person]=start/16000
 inference={'modelReady':old['modelReady'],'torchaudioSource':old['torchaudioSource'],'profiles':[{k:p[k] for k in ('id','nativePerson','audio','audioSha256')} for p in profiles],'queries':[{k:p[k] for k in ('id','audio','audioSha256')} for p in queries],'calibration':[]}
 write(folder/'audio-only.json',inference)
 write(folder/'selection-scoring-only.json',{'meeting':meeting,'source':source,'journal':str(journal),'journalSha256':sha(journal),'profiles':profiles,'queries':queries,'answersReadDuringSelection':False,'previousL22QueryAudioExcluded':True})
 worker=M/'src/automatic_speaker_cpu_worker_20261109.py'
 write(folder/'protocol.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'workerSha256':sha(worker),'audioOnlySha256':sha(folder/'audio-only.json'),'modelReadySha256':sha(old['modelReady']),'policy':'Same frozen originalPS4 model/CPUencoder/rawmean prototype. S enrollment:earliest3 solo predictedclips perperson,2..8s,200msedgeguard,30sstartspacing. Existing L17reference clips retained unchanged. Query:earliest1..4s perpredictedsolo span,200msedgeguard,15sstartspacing; >15s awayfrom allprofiles. L excludes old302s analysis andall22priorqueries. No answer/reference identities/count/text used. No threshold/tuning/training. Allselected kept.','qualification':'Exposed development meetings, not wholeDER or finalheldout. Report everyquery and provenance, same frozen recipe across rooms.','cpuPercentCap':5,'privateCommitCapBytes':2147483648,'saleQualified':False})
 cases.append({'meeting':meeting,'control':str(folder),'profiles':len(profiles),'profileCounts':dict(collections.Counter(p['nativePerson'] for p in profiles)),'queries':len(queries),'queryCounts':dict(collections.Counter(p['nativePerson'] for p in queries))})
write(C/'predeclared-selection.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'cases':cases,'referenceLabelsOrTextReadDuringPreparation':False,'decisionRule':'Report originaljournal versus independentfrozenencoder. Additionally evaluate an agreement-only annotation as an uncertainty policy, without fitting a scorethreshold: disagreement is unconfirmed, never drop/transcribe-away audio/text. Report coverage and wrong accepted identities together. Do not call agreement verified identity or claim modelaccuracygain from abstention.','newHyperparameterSearch':False,'finalHoldoutOpened':False,'saleQualified':False})
print(json.dumps(cases,ensure_ascii=False),flush=True)
