from pathlib import Path
import json,sys,uuid,traceback,hashlib
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-pcm-reader-collision-r1');assert not E.exists();E.mkdir()
session=PcmSession.create(E/'session',recording_id=str(uuid.uuid4()))
source=S/'companion_local_pcm_session_20261114.py';(E/'session-source-before-fix.py').write_bytes(source.read_bytes())
result={'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'newNeuralCalls':0}
with session.meta.open('rb') as reader:
 try:session.append(0,b'\0\0'*2);result['unexpectedPass']=True
 except BaseException as error:result.update(errorType=type(error).__name__,error=repr(error),errno=getattr(error,'errno',None),winerror=getattr(error,'winerror',None),traceback=traceback.format_exc())
result.update(durablePcmBytes=session.audio.stat().st_size,confirmedFrames=session.state()['confirmedFrames'])
(E/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
