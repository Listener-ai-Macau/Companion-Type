"""Bounded official train-archive header check; never fetch evaluation data."""
from pathlib import Path
from datetime import datetime
import hashlib,io,json,urllib.request,zlib,tarfile,wave
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/alimeeting-intake-audit-r1')
url='https://speech-lab-share-data.oss-cn-shanghai.aliyuncs.com/AliMeeting/openlr/Train_Ali_far.tar.gz'
target=E/'official-train-first1048576bytes.bin';assert not target.exists()
result={'at':datetime.now().astimezone().isoformat(),'state':'CHECKING_OFFICIAL_TRAIN_ARCHIVE_PREFIX',
    'url':url,'maximumResponseBodyBytes':1048576,'evaluationOrTestUrlRequested':False,
    'fullArchiveDownloaded':False,'trainingAdmitted':False,'neuralCalls':0,'parameterUpdates':0}
try:
    request=urllib.request.Request(url,headers={'Range':'bytes=0-1048575','User-Agent':'Companion-public-training-intake/1.0'})
    with urllib.request.urlopen(request,timeout=20) as response:
        raw=response.read(1048576);result.update(httpStatus=response.status,contentRange=response.headers.get('Content-Range'),
            etag=response.headers.get('ETag'),lastModified=response.headers.get('Last-Modified'))
    target.write_bytes(raw);result.update(receivedBytes=len(raw),prefixSha256=hashlib.sha256(raw).hexdigest())
    expanded=zlib.decompressobj(16+zlib.MAX_WBITS).decompress(raw,4*1024**2)
    result['maximumDecompressedPrefixBytes']=4*1024**2;result['decompressedBytes']=len(expanded)
    entries=[];position=0
    while position+512<=len(expanded):
        block=expanded[position:position+512]
        if not any(block):break
        info=tarfile.TarInfo.frombuf(block,encoding='utf-8',errors='strict')
        data=expanded[position+512:min(len(expanded),position+512+info.size)]
        item={'name':info.name,'bytes':info.size,'type':info.type.decode('ascii'),'headerChecksumVerified':True,
            'prefixPayloadBytesAvailable':len(data),'completeMemberAvailable':len(data)==info.size}
        if info.name.lower().endswith('.wav'):
            with wave.open(io.BytesIO(data),'rb') as audio:
                item['waveHeader']={'channels':audio.getnchannels(),'sampleWidth':audio.getsampwidth(),
                    'sampleRate':audio.getframerate(),'frames':audio.getnframes(),'audioSeconds':audio.getnframes()/audio.getframerate()}
            result['trainingAudioPrefixOpened']=True
        entries.append(item)
        if len(data)!=info.size:break
        position+=512+((info.size+511)//512)*512
    result.update(state='OFFICIAL_TRAIN_PREFIX_HEADER_INSPECTED_NOT_FULL_SOURCE_VERIFICATION',entries=entries,
        fullAudioOrOriginalAnnotationVerified=False)
except BaseException as error:result.update(state='OFFICIAL_TRAIN_PREFIX_CHECK_FAILED_RETAINED_NO_RETRY',error=repr(error))
(E/'official-train-prefix-inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
