"""Lossless channel-preserving research input, independent of model providers.

An interleaved WAV grid does not prove physical clock synchronization. Channel
IDs are microphone IDs, never speaker IDs. No normalization, resampling, gain,
polarity change, channel averaging, or neural inference is performed here.
"""
from pathlib import Path
import argparse,hashlib,json,wave

def sha256_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def read_channel_blocks(path,frames_per_block=4096):
    """Yield start sample plus original little-endian PCM bytes per microphone."""
    if not isinstance(frames_per_block,int) or frames_per_block<=0:
        raise ValueError('frames_per_block must be a positive integer')
    with wave.open(str(path),'rb') as stream:
        channels=stream.getnchannels()
        if channels not in (1,2) or stream.getsampwidth()!=2 or stream.getcomptype()!='NONE':
            raise ValueError('Research input requires one or two explicit PCM16 WAV channels; no implicit channel selection or conversion')
        if stream.getframerate()<=0 or stream.getnframes()<=0:
            raise ValueError('Empty or invalid recording')
        start=0
        while start<stream.getnframes():
            raw=stream.readframes(frames_per_block)
            stride=channels*2
            if not raw or len(raw)%stride:
                raise ValueError('Truncated PCM frame; no padding or repair performed')
            count=len(raw)//stride
            separated=[]
            for channel in range(channels):
                pcm=bytearray(count*2)
                pcm[0::2]=raw[channel*2::stride]
                pcm[1::2]=raw[channel*2+1::stride]
                separated.append(bytes(pcm))
            yield start,tuple(separated)
            start+=count
        if start!=stream.getnframes():
            raise ValueError('PCM length differs from WAV sample count')

def inspect_recording(path,expected_channels=None):
    path=Path(path).resolve();before=path.stat();file_hash=sha256_file(path)
    with wave.open(str(path),'rb') as stream:
        channels=stream.getnchannels();rate=stream.getframerate();frames=stream.getnframes()
    if expected_channels is not None and channels!=expected_channels:
        raise ValueError(f'Expected {expected_channels} microphone channels, found {channels}; a second microphone cannot be reconstructed from mono')
    hashes=[hashlib.sha256() for _ in range(channels)];same=True;completed=0
    for start,parts in read_channel_blocks(path):
        if start!=completed:raise ValueError('Non-contiguous source sample positions')
        for digest,pcm in zip(hashes,parts):digest.update(pcm)
        if channels==2 and parts[0]!=parts[1]:same=False
        completed+=len(parts[0])//2
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or sha256_file(path)!=file_hash:
        raise ValueError('Source changed while inspecting; no partial manifest accepted')
    return {'schema':'companion.channel-preserving-research-input.v1','sourceFile':str(path),'sourceFileSha256':file_hash,
        'sampleRateHz':rate,'sampleFrames':frames,'durationSeconds':frames/rate,
        'sampleFormat':'PCM16_LE','inputChannels':channels,
        'microphoneChannels':[{'channelIndex':i,'pcmSha256':digest.hexdigest()} for i,digest in enumerate(hashes)],
        'sharedInterleavedSampleGrid':True,'physicalClockSynchronizationVerified':False,
        'identicalMicrophoneSamples':same if channels==2 else None,
        'distinctPairSamplesAvailable':channels==2 and not same,
        'speakerCount':None,'channelIndexDoesNotIdentifySpeaker':True,
        'processing':{'downmix':False,'resampling':False,'gainNormalization':False,'polarityChange':False,'neuralInference':False},
        'scope':'Input integrity only. Geometry, physical synchrony, calibration and actual multi-speaker separation remain separate requirements.'}

def require_distinct_pair(manifest):
    if manifest['inputChannels']!=2 or not manifest['distinctPairSamplesAvailable']:
        raise ValueError('Spatial research needs two non-duplicate microphone channels; mono or duplicated stereo supplies no additional spatial observation')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio',required=True,type=Path);parser.add_argument('--expected-channels',type=int,choices=[1,2])
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    from moss_windows_resource_limits_20261104 import WorkerLimits
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
    result=inspect_recording(args.audio,args.expected_channels)
    if args.output.resolve()==args.audio.resolve() or args.output.exists():
        raise ValueError('Output must be a new manifest, never an existing source')
    result['resourceLimits']=limits.query();args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'channels':result['inputChannels'],'frames':result['sampleFrames'],'distinctPairSamplesAvailable':result['distinctPairSamplesAvailable'],'sourceUnchanged':True}),flush=True)

if __name__=='__main__':main()
