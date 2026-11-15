"""Use the exact PCM16 samples without importing a resampling/JIT pipeline."""
from pathlib import Path
import wave
import numpy as np


def install_pcm16_loader(inference_utils):
    original=inference_utils.load_audio_item
    stats={'nativePcm16Loads':0,'fallbackLoads':0,'resamplingSkippedOnlyWhenAlreadyExactFormat':True}
    def load(audio,sampling_rate):
        if isinstance(audio,(str,Path)) and str(audio).lower().endswith('.wav'):
            try:
                with wave.open(str(audio),'rb') as source:
                    if (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())==(1,2,sampling_rate,'NONE'):
                        pcm=source.readframes(source.getnframes())
                        samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)
                        samples*=np.float32(1/32768)
                        stats['nativePcm16Loads']+=1
                        return samples
            except (OSError,wave.Error):pass
        stats['fallbackLoads']+=1
        return original(audio,sampling_rate=sampling_rate)
    inference_utils.load_audio_item=load
    return stats
