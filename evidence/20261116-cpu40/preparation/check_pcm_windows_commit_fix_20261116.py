"""Real Windows sharing collisions, bounded failure, durable replay and exact EOS."""
from pathlib import Path
from datetime import datetime
import hashlib,json,sys,threading,time,uuid
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession,SessionConflict,exclusive_file
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-pcm-reader-collision-fix-r1');assert not E.exists();E.mkdir()
rows=[]
def asynchronous_append(session,data):
 result={};tick=time.monotonic()
 def append():
  try:result['ack']=session.append(0,data)
  except BaseException as error:result.update(error=repr(error),type=type(error).__name__,winerror=getattr(error,'winerror',None))
  finally:result['seconds']=time.monotonic()-tick
 thread=threading.Thread(target=append);thread.start();return thread,result
session=PcmSession.create(E/'reader',recording_id=str(uuid.uuid4()));data=b'\1\0'*160
with session.meta.open('rb') as reader:
 thread,result=asynchronous_append(session,data);time.sleep(.2);assert thread.is_alive() and session.state()['confirmedFrames']==0
thread.join(timeout=2);assert not thread.is_alive() and 'error' not in result and result['ack']['confirmedFrames']==160
assert session.audio.read_bytes()==data;rows.append({'case':'temporary_open_reader_commit_waits_then_succeeds',**result})
locked=PcmSession.create(E/'owner',recording_id=str(uuid.uuid4()))
with exclusive_file(locked.root/'intake.lock'):
 thread,result=asynchronous_append(locked,data);time.sleep(.2);assert thread.is_alive()
thread.join(timeout=2);assert not thread.is_alive() and 'error' not in result;rows.append({'case':'temporary_intake_owner_serializes',**result})
blocked=PcmSession.create(E/'permanent-reader',recording_id=str(uuid.uuid4()))
with blocked.meta.open('rb') as reader:
 thread,result=asynchronous_append(blocked,data);thread.join(timeout=4)
 assert not thread.is_alive() and result['type']=='PermissionError' and 2.9<=result['seconds']<4
assert blocked.state()['confirmedFrames']==0 and blocked.audio.read_bytes()==data
ack=blocked.append(0,data);assert ack['confirmedFrames']==160 and len(blocked.audio.read_bytes())==len(data)
rows.append({'case':'persistent_reader_fails_bounded_then_exact_replay_recovers_without_duplication',**result,'replayAck':ack})
for name,first,packet in [('gap',161,b'\0\0'),('changed_replay',0,b'\2\0'*160)]:
 tick=time.monotonic()
 try:session.append(first,packet)
 except SessionConflict as error:assert time.monotonic()-tick<.2;rows.append({'case':name,'error':str(error),'seconds':time.monotonic()-tick})
 else:raise AssertionError('Conflict must not be hidden by retries')
session.seal(160);assert session.state()['sealed'] and session.audio.read_bytes()==data
result={'state':'PASS_ACTUAL_WINDOWS_ATOMIC_COMMIT_OWNERSHIP_AND_DURABLE_REPLAY','at':datetime.now().astimezone().isoformat(),
 'sourceSha256':hashlib.sha256((S/'companion_local_pcm_session_20261114.py').read_bytes()).hexdigest(),'cases':rows,'newNeuralCalls':0,'recognitionQualityClaim':False}
(E/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
