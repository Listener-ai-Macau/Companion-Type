"""Original hardware-pair readback plus anti-phase and false-stereo controls."""
from pathlib import Path
from datetime import datetime
import hashlib,json,struct,tempfile,wave
from companion_multichannel_input_20261108 import inspect_recording,read_channel_blocks,require_distinct_pair,sha256_file
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-dual-mic-architecture-review'
old=Path('C:/Users/Billy/Documents/Codex/2026-10-28/companion-upper-delivery-20261028/work/isolated-sources-p692')
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
C.mkdir(exist_ok=True);assert not (C/'input-integrity-review.json').exists()
items=[]
for case in ['left-only-r2','right-only']:
    folder=old/case/'actual-pilot/independent-source';file=folder/'original-pair.wav'
    source=json.loads((folder/'source.json').read_text(encoding='utf8'))
    assert sha256_file(file)==source['pairWavSha256'] and source['sourceKind']=='SYNCHRONOUS_DUAL_PCM' and not source['synthetic']
    result=inspect_recording(file,2);require_distinct_pair(result)
    with wave.open(str(file),'rb') as stream:original=stream.readframes(stream.getnframes())
    reconstructed=bytearray()
    for start,parts in read_channel_blocks(file,137):
        count=len(parts[0])//2;block=bytearray(count*4)
        block[0::4]=parts[0][0::2];block[1::4]=parts[0][1::2]
        block[2::4]=parts[1][0::2];block[3::4]=parts[1][1::2]
        reconstructed.extend(block)
    assert bytes(reconstructed)==original and sha256_file(file)==source['pairWavSha256']
    result.update(archivedCase=case,pcmReinterleaveExactlyOriginal=True,chunkBoundaryFrames=137,
        captureMetadataFile=str(folder/'source.json'),captureMetadataSha256=sha256_file(folder/'source.json'),
        historicalMetadataDeclaresContinuity=source['continuityVerified'],
        historicalUnsignedCaptureNotNewPhysicalSynchronizationProof=True,
        sourceScope='One isolated computer-rendered source per archived2s capture, not simultaneous real meeting people or a current-board spatial qualification.')
    items.append(result)

def write(path,channels,pcm):
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(channels);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(pcm)

with tempfile.TemporaryDirectory(prefix='companion-dual-input-',dir='E:/CodexData/Companion/.model-cache') as temp:
    root=Path(temp);left=[-12345,-41,0,17,12345]*7
    anti=b''.join(struct.pack('<hh',n,-n) for n in left);file=root/'anti-phase.wav';write(file,2,anti)
    actual=inspect_recording(file,2);require_distinct_pair(actual)
    pair=next(read_channel_blocks(file,100))[1]
    assert pair[0]==b''.join(struct.pack('<h',n) for n in left) and pair[1]==b''.join(struct.pack('<h',-n) for n in left)
    mono=root/'mono.wav';write(mono,1,pair[0])
    try:inspect_recording(mono,2);raise AssertionError('Mono accepted as two microphones')
    except ValueError:pass
    duplicate=root/'duplicated.wav';write(duplicate,2,b''.join(struct.pack('<hh',n,n) for n in left))
    try:require_distinct_pair(inspect_recording(duplicate,2));raise AssertionError('Duplicated mono accepted for spatial research')
    except ValueError:pass
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CHANNEL_PRESERVING_INPUT_VERIFIED_NOT_DIARIZATION_OR_SEPARATION',
    'realArchivedInputs':items,'controls':{'antiPhaseSamplesAndPolarityPreserved':True,'monoRefusedAsTwoMicrophones':True,'duplicatedStereoRefusedForSpatialResearch':True},
    'newModels':0,'newHardwareAccess':0,'originalRecordingsModified':False,'productDefaultChanged':False,
    'actualMultiPersonTestPerformed':False,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'input-integrity-review.json',result)
print(json.dumps({'state':result['state'],'archivedPhysicalPairs':len(items),'controls':result['controls'],'newModels':0,'newHardwareAccess':0},ensure_ascii=False),flush=True)
