"""Fetch only needed lossless source ranges; keep original microphone-zero samples."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,tarfile,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from target_activity_remote_data_20261108 import PublicRangeFile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-target-activity-adaptation';E=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);assert not (C/'prepared-audio.json').exists();state={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARING_REAL_TRAINING_AUDIO_RANGES','newNeuralCalls':0,'completedExcerpts':0,'sources':[]};atomic_json(C/'audio-preparation-state.json',state);tick=time.perf_counter()
import numpy as np
import soundfile as sf
queries=read(C/'training-inputs-only.json');profiles=read(C/'supervised-enrollment-plan.json');prepared=[]
try:
    for index,source in enumerate(read(C/'selected-training-sources.json')):
        folder=E/'ranges'/source['meeting'];remote=PublicRangeFile(source['url'],source['fileSize'],folder,max_download_bytes=64*1024**2)
        if index==0:
            with tarfile.open(E/'train_L-prefix-2MiB.gz',mode='r|gz') as archive:
                for member in archive:
                    if member.name=='train_L/wav/20200707_L_R001S08C01.flac':original=archive.extractfile(member).read(65536);break
                else:raise ValueError('Official archive prefix lost its expected first FLAC member')
            assert remote.read(len(original))==original,'Pinned transport mirror differs from official OpenSLR audio prefix';remote.seek(0)
        with sf.SoundFile(remote) as stream:
            assert stream.samplerate==16000 and stream.channels==8 and stream.subtype=='PCM_16'
            source_receipt={'meeting':source['meeting'],'samplerate':stream.samplerate,'channels':stream.channels,'subtype':stream.subtype,'totalFramesFromFlacHeader':stream.frames,'expectedWholeFileSha256NotVerifiedByPartialRanges':source['expectedWholeFileLfsSha256'],'downloadedNewRangeBytes':0}
            items=[('query',r) for r in queries if r['meeting']==source['meeting']]+[('profile',r) for r in profiles if r['meeting']==source['meeting']]
            for kind,item in sorted(items,key=lambda pair:pair[1]['startSample']):
                dest=E/'audio'/kind/(item['id']+'.wav');dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists():
                    assert stream.seek(item['startSample'])==item['startSample'];audio=stream.read(item['endSample']-item['startSample'],dtype='int16',always_2d=True);assert audio.shape==(item['endSample']-item['startSample'],8)
                    with wave.open(str(dest),'wb') as output:output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(np.ascontiguousarray(audio[:,0],dtype='<i2').tobytes())
                with wave.open(str(dest),'rb') as check:assert check.getnframes()==item['endSample']-item['startSample'] and check.getframerate()==16000 and check.getnchannels()==1
                digest=hashlib.sha256(dest.read_bytes()).hexdigest();prepared.append({**item,'kind':kind,'audio':str(dest),'audioSha256':digest,'audioSeconds':(item['endSample']-item['startSample'])/16000,'originalSourceChannel':0,'sourceSamplesUnaltered':True})
                state['completedExcerpts']=len(prepared);source_receipt['downloadedNewRangeBytes']=remote.downloaded;atomic_json(C/'audio-preparation-state.json',state,progress=True)
        atomic_json(C/('source-ranges-'+source['meeting']+'.json'),{'sourceUrl':source['url'],'repositoryRevision':source['repositoryRevision'],'sourceWholeFileSize':source['fileSize'],'wholeFilePayloadShaNotVerified':True,'blocksDownloadedThisAttempt':remote.receipts,'rangeCacheBytesPresent':sum(p.stat().st_size for p in folder.glob('*.bin'))})
        source_receipt['downloadedNewRangeBytes']=remote.downloaded;state['sources'].append(source_receipt);atomic_json(C/'audio-preparation-state.json',state)
    assert len(prepared)==len(queries)+len(profiles)==114
    atomic_json(C/'prepared-audio.json',prepared);state.update(state='COMPLETE_INDEPENDENT_REAL_TRAINING_AUDIO_PREPARATION',rawAudioUploaded=False,selectedQueries=len(queries),selectedProfiles=len(profiles),firstAudioPrefixMatchesOfficialOpenSlr=True,qualityQualified=False)
except BaseException as error:state.update(state='TRAINING_AUDIO_PREPARATION_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholePreparationSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(C/'audio-preparation-state.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)
