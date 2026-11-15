"""Idempotent PCM publication across a crash between WAV and receipt commits."""
from pathlib import Path
import hashlib,os,uuid,wave
def publish_pcm16_wave(path,pcm_bytes,*,sample_rate=16000,channels=1):
    path=Path(path);assert isinstance(pcm_bytes,bytes) and len(pcm_bytes)%(channels*2)==0
    def verify():
        with wave.open(str(path),'rb') as f:
            assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes(),f.getcomptype())==(channels,2,sample_rate,len(pcm_bytes)//(channels*2),'NONE'),'Existing orphan format differs; retain and stop'
            assert f.readframes(f.getnframes())==pcm_bytes,'Existing orphan PCM differs; retain and stop'
    recovered=path.exists()
    if recovered:verify()
    else:
        part=path.parent/('.pcm-'+uuid.uuid4().hex+'.part')
        try:
            with wave.open(str(part),'wb') as f:f.setnchannels(channels);f.setsampwidth(2);f.setframerate(sample_rate);f.writeframes(pcm_bytes)
            with part.open('r+b') as f:os.fsync(f.fileno())
            # Atomic no-replace rename on Windows; do not overwrite an existing
            # audio file from another attempt or a conflicting producer.
            try:os.rename(part,path)
            except FileExistsError:verify();recovered=True
        finally:
            if part.exists():part.unlink()
    verify()
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    return {'audioSha256':digest,'existingIdenticalPcmRecovered':recovered,'allSamplesVerified':True,'existingAudioOverwritten':False}
