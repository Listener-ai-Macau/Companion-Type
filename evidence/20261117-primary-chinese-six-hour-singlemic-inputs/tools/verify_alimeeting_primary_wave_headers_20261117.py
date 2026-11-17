"""Check every released train WAV's real header against source labels and conversion."""
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import csv,gzip,hashlib,json,re,struct,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from reference_textgrid_20261104 import read_reference_intervals
from durable_model_state_20261117 import atomic_json
from alimeeting_public_oss_20261117 import PublicAliTrainingStore
import psutil
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';A=E/'alimeeting-intake-audit-r1';out=O/'primary-wave-headers-r1';out.mkdir()
state={'at':datetime.now().astimezone().isoformat(),'state':'PREPARING_PRIMARY209_TRAIN_WAVE_HEADERS',
    'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'helperSha256':hashlib.sha256(Path(__file__).with_name('alimeeting_public_oss_20261117.py').read_bytes()).hexdigest(),
    'entries':[],'headerBytesRequestedPerSource':4096,'parallelRequests':2,'automaticRetries':0,
    'evalOrTestFilesRequested':False,'fullAudioDownloaded':False,'neuralCalls':0,'parameterUpdates':0,'trainingAdmitted':False}
def save():
    state.update(observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
pressure=SystemRamPressure();began=time.monotonic();save()
def stop():
    assert not pressure.low() and psutil.virtual_memory().available>=3414499000,'Original RAM floor'
    assert time.monotonic()-began<600 and not(out/'stop.request').exists(),'Bounded train-header audit cutoff'
def parse(raw,total):
    assert raw[:4]==b'RIFF' and raw[8:12]==b'WAVE' and struct.unpack_from('<I',raw,4)[0]+8==total
    at=12;fmt=None
    while at+8<=len(raw):
        kind=raw[at:at+4];n=struct.unpack_from('<I',raw,at+4)[0];chunk=raw[at+8:at+8+n]
        if kind==b'fmt ':
            assert len(chunk)>=16;code,ch,sr,rate,align,bits=struct.unpack_from('<HHIIHH',chunk)
            assert code in (1,65534) and (ch,sr,align,bits,rate)==(8,16000,16,16,256000)
            if code==65534:
                assert len(chunk)>=40 and struct.unpack_from('<H',chunk,18)[0]==16
                assert chunk[24:40]==bytes.fromhex('0100000000001000800000aa00389b71')
            fmt={'formatCode':code,'channels':ch,'sampleRate':sr,'bits':bits,'blockAlign':align}
        if kind==b'data':
            assert fmt and n%16==0 and at+8+n<=total
            return {**fmt,'frames':n//16,'dataBytes':n,'dataOffset':at+8,
                'headerSha256':hashlib.sha256(raw[:at+8]).hexdigest()}
        at+=8+n+n%2
    raise ValueError('PCM header not fully present in bounded source prefix')
try:
    store=PublicAliTrainingStore(O/'Train_Ali_far.csv');catalog={};raw_cut_count=0
    with gzip.open(A/'alimeeting-far_cuts_train.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line);rec=r['recording']
            if rec.get('transforms'):continue
            raw_cut_count+=1
            v={'frames':rec['num_samples'],'sampleRate':rec['sampling_rate'],
                'sourceBasenames':sorted(Path(s['source']).name for s in rec['sources'])}
            if rec['id'] in catalog:assert catalog[rec['id']]==v,'Converted recording metadata differs between cuts'
            else:catalog[rec['id']]=v
    assert len(catalog)==209 and raw_cut_count==186364
    atomic_json(out/'converted-recording-catalog.json',catalog)
    def probe(row):
        path=row['Audio:FILE'];meeting=Path(row['Text:FILE']).stem;stop()
        assert Path(path).name in catalog[meeting]['sourceBasenames']
        with store.open(path,byte_range=(0,4095)) as response:
            assert response.status==206;raw=response.read(4097);assert len(raw)==4096
            match=re.fullmatch(r'bytes 0-4095/(\d+)',response.headers['Content-Range']);assert match
            total=int(match.group(1));etag=response.headers.get('ETag','').strip('"')
        header=parse(raw,total);original=read_reference_intervals(O/'original-textgrids'/(meeting+'.TextGrid'))
        speech=[r for r in original if r['text'] and r['end']>r['start']]
        outside=[r for r in speech if round(r['end']*16000)>header['frames']]
        return {'meeting':meeting,'file':path,'objectBytes':total,'etag':etag,'header':header,
            'convertedMetadataFrames':catalog[meeting]['frames'],'originalWavFramesMatchConvertedMetadata':header['frames']==catalog[meeting]['frames'],
            'originalAnnotationSpeechIntervals':len(speech),'speechIntervalsPastActualAudioEnd':len(outside),
            'latestOriginalSpeechEndFrame':max(round(r['end']*16000) for r in speech),
            'singleMicCandidateSourceStructurallyAdmissible':not outside and header['frames']==catalog[meeting]['frames']}
    todo=iter(store.rows)
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending={}
        def submit():
            row=next(todo,None)
            if row is not None:pending[executor.submit(probe,row)]=row['Audio:FILE']
        submit();submit();save()
        while pending:
            stop();finished,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
            for f in finished:
                pending.pop(f);state['entries'].append(f.result());save();submit()
    assert len(state['entries'])==209
    state.update(state='COMPLETE_PRIMARY209_WAVE_HEADER_AND_ORIGINAL_LABEL_BOUNDS_AUDIT',
        allOriginalHeadersMatchConvertedFrameCounts=all(r['originalWavFramesMatchConvertedMetadata'] for r in state['entries']),
        originalLabelsPastActualWaveEnd=sum(r['speechIntervalsPastActualAudioEnd'] for r in state['entries']),
        inadmissibleSourceMeetings=[r['meeting'] for r in state['entries'] if not r['singleMicCandidateSourceStructurallyAdmissible']],
        cleanSourceMeetings=sum(r['singleMicCandidateSourceStructurallyAdmissible'] for r in state['entries']),
        retrievedHeaderPrefixBytes=209*4096,elapsedSeconds=time.monotonic()-began,
        originalLabelsOrEvaluationMetricsChanged=False)
    save();atomic_json(out/'completed.json',state)
except BaseException as error:state.update(state='FAILED_PRIMARY_TRAIN_WAVE_HEADER_AUDIT_RETAINED',error=repr(error));save();raise
finally:pressure.close()
print(json.dumps({k:v for k,v in state.items() if k!='entries'},ensure_ascii=False))
