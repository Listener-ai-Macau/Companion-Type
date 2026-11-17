"""Read cached official RIFF metadata including WAVE_FORMAT_EXTENSIBLE; no HTTP retry."""
from pathlib import Path
from datetime import datetime
import gzip,hashlib,json,struct,tarfile,zlib
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/alimeeting-intake-audit-r1')
raw=(E/'official-train-first1048576bytes.bin').read_bytes()
old=json.loads((E/'official-train-prefix-inspection.json').read_text(encoding='utf-8'))
assert hashlib.sha256(raw).hexdigest()==old['prefixSha256']
data=zlib.decompressobj(16+zlib.MAX_WBITS).decompress(raw,4*1024**2)
entries=[];position=0;wav=None
while position+512<=len(data):
    block=data[position:position+512]
    if not any(block):break
    info=tarfile.TarInfo.frombuf(block,encoding='utf-8',errors='strict');start=position+512
    payload=data[start:min(len(data),start+info.size)]
    entry={'name':info.name,'memberBytes':info.size,'tarHeaderChecksumVerified':True,
        'completeMemberAvailable':len(payload)==info.size}
    entries.append(entry)
    if info.name.lower().endswith('.wav'):
        assert payload[:4]==b'RIFF' and payload[8:12]==b'WAVE'
        at=12;fmt=None;data_size=None
        while at+8<=len(payload):
            kind=payload[at:at+4];size=struct.unpack_from('<I',payload,at+4)[0];chunk=payload[at+8:at+8+size]
            if kind==b'fmt ':
                assert len(chunk)>=16
                code,channels,rate,byte_rate,align,bits=struct.unpack_from('<HHIIHH',chunk)
                fmt={'formatCode':code,'channels':channels,'sampleRate':rate,'byteRate':byte_rate,
                    'blockAlign':align,'bitsPerSample':bits}
                if code==65534:
                    assert len(chunk)>=40 and struct.unpack_from('<H',chunk,16)[0]>=22
                    valid,mask=struct.unpack_from('<HI',chunk,18);guid=chunk[24:40]
                    assert guid==bytes.fromhex('0100000000001000800000aa00389b71'),'Only exactPCM GUID accepted'
                    fmt.update(validBitsPerSample=valid,channelMask=mask,subformat='PCM',subformatGuidHex=guid.hex())
                else:assert code==1
            if kind==b'data':data_size=size;entry['audioPrefixPayloadBytes']=len(chunk);break
            at+=8+size+(size%2)
        assert fmt and data_size is not None and fmt['bitsPerSample']==16 and fmt['validBitsPerSample']==16
        assert fmt['channels']==8 and fmt['sampleRate']==16000 and fmt['blockAlign']==16
        assert fmt['byteRate']==16000*16 and data_size%16==0
        fmt.update(declaredPcmBytes=data_size,frames=data_size//16,audioSeconds=data_size/16/16000)
        entry['waveHeader']=fmt;wav=entry;break
    if len(payload)!=info.size:break
    position+=512+((info.size+511)//512)*512
assert wav is not None
matches=[]
with gzip.open(E/'alimeeting-far_cuts_train.jsonl.gz','rt',encoding='utf-8') as stream:
    for line in stream:
        r=json.loads(line);rec=r['recording']
        if rec.get('transforms'):continue
        if any(Path(s['source']).name==Path(wav['name']).name for s in rec['sources']):
            assert rec['sampling_rate']==16000 and rec['num_samples']==wav['waveHeader']['frames']
            matches.append({'recordingId':rec['id'],'sourceBasename':Path(wav['name']).name,
                'frames':rec['num_samples'],'channels':r['channel'],'headerFramesMatchExactly':True});break
result={'at':datetime.now().astimezone().isoformat(),'state':'PASS_CACHED_OFFICIAL_TRAIN_RIFF_HEADER_NOT_FULL_AUDIO_OR_TEXTGRID_PROOF',
    'prefixSha256':old['prefixSha256'],'newNetworkRequests':0,'officialPrefixBytes':len(raw),
    'originalArchiveDeclaredBytes':78639309701,'entries':entries,'conversionMetadataMatch':matches,
    'python311WaveModuleFailureReason':'Format65534 WAVE_FORMAT_EXTENSIBLE; verifiedPCM subformatGUID/16bits/8channels/16k fromRIFF header.',
    'firstAttemptFailureRetained':str(E/'official-train-prefix-inspection.json'),
    'trainingAudioPrefixOpened':True,'fullAudioOrOriginalTextgridVerified':False,'trainingAdmitted':False,
    'requiresSingleChannelExtractionFromRawPcm':True,'mixingOrAveragingChannelsApproved':False,
    'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False}
target=E/'official-train-prefix-riff-r2.json';assert not target.exists()
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
