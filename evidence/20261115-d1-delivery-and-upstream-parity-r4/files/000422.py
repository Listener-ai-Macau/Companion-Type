"""Restore the original declared AMI validation source; no model inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,traceback,urllib.request,wave
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'native8-ami-r1';C.mkdir(exist_ok=False);E=Path('E:/CodexData/Companion/.model-cache/native8-cross-corpus-20261107/AMI/EN2002a');E.mkdir(parents=True,exist_ok=True);read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
urls={'EN2002a.Array1-01.wav':'https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/EN2002a/audio/EN2002a.Array1-01.wav','EN2002a.rttm':'https://raw.githubusercontent.com/BUTSpeechFIT/AMI-diarization-setup/2509d8933721023fab4def2618aabd5c28eb82e9/only_words/rttms/test/EN2002a.rttm'}
state={'state':'RESTORING_ORIGINAL_AMI_SOURCE_NO_INFERENCE','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'selection':'Exactly EN2002a/Array1-01 from the original20261103 cross-corpus v2 preparation script, no source/output-based replacement','referencePolicy':'Original official only_words RTTM, not forced-aligned model-card labels. Do not compare its short-word spans to Chinese utterance spans or published scores with other references.','finalHoldoutOpened':False,'neuralInferencePerformed':False,'files':[]};atomic_json(C/'input-preparation.json',state)
try:
    for name,url in urls.items():
        dest=E/name;assert not dest.exists();partial=dest.with_suffix(dest.suffix+'.part');request=urllib.request.Request(url,headers={'User-Agent':'Companion-real-meeting-validation-20261107'})
        with urllib.request.urlopen(request,timeout=45) as response,partial.open('wb') as target:
            shutil.copyfileobj(response,target,1024*1024);target.flush();os.fsync(target.fileno());length=response.headers.get('Content-Length');assert not length or partial.stat().st_size==int(length);metadata={'url':url,'file':str(dest),'bytes':partial.stat().st_size,'sha256':sha(partial),'lastModified':response.headers.get('Last-Modified'),'etag':response.headers.get('ETag')}
        os.replace(partial,dest);state['files'].append(metadata);atomic_json(C/'input-preparation.json',state)
    audio=E/'EN2002a.Array1-01.wav';reference=E/'EN2002a.rttm'
    with wave.open(str(audio),'rb') as source:assert (source.getframerate(),source.getnchannels(),source.getsampwidth())==(16000,1,2);seconds=source.getnframes()/16000
    case={'meeting':'EN2002a','audio':str(audio),'audioSeconds':seconds,'audioSha256':sha(audio)};atomic_json(C/'audio-only.json',[case]);atomic_json(C/'scoring-only.json',[{**case,'corpus':'AMI','reference':str(reference),'referenceSha256':sha(reference),'referenceKind':'rttm_only_words'}]);protocol=read(B/'native8-f16-full-r1/protocol.json');protocol['probabilityCacheRoot']=str(E/'native-probabilities');atomic_json(C/'protocol.json',protocol)
    state.update(state='RESTORED_ONE_COMPLETE_AMI_VALIDATION_NO_INFERENCE',audioSeconds=seconds,neuralConfigurationUnchangedFromFrozenChineseBatch=True,qualification='Known project validation, original cache/manifest deleted. Fresh source hashes frozen now; not claimed byte-compared to deleted old cache, new final blind data, Chinese ASR or product acceptance.')
except BaseException as error:state.update(state='SOURCE_RESTORATION_FAILED_NO_SUBSTITUTION',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');atomic_json(C/'input-preparation.json',state);print(json.dumps({k:state.get(k) for k in ['state','audioSeconds','error']},ensure_ascii=False),flush=True)
