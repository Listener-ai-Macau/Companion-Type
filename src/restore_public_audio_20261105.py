"""Recover exactly two previously exposed meetings, not any heldout payload."""
from pathlib import Path
import json,hashlib,requests,psutil,time,tarfile,shutil,wave,sys
from datetime import datetime
from zoneinfo import ZoneInfo
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');proof=root/'docs/handoffs/20261105-model-resume';out=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031');out.mkdir(parents=True,exist_ok=True)
receipt=proof/'public-audio-restore-r3.json';assert not receipt.exists()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);allowed=psutil.Process().cpu_affinity();psutil.Process().cpu_affinity(allowed[-2:])
s=requests.Session();s.trust_env=False
revision='aada72727856313b19d4a030383c426364931dbf'
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
state={'at':now(),'state':'RESTORING_PREVIOUSLY_EXPOSED_PUBLIC_AUDIO','dataset':'AISHELL/AISHELL-4','mirrorRevision':revision,
    'referencePassedToInference':False,'finalHoldoutPayloadExtracted':False,'modelLoaded':False,'cases':[],
    'license':'Upstream OpenSLR111 CC BY-SA4.0 retained; HF metadata Apache2 is inconsistent and not used to relicense upstream data.'}
def save():
    t=receipt.with_suffix('.tmp');t.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');t.replace(receipt)
def sha(path):
    with path.open('rb') as inp:return hashlib.file_digest(inp,'sha256').hexdigest()
save();begin=time.perf_counter()
try:
    # Existing official archive prefix supplies the exact original reference bytes.
    prefix=Path('E:/CodexData/Companion/.model-cache/aishell4-20261105/test-prefix8MiB.gz')
    expected={'L_R003S01C02':('768574317a1054afe52a098f8b2630185974a57eb42144ecdf249e929807fc1a','a7e060c87f76f6ad51ca1bcd6ae7243942757f25bdcbfc9a628c552d03dcbc4c'),
              'S_R004S03C01':('82ac9f8b25e2c085b2e0434e444727af0577e373ed5e1f587d3f28881862fe2f','ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3')}
    with tarfile.open(prefix,'r|gz') as archive:
        found=set()
        for m in archive:
            if not m.isfile():continue
            name=Path(m.name)
            if name.stem in expected and name.suffix=='.TextGrid':
                dest=out/name.name
                with archive.extractfile(m) as inp:raw=inp.read()
                source=proof/(name.stem+'.upstream-crlf.TextGrid')
                if source.exists():assert source.read_bytes()==raw
                else:source.write_bytes(raw)
                # The pre-cleanup file used LF. Keep upstream raw bytes too;
                # accept this conversion only when it recreates the old SHA.
                restored=raw.replace(b'\r\n',b'\n')
                assert hashlib.sha256(restored).hexdigest()==expected[name.stem][1]
                if dest.exists():assert dest.read_bytes() in [raw,restored]
                dest.write_bytes(restored)
                state.setdefault('referenceLineEndingRecovery',[]).append({'meeting':name.stem,'upstreamRawSha256':hashlib.sha256(raw).hexdigest(),'restoredExactPreviousSha256':sha(dest),'onlyChange':'CRLF to LF'})
                found.add(name.stem)
            if len(found)==2:break
        assert len(found)==2
    tree=s.get(f'https://huggingface.co/api/datasets/AISHELL/AISHELL-4/tree/{revision}/test/wav',timeout=30);tree.raise_for_status();tree=tree.json()
    sys.path.insert(0,'E:/CodexData/Companion/.model-cache/audio-tools')
    import soundfile as sf
    # Same S30s compatibility input before trying the hard full L meeting.
    for meeting in ['S_R004S03C01','L_R003S01C02']:
        item=next(x for x in tree if x['path']==f'test/wav/{meeting}.flac')
        encoded=out/(meeting+'.flac');partial=encoded.with_suffix('.part');assert not encoded.exists() and not partial.exists()
        state.update(activeMeeting=meeting,state='DOWNLOADING_SINGLE_PREVIOUS_PUBLIC_MEETING',expectedBytes=item['size'],downloadedBytes=0);save()
        with s.get(f'https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/{revision}/{item["path"]}',stream=True,timeout=(20,90)) as response:
            response.raise_for_status();count=0;last=time.perf_counter()
            with partial.open('xb') as output:
                for block in response.iter_content(1024*1024):
                    if not block:continue
                    output.write(block);count+=len(block)
                    if time.perf_counter()-last>3:state['downloadedBytes']=count;save();last=time.perf_counter()
        assert count==item['size'];assert sha(partial)==item['lfs']['oid'];partial.replace(encoded)
        mono=out/(('meeting' if meeting.startswith('S_') else meeting)+'-channel1.wav');assert not mono.exists()
        with sf.SoundFile(encoded) as source:
            assert source.channels==8 and source.samplerate==16000
            frames=source.frames;decoded=0
            with sf.SoundFile(mono,'w',samplerate=16000,channels=1,subtype='PCM_16') as output:
                for block in source.blocks(blocksize=32768,dtype='int16',always_2d=True):output.write(block[:,0]);decoded+=len(block)
            assert decoded==frames
        assert sha(mono)==expected[meeting][0], 'Recovered mono differs from pre-cleanup source; do not compare quality'
        row={'meeting':meeting,'audio':str(mono),'audioSha256':sha(mono),'audioSeconds':frames/16000,'reference':str(out/(meeting+'.TextGrid')),'referenceSha256':expected[meeting][1],'encodedSha256':item['lfs']['oid']}
        state['cases'].append(row);save()
        if meeting.startswith('S_'):
            smoke=out/'engine-smoke30s-restored.wav'
            with wave.open(str(mono),'rb') as inp:params=inp.getparams();pcm=inp.readframes(30*16000)
            with wave.open(str(smoke),'wb') as dst:dst.setparams(params);dst.writeframes(pcm)
            manifest=[{'meeting':'engine-smoke30s-restored-20261105','audio':str(smoke),'audioSha256':sha(smoke),'audioSeconds':30.,'smokeOnly':True}]
            (proof/'compatibility-audio-only.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    state.update(state='TWO_PREVIOUS_PUBLIC_MEETINGS_RESTORED_EXACT_AUDIO_AND_REFERENCE_HASHES',activeMeeting=None)
except BaseException as error:
    state.update(state='PUBLIC_AUDIO_RESTORE_FAILURE_RETAINED',error=repr(error));raise
finally:
    state.update(finishedAt=now(),wallSeconds=round(time.perf_counter()-begin,3));save();print(json.dumps(state,ensure_ascii=False),flush=True)
