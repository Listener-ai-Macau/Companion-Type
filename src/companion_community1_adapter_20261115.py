"""Lossless local boundary for an optional upstream Community1 comparison.

Keep overlapping regular diarization and full precision. Exclusive intervals
are a separate diagnostic and never substitute for the original strict score.
"""
from pathlib import Path
import ctypes,hashlib,json,math,wave
from companion_local_pcm_session_20261114 import atomic_json

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def pin_rocm_blas(path,expected_sha256):
 assert sha(path)==expected_sha256
 library=ctypes.CDLL(str(path))
 get=library.openblas_get_num_threads;get.argtypes=[];get.restype=ctypes.c_int
 set_threads=library.openblas_set_num_threads;set_threads.argtypes=[ctypes.c_int];set_threads.restype=None
 before=get();set_threads(1);assert get()==1
 return {'library':str(path),'sha256':expected_sha256,'before':before,'after':get()}

def read_pcm_tensor(case,torch):
 import numpy as np
 assert set(case)=={'meeting','audio','audioSha256','audioSeconds'}
 assert sha(case['audio'])==case['audioSha256']
 with wave.open(case['audio'],'rb') as stream:
  assert (stream.getframerate(),stream.getnchannels(),stream.getsampwidth(),stream.getcomptype())==(16000,1,2,'NONE')
  frames=stream.getnframes();assert frames/16000==case['audioSeconds']
  pcm=stream.readframes(frames);assert len(pcm)==frames*2
 samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32);samples/=32768
 tensor=torch.from_numpy(samples.reshape(1,-1))
 return tensor,{'frames':frames,'sampleRate':16000,'channels':1,
  'pcmSha256':hashlib.sha256(pcm).hexdigest(),'normalization':'Exact PCM16/32768 only','sourceWavSha256':case['audioSha256']}

def annotation_rows(annotation):
 rows=[]
 for segment,track,speaker in annotation.itertracks(yield_label=True):
  start,end=float(segment.start),float(segment.end);speaker=str(speaker)
  assert math.isfinite(start) and math.isfinite(end) and 0<=start<end
  assert speaker and not any(c.isspace() for c in speaker)
  rows.append({'start':start,'end':end,'track':str(track),'speaker':speaker})
 return rows

def rttm_text(rows,meeting):
 assert meeting and not any(c.isspace() for c in meeting)
 return ''.join(f"SPEAKER {meeting} 1 {r['start']:.9f} {r['end']-r['start']:.9f} <NA> <NA> {r['speaker']} <NA> <NA>\n" for r in rows)

def export_output(output,directory,*,case,binding):
 import numpy as np
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
 regular=annotation_rows(output.speaker_diarization)
 exclusive=annotation_rows(output.exclusive_speaker_diarization)
 value={'meeting':case['meeting'],'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
  'regular':regular,'exclusiveDiagnosticOnly':exclusive,'binding':binding,
  'originalFloatTimesPreserved':True,'speakerIdentityVerified':False,'qualityQualified':False}
 atomic_json(directory/'raw-output.json',value)
 for name,rows in [('predicted',regular),('exclusive-diagnostic-only',exclusive)]:
  (directory/(name+'.rttm')).write_text(rttm_text(rows,case['meeting']),encoding='utf-8',newline='\n')
 embeddings=output.speaker_embeddings
 if embeddings is not None:
  embeddings=np.asarray(embeddings);assert embeddings.ndim==2 and len(embeddings)==len(output.speaker_diarization.labels())
  assert np.isfinite(embeddings).all();np.save(directory/'speaker-embeddings.npy',embeddings,allow_pickle=False)
 receipt={'state':'COMPLETE_ORIGINAL_REGULAR_AND_EXCLUSIVE_LOGS_SEPARATELY_PRESERVED',
  'regularIntervals':len(regular),'exclusiveIntervals':len(exclusive),
  'predictedAnonymousSpeakers':len({r['speaker'] for r in regular}),
  'regularRttmSha256':sha(directory/'predicted.rttm'),'rawOutputSha256':sha(directory/'raw-output.json'),
  'scoringOutput':'predicted.rttm','exclusiveOutputUsedForQualification':False,'qualityQualified':False}
 atomic_json(directory/'output-receipt.json',receipt)
 return receipt
