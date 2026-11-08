"""Acquire two preselected complete public meetings, preserving physical channels.

No test transcript is downloaded here. Full source hash precedes PCM extraction.
Four bounded network streams; resumable fragments, no whole-file RAM buffers.
"""
from pathlib import Path
from datetime import datetime
import concurrent.futures,hashlib,json,os,sys,time,urllib.request,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=R/'docs/handoffs/20261108-dual-mic-independent-meetings'
E=Path('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108')
REV='aada72727856313b19d4a030383c426364931dbf'
SOURCES=[('M_R003S02C01',258267458,'b74f2c00c374b899c7b0154a1b492a9429b0dd270e0f236d83abff0f7a2c7e0f'),('S_R003S01C01',255177109,'e4a8a76315b7dabe63f43e2364486d9dee989ddcf111d73dc3eae47d86838cd0')]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def fetch(meeting,size,digest):
    target=E/(meeting+'.flac');parts=E/'ranges'/meeting;parts.mkdir(parents=True,exist_ok=True)
    if target.exists():assert target.stat().st_size==size and sha(target)==digest;return target
    url=f'https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/{REV}/test/wav/{meeting}.flac'
    width=8*1024**2
    def piece(index):
        start=index*width;end=min(size,start+width)-1;p=parts/(str(index)+'.part');expected=end-start+1
        if p.exists() and p.stat().st_size==expected:return p
        for attempt in range(4):
            offset=p.stat().st_size if p.exists() else 0;assert offset<expected
            # Include the exact range in the URL to avoid intermediaries reusing
            # an unrelated206 response. Its bytes must still match full LFS SHA.
            request=urllib.request.Request(url+f'?download=true&companion_range={start+offset}-{end}',headers={'Range':f'bytes={start+offset}-{end}','Accept-Encoding':'identity','User-Agent':'Companion-public-meeting-validation'})
            try:
                with urllib.request.urlopen(request,timeout=45) as response:
                    assert response.status==206 and response.headers.get('Content-Range')==f'bytes {start+offset}-{end}/{size}'
                    with p.open('ab') as out:
                        remaining=expected-offset
                        while remaining:
                            b=response.read(min(1024**2,remaining));assert b,'Incomplete206 body';out.write(b);remaining-=len(b)
                        out.flush();os.fsync(out.fileno())
                assert p.stat().st_size==expected;return p
            except Exception:
                if attempt==3:raise
                time.sleep(min(2**attempt,4))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pieces=list(pool.map(piece,range((size+width-1)//width)))
    assembled=target.with_suffix('.assembled.part')
    with assembled.open('wb') as out:
        for p in pieces:
            with p.open('rb') as source:
                while b:=source.read(1024**2):out.write(b)
        out.flush();os.fsync(out.fileno())
    assert assembled.stat().st_size==size and sha(assembled)==digest,'Reject corrupt or wrong public source'
    os.replace(assembled,target);return target
def main():
    limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2);E.mkdir(parents=True,exist_ok=True);C.mkdir(parents=True,exist_ok=True)
    receipt={'state':'PREPARING_UNSEEN_ROOM_MEETINGS','startedAt':datetime.now().astimezone().isoformat(),'selectedMeetings':[x[0] for x in SOURCES],'selection':'First unused medium-room session02 and small-room session01 by filename; exclude prior M_R003S01C01 clips and reserved L_R003S03C02. Not selected using quality outcomes.','revision':REV,'referencePayloadRead':False,'sourceDownloads':[],'audioOnly':[]}
    atomic_json(C/'preparation.json',receipt)
    sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools');import soundfile as sf
    for meeting,size,digest in SOURCES:
        tick=time.perf_counter();source=fetch(meeting,size,digest)
        with sf.SoundFile(str(source)) as audio:
            assert audio.channels==8 and audio.samplerate==16000 and audio.subtype=='PCM_16'
            frames=audio.frames;outputs=[]
            for ch in [0,1]:
                path=E/(meeting+f'-mic{ch}.wav');audio.seek(0)
                if not path.exists():
                    temp=path.with_suffix('.pcm.part')
                    with wave.open(str(temp),'wb') as dest:
                        dest.setnchannels(1);dest.setsampwidth(2);dest.setframerate(16000)
                        while len(block:=audio.read(65536,dtype='int16',always_2d=True)):
                            dest.writeframesraw(block[:,ch].astype('<i2',copy=False).tobytes())
                    os.replace(temp,path)
                with wave.open(str(path),'rb') as check:assert (check.getnchannels(),check.getsampwidth(),check.getframerate(),check.getnframes())==(1,2,16000,frames)
                outputs.append({'corpus':'AISHELL-4-official-test','meeting':meeting+f'-mic{ch}','originalMeeting':meeting,'audio':str(path),'audioSha256':sha(path),'audioSeconds':frames/16000,'sourceSha256':digest,'sourceChannel':ch,'sourceFrames':frames,'sourceSampleRate':16000,'sourceChannels':8,'extraction':'Lossless PCM16 channel selection, no mixing, resampling, alignment or normalization.'})
            receipt['audioOnly']+=outputs;receipt['sourceDownloads'].append({'meeting':meeting,'path':str(source),'sha256':digest,'bytes':size,'preparationSeconds':time.perf_counter()-tick});atomic_json(C/'preparation.json',receipt)
            print(json.dumps({'meeting':meeting,'seconds':frames/16000,'state':'COMPLETE_VERIFIED_SOURCE_AND_TWO_CHANNELS'}),flush=True)
    atomic_json(C/'audio-only.json',receipt['audioOnly']);receipt.update(state='COMPLETE_TWO_FULL_PUBLIC_MEETINGS_FOUR_PHYSICAL_CHANNEL_INPUTS',finishedAt=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(C/'preparation.json',receipt)
if __name__=='__main__':main()
