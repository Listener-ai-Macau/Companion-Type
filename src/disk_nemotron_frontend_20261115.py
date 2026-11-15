"""Original no-CMVN frontend in hop-aligned disk blocks, not independent chunks.

Preemphasis uses the actual previous original sample; zero padding only at the
two global edges, after preemphasis. Final mask and all upstream STFT calls are
unchanged. A direct upstream numerical control is required by the caller.
"""
from pathlib import Path
import os,wave
def extract_wave(extractor,audio,target,*,torch,frames_per_block=3000):
 import numpy as np
 assert frames_per_block==3000 and extractor.hop_length==160 and extractor.n_fft==512
 assert not Path(target).exists()
 with wave.open(str(audio),'rb') as wav:
  assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000)
  samples=wav.getnframes();valid=samples//160;frames=valid+1
  out=np.lib.format.open_memmap(target,mode='w+',dtype=np.float32,shape=(frames,128))
  for first in range(0,frames,frames_per_block):
   last=min(first+frames_per_block,frames)
   low,high=first*160-256,(last-1)*160+256
   actual_low,actual_high=max(0,low),min(samples,high)
   read_low=max(0,actual_low-1)
   wav.setpos(read_low);pcm=wav.readframes(actual_high-read_low)
   x=torch.from_numpy(np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768)
   # Same torch pointwise expression and float32 multiplication as upstream.
   emphasized=torch.cat([x[:1],x[1:]-extractor.preemphasis*x[:-1]]) if extractor.preemphasis is not None else x
   block=torch.zeros((1,high-low),dtype=torch.float32)
   block[0,actual_low-low:actual_high-low]=emphasized[actual_low-read_low:]
   features=extractor._torch_extract_fbank_features(block,device='cpu',center=False)
   assert features.shape==(1,last-first,128)
   features*= (torch.arange(first,last)<valid)[None,:,None]
   out[first:last]=features[0].numpy()
  out.flush();del out
 with Path(target).open('rb+') as file:os.fsync(file.fileno())
 return {'frames':frames,'validFrames':valid,'samples':samples,'blockFrames':frames_per_block,
  'globalPreemphasis':True,'onlyGlobalEdgePadding':True,'originalMaskUnchanged':True,'globalCMVN':False}
