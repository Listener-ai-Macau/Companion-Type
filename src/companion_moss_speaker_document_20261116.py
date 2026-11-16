"""Prediction-only native MOSS local IDs -> continuous native8 global IDs.

Pure finalization, after both neural workers exited. No reference labels,
speaker counts, text cleaning, lexical deduplication or new neural inference.
"""
from pathlib import Path
import hashlib,json,math
import numpy as np
from scipy.optimize import linear_sum_assignment
from companion_moss_raw_output_20261116 import parse_native
from companion_exclusive_journal_20261114 import exclusive_journal
from practical_nemotron_worker_20261107 import probability_segments
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def overlap(a,b):
 total=0.;i=j=0
 while i<len(a) and j<len(b):
  total+=max(0.,min(a[i]['end'],b[j]['end'])-max(a[i]['start'],b[j]['start']))
  if a[i]['end']<b[j]['end']:i+=1
  else:j+=1
 return total
def union(rows):
 out=[]
 for row in sorted(rows,key=lambda r:(r['start'],r['end'])):
  if out and row['start']<=out[-1]['end']:out[-1]['end']=max(out[-1]['end'],row['end'])
  else:out.append(dict(row))
 return out
def join_recording(session,*,audio,probability_root,speaker_result_root):
 document=session.document();assert document['isFinal'] and document['finalDecodedFrames']==audio['frames']
 probability_root=Path(probability_root);speaker_result_root=Path(speaker_result_root)
 producer=read(speaker_result_root/'completed-state.json');journal=read(speaker_result_root/'speaker-journal.json');meta=read(probability_root/'probabilities.json')
 assert producer['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' and producer['allOriginalAudioSamplesSubmitted'] and producer['oneContinuousSpeakerState']
 assert producer['gpuUsed'] is False and producer['backend']=='cpu'
 assert producer['audioSha256']==journal['audioSha256']==meta['audioSha256']==audio['audioSha256']
 data=np.load(probability_root/'probabilities.npy',mmap_mode='r',allow_pickle=False);frames=meta['committedFrames'];cadence=producer['nativeSecondsPerFrame']
 assert hashlib.sha256(memoryview(data[:frames]).cast('B')).hexdigest()==meta['committedPrefixSha256']
 assert probability_segments(data,frames,cadence,audio['audioSeconds'],.5)==journal['segments']
 exclusive,receipt=exclusive_journal(data,frames=frames,seconds_per_frame=cadence,source_journal=journal)
 global_ids=sorted({r['speaker'] for r in exclusive['segments']})
 finals=sorted((read(p) for p in (session.root/'results').glob('*.json') if read(p)['request']['blockFinal']),key=lambda r:r['request']['startFrame'])
 utterances=[];traces=[];all_text=[];cursor=0;invalid=[];unknown=0
 for record in finals:
  job=record['request'];result=record['result'];assert job['startFrame']==cursor and result['accepted'] and result['naturalEos']
  cursor=job['endFrame'];offset=job['startFrame']/16000;seconds=(job['endFrame']-job['startFrame'])/16000
  parsed,rows,residual=parse_native(result['rawDecoded']);assert ' '.join(r['text'] for r in rows)==result['text']
  valid=lambda r: r['speaker'] is not None and math.isfinite(r['start']) and 0<=r['start']<r['end']<=seconds
  local=sorted({r['speaker'] for r in rows if valid(r)});matrix=np.zeros((len(local),len(global_ids)))
  for i,s in enumerate(local):
   selected=union([dict(r,start=offset+r['start'],end=offset+r['end']) for r in rows if valid(r) and r['speaker']==s])
   for j,g in enumerate(global_ids):matrix[i,j]=overlap(selected,[r for r in exclusive['segments'] if r['speaker']==g])
  rr,cc=linear_sum_assignment(-matrix);mapping={local[i]:global_ids[j] for i,j in zip(rr,cc) if matrix[i,j]>0}
  # Preserve the PCM document's exact character sequence, including all spaces
  # between native segments and all newlines between complete source blocks.
  for i,row in enumerate(rows):
   prefix=('\n' if job['block'] else '') if i==0 else ' '
   native=mapping.get(row['speaker']) if valid(row) else None
   start=(offset+row['start'])*1000 if valid(row) else job['startFrame']/16
   end=(offset+row['end'])*1000 if valid(row) else job['endFrame']/16
   if not valid(row) and row['speaker'] is not None:invalid.append({'job':job['jobId'],'row':i,'nativeStart':row['start'],'nativeEnd':row['end']})
   text=prefix+row['text'];unknown+=len(text) if native is None else 0
   utterances.append({'text':text,'startMs':start,'endMs':end,'speaker':'speaker_'+str(native) if native is not None else None,
    'approximateTiming':True,'nativeTimeValid':valid(row),'speakerIdentityVerified':False,'wordTimingVerified':False,'sourceBlock':job['block'],'sourceRevision':job['jobId']})
   all_text.append(text)
  if not rows:
   # Empty/silent final blocks still contribute the exact document separator.
   text='\n' if job['block'] else ''
   utterances.append({'text':text,'startMs':job['startFrame']/16,'endMs':job['endFrame']/16,'speaker':None,'approximateTiming':True,
    'nativeTimeValid':False,'speakerIdentityVerified':False,'wordTimingVerified':False,'sourceBlock':job['block'],'sourceRevision':job['jobId']});all_text.append(text)
  traces.append({'job':job,'localToNativeGlobal':mapping,'matrixLocalOrder':local,'matrixGlobalOrder':global_ids,'overlapSecondsMatrix':matrix.tolist(),'residualKeptUnknown':residual})
 assert cursor==audio['frames'] and ''.join(all_text)==document['text']
 final={**document,'utterances':utterances,'text':''.join(all_text),'speakerJournalApplied':True,'speakerIdentityVerified':False,'wordTimingVerified':False,
  'reviewRequired':True,'qualityQualified':False,'sourceUploaded':False,'localOnly':True,'unrecognizedAudio':[],'unknownSpeakerTextCharacters':unknown,
  'nativeInvalidTimeSegments':invalid,'speakerJournalContinuity':'One continuous CPU native8 state over all original input samples; native MOSS IDs reset only locally and are linked through predicted whole-source activity.'}
 return final,{'blocks':traces,'exclusiveDerivation':receipt,'rawSpeakerJournalRetained':True,'referencesRead':False,'trueSpeakerCountsRead':False,'wordsRewritten':False,'newNeuralCalls':0}
