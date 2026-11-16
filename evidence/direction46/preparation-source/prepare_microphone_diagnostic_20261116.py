"""Freeze one inference-only microphone diagnostic; never train or infer.

The official headset mix is an easier recording condition for causal diagnosis,
not the product's single distant microphone and not a new acceptance score.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
import hashlib
import json
import os
import struct
import sys
import urllib.request
import wave

os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'model-research/src'; sys.path.insert(0,str(S))
import numpy as np
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
from meeting_acoustic_contract_20261116 import read,require,sha

D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r2'
J=D/'joint-architecture-r1/microphone-diagnostic-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/microphone-diagnostic-r1')
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2); pressure=SystemRamPressure()
require(not pressure.low(),'Windows low RAM')
J.mkdir(exist_ok=True); E.mkdir(exist_ok=True); (E/'audio').mkdir(exist_ok=True)
require(not (J/'pairing.json').exists(),'Do not overwrite an exited pairing diagnostic')
cases=[r for r in read(C/'scoring-only.json') if r['language']=='English' and r['role']=='validation']
require(len(cases)==12 and not any(r['overlapPresentByReference'] for r in cases),'Fixed original English cohort required')
source_cache={}; downloaded_bytes=0; pairs=[]
prior_failure=read(J/'preparation-failure.json') if (J/'preparation-failure.json').exists() else None
prior_pairs={r['id']:r for r in prior_failure['completedPairs']} if prior_failure else {}
if prior_failure:
    archive=J/('preparation-failure-'+sha(J/'preparation-failure.json')[:16]+'.json')
    if not archive.exists():
        archive.write_bytes((J/'preparation-failure.json').read_bytes())
    for meeting in {r['meeting'] for r in prior_pairs.values()}:
        source_cache[meeting]=prior_failure['sources'][meeting]
(E/'range-cache').mkdir(exist_ok=True)


def request_range(url,first,last):
    global downloaded_bytes
    require(not pressure.low(),'Windows low RAM')
    if last-first+1>262144:
        parts=[]; receipts=[]
        for position in range(first,last+1,262144):
            body,receipt=request_range(url,position,min(last,position+262144-1))
            parts.append(body); receipts.append(receipt)
        require(len({(r['sourceBytes'],r['etag']) for r in receipts})==1,'Remote object changed across bounded ranges')
        combined=dict(receipts[0],contentRange=f'bytes {first}-{last}/{receipts[0]["sourceBytes"]}',assembledRanges=receipts)
        return b''.join(parts),combined
    key=hashlib.sha256(url.encode()).hexdigest()[:16]+f'-{first}-{last}'
    cached=E/'range-cache'/(key+'.bin'); metadata=E/'range-cache'/(key+'.json')
    if cached.exists() and metadata.exists():
        saved=read(metadata); data=cached.read_bytes()
        require(len(data)==last-first+1 and sha(cached)==saved['payloadSha256'],'Cached official byte range changed')
        return data,saved['receipt']
    request=urllib.request.Request(url,headers={'Range':f'bytes={first}-{last}',
        'Accept-Encoding':'identity','User-Agent':'Companion-public-audio-diagnostic/1.0'})
    with urllib.request.urlopen(request,timeout=45) as response:
        require(response.status==206,'Official server did not honor bounded Range request')
        content=response.headers.get('Content-Range','')
        require(content.startswith(f'bytes {first}-{last}/'),'Unexpected remote byte range')
        total=int(content.split('/')[-1]); data=response.read(last-first+2)
        require(len(data)==last-first+1,'Incomplete/oversized remote byte range')
        downloaded_bytes+=len(data)
        receipt={'url':url,'contentRange':content,'sourceBytes':total,
                 'etag':response.headers.get('ETag'),'lastModified':response.headers.get('Last-Modified')}
        require(not cached.exists() and not metadata.exists(),'Incomplete byte-range cache requires inspection')
        cached.write_bytes(data)
        atomic_json(metadata,{'payloadSha256':sha(cached),'receipt':receipt})
        return data,receipt


def remote_header(meeting):
    url=f'https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/HeadsetAudio/{meeting}.Mix-Headset.wav'
    prefix,receipt=request_range(url,0,4095)
    require(prefix[:4]==b'RIFF' and prefix[8:12]==b'WAVE','Not a RIFF/WAVE source')
    require(struct.unpack('<I',prefix[4:8])[0]+8==receipt['sourceBytes'],'Remote source length mismatch')
    pos=12; fmt=None; offset=None; length=None
    while pos+8<=len(prefix):
        kind=prefix[pos:pos+4]; count=struct.unpack('<I',prefix[pos+4:pos+8])[0]
        if kind==b'fmt ':
            fmt=struct.unpack('<HHIIHH',prefix[pos+8:pos+24])
        if kind==b'data':
            offset=pos+8; length=count; break
        pos+=8+count+(count%2)
    require(fmt==(1,1,16000,32000,2,16) and offset is not None and length%2==0,'Unexpected official PCM format')
    header=dict(receipt,dataOffset=offset,frames=length//2,headerSha256=hashlib.sha256(prefix).hexdigest())
    if prior_failure and meeting in prior_failure['sources']:
        old=prior_failure['sources'][meeting]
        require(all(header[key]==old[key] for key in ['sourceBytes','dataOffset','frames','headerSha256']),
                'Official alternative endpoint is not the same source file')
    return header


def pcm(path):
    with wave.open(str(path),'rb') as stream:
        require((stream.getnchannels(),stream.getframerate(),stream.getsampwidth())==(1,16000,2),'Wrong local PCM')
        return stream.readframes(stream.getnframes())


def envelope_alignment(a,b):
    def envelope(data):
        x=np.frombuffer(data,dtype='<i2').astype(np.float64)
        count=len(x)//320; blocks=x[:count*320].reshape(count,320)
        return np.sqrt(np.mean(blocks*blocks,axis=1))
    x,y=envelope(a),envelope(b); require(len(x)==len(y),'Paired frame lengths changed')
    values=[]
    for lag in range(-25,26):
        a=x[max(0,lag):min(len(x),len(x)+lag)]
        b=y[max(0,-lag):min(len(y),len(y)-lag)]
        a=a-a.mean(); b=b-b.mean(); denom=float(np.linalg.norm(a)*np.linalg.norm(b))
        values.append((float(a@b/denom) if denom else -1.,lag))
    correlation,lag=max(values)
    return {'bestEnvelopeCorrelation':correlation,'bestEnvelopeLagMs':lag*20,
            'shiftApplied':False,'diagnosticOnly':True}


try:
    for case in cases:
        meeting=case['meeting']
        if case['id'] in prior_pairs:
            old=prior_pairs[case['id']]
            require(sha(old['distant']['audio'])==old['distant']['audioSha256']
                    and sha(old['headsetMix']['audio'])==old['headsetMix']['audioSha256'],
                    'A completed paired clip changed')
            pairs.append(old)
            continue
        if meeting not in source_cache:
            source_cache[meeting]=remote_header(meeting)
        header=source_cache[meeting]
        start,end=case['sourceStartFrame'],case['sourceEndFrame']
        require(0<=start<end<=header['frames'],'Requested clip is outside official headset source')
        require(sha(case['wav'])==case['wavSha256'],'Original distant audio changed')
        first=header['dataOffset']+start*2; last=header['dataOffset']+end*2-1
        data,receipt=request_range(header['url'],first,last)
        require(receipt['etag']==header['etag'] and receipt['sourceBytes']==header['sourceBytes'],'Official source changed between range requests')
        near=E/'audio'/(case['id']+'-headset-mix.wav')
        require(not near.exists(),'Preserve an already downloaded diagnostic clip')
        with wave.open(str(near),'wb') as stream:
            stream.setnchannels(1); stream.setframerate(16000); stream.setsampwidth(2); stream.writeframes(data)
        far_pcm=pcm(case['wav'])
        require(len(far_pcm)==len(data)==case['frames']*2,'Frame mismatch across recorded views')
        alignment=envelope_alignment(far_pcm,data)
        pair={'id':case['id'],'meeting':meeting,'language':'English','frames':case['frames'],
              'sourceStartFrame':start,'sourceEndFrame':end,
              'distant':{'audio':case['wav'],'audioSha256':case['wavSha256'],'pcmSha256':hashlib.sha256(far_pcm).hexdigest()},
              'headsetMix':{'audio':str(near),'audioSha256':sha(near),'pcmSha256':hashlib.sha256(data).hexdigest()},
              'remoteRange':receipt,'timebaseInspection':alignment,
              'referenceUsedToSelectSpeakersOrMaskWaveforms':False,
              'gainDenoiseOrResamplingApplied':False}
        pairs.append(pair)
    baseline=read(C/'raw-text-baseline.json')
    native_state=read(Path(baseline['sourceRun'])/'baseline-state.json')
    control=next(r for r in native_state['completed'] if r['id']=='ES2003b-seq-000')
    raw=read(control['rawResult'])
    require(raw['result']['accepted'] and len(raw['result']['rawGeneratedIds'])==1,'Original exact native control unavailable')
    control_tokens=raw['result']['rawGeneratedIds'][0]
    inspection={'pairs':len(pairs),'sources':len(source_cache),'downloadedBytesThisAttempt':downloaded_bytes,
                'reusedPreparedPairs':len(prior_pairs),'preparedPcmBytes':sum(p['frames']*2 for p in pairs),
                'largestAbsoluteEnvelopeLagMs':max(abs(r['timebaseInspection']['bestEnvelopeLagMs']) for r in pairs),
                'minimumEnvelopeCorrelation':min(r['timebaseInspection']['bestEnvelopeCorrelation'] for r in pairs)}
    paired={'state':'OFFICIAL_PAIRED_MICROPHONE_INPUTS_PREPARED_NO_INFERENCE',
            'at':datetime.now().astimezone().isoformat(timespec='seconds'),
            'inspection':inspection,'sources':source_cache,'pairs':pairs,
            'control':{'caseId':control['id'],'audio':next(c['wav'] for c in cases if c['id']==control['id']),
                       'audioSha256':next(c['wavSha256'] for c in cases if c['id']==control['id']),
                       'expectedGeneratedIds':control_tokens,'originalRawResult':control['rawResult'],
                       'originalRawResultSha256':sha(control['rawResult'])},
            'sourceManifests':[{'file':str(p),'sha256':sha(p)} for p in [C/'audio-only.json',C/'scoring-only.json',C/'raw-text-baseline.json']],
            'sourceSha256':sha(__file__),
            'scope':'Same12 exposed nonoverlap English clips; original array-channel microphone versus official non-reference-selected headset mix. An acoustic-condition diagnostic, never a single-microphone product acceptance score.',
            'timePolicy':'Same official annotation timeline and original frame intervals. Envelope correlation is inspected, never used to shift audio or optimize a transcript. Whole source tails can differ; all selected clips are within both sources.',
            'expectedNewGpuDecodes':13,'trainingUpdates':0,'newNeuralCalls':0,
            'preparationRecovery':{'priorFailurePreserved':bool(prior_failure),
                'change':'Per-session range GET timed out; the official HeadsetAudio index endpoint succeeded for the same byte interval. A later large-range timeout motivated fixed256KiB requests with verified partial caching; completed paired clips are reused. Source header/size/frame counts remain identical. No proxy/DNS/timeout changes.',
                'unchangedCompletedPairsReused':len(prior_pairs)},
            'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    atomic_json(J/'pairing.json',paired)
    print(json.dumps({'state':paired['state'],**inspection,'newNeuralCalls':0},ensure_ascii=False))
except BaseException as error:
    import traceback
    atomic_json(J/'preparation-failure.json',{'error':repr(error),'traceback':traceback.format_exc(),
                'completedPairs':pairs,'sources':source_cache,'downloadedBytes':downloaded_bytes,
                'newNeuralCalls':0,'trainingUpdates':0,'qualityQualified':False})
    raise
finally:
    pressure.close()
